"""Decouple OCR execution from any single SSE request (AR-01) via an in-process runner registry.

Before this module, ``GET /jobs/{id}/stream`` *was* the OCR trigger: the route fed ``run_ocr``
straight into the HTTP response, so closing the tab (or a network drop) stopped the OCR itself —
it only resumed on the next reconnect. That made a client's connection the source of truth for
whether transcription was happening, which is backwards: a background job shouldn't die because
nobody's watching, and multiple tabs watching the same job shouldn't double the OCR cost.

This module fixes that by giving each job's OCR run its own ``asyncio.Task`` that outlives any
individual request: ``start_runner`` spawns (or reuses) that task, and ``tail_job`` is a read-only
observer that replays already-done pages from disk, then fans in on the runner's live events.
Disconnecting only detaches an observer — it never touches the runner task.

# ponytail: in-process registry (a module-level dict), fine for marginalia's single-user,
# single-worker posture (docs/ARCHITECTURE.md). A real broker (Redis pub/sub, a separate worker
# process) would replace this if marginalia ever became multi-worker or multi-user.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Final, cast

from marginalia.jobs.service import PAGE_TIMEOUT_S, run_ocr
from marginalia.jobs.store import JobStore
from marginalia.ocr.engine import OCREngine

logger = logging.getLogger(__name__)

# Marks the end of a runner's event stream for every subscriber. A plain ``object()`` (not a dict)
# so it can never collide with a real job event, which is always a dict with a "type" key.
_SENTINEL: Final[object] = object()


@dataclass
class RunnerState:
    """One in-flight OCR run for a job: its background task plus the live subscriber fan-out.

    ``subscribers`` is mutated by ``tail_job`` (add on connect, discard on disconnect); the
    runner task only ever reads it, to publish each event to whoever's currently subscribed.
    """

    task: asyncio.Task[None]
    subscribers: set[asyncio.Queue[object]] = field(default_factory=set)


_runners: dict[str, RunnerState] = {}


def get_runner(job_id: str) -> RunnerState | None:
    """Return the live runner for a job, or ``None`` if no OCR run is currently in flight for it."""
    return _runners.get(job_id)


def start_runner(
    store: JobStore,
    engine: OCREngine,
    job_id: str,
    prompt: str | None = None,
    page_timeout: float = PAGE_TIMEOUT_S,
) -> RunnerState:
    """Ensure exactly one OCR run is in flight for ``job_id``; return its (possibly reused) state.

    Idempotent: calling this while a runner is already live for the job returns the SAME state
    instead of starting a second OCR pass. That's what lets several SSE streams (a second tab, a
    reconnect racing the original one) safely tail one job — replacing the old ``409`` guard that
    used to reject a second stream outright.

    The task is fire-and-forget: nothing here awaits it, so whatever caller triggered this (an
    HTTP request handler) can return, disconnect, or even be cancelled without affecting the OCR
    run. That decoupling is the whole point of AR-01 — see the module docstring.
    """
    existing = _runners.get(job_id)
    if existing is not None and not existing.task.done():
        return existing
    subscribers: set[asyncio.Queue[object]] = set()
    task = asyncio.ensure_future(_run_and_publish(store, engine, job_id, prompt, page_timeout, subscribers))
    state = RunnerState(task=task, subscribers=subscribers)
    _runners[job_id] = state
    return state


async def _run_and_publish(
    store: JobStore,
    engine: OCREngine,
    job_id: str,
    prompt: str | None,
    page_timeout: float,
    subscribers: set[asyncio.Queue[object]],
) -> None:
    """Drive ``run_ocr`` to completion, fanning out each event to every current subscriber.

    Runs independently of any HTTP request: started once by ``start_runner`` and never cancelled
    by a subscriber disconnecting (``tail_job`` only ever discards itself from ``subscribers``).
    All of ``run_ocr``'s existing guarantees — resume/skip-done, the preflight check, the per-page
    timeout, named error messages, and the disconnect-safe status reset in its own ``finally`` —
    are untouched; this only changes *who drives* the generator and *how many* listeners see it.
    """
    try:
        async for event in run_ocr(store, engine, job_id, prompt, page_timeout):
            for queue in subscribers:
                queue.put_nowait(event)
    finally:
        for queue in subscribers:
            queue.put_nowait(_SENTINEL)
        # Only drop the registry entry if it's still this task's — defensive, since a single
        # in-process worker means start_runner never replaces a live entry in practice.
        current = _runners.get(job_id)
        if current is not None and current.task is asyncio.current_task():
            del _runners[job_id]


async def tail_job(store: JobStore, engine: OCREngine, job_id: str) -> AsyncGenerator[dict, None]:
    """Observe a job's OCR: replay already-done pages from disk, then tail the live run (AR-01).

    This is the read-only half of the decoupling — it starts (or reuses) the job's background
    runner and never triggers OCR by itself. A late subscriber (a fresh tab, a reconnect) first
    catches up on whatever's already ``done`` on disk, replayed as the same
    page_started/page_delta(full text)/page_done triple a live run would have sent, then receives
    the runner's live events until a terminal one (``job_done``/``error``).

    Disconnecting — this generator being closed by Starlette when the client goes away — only
    unsubscribes via the ``finally`` below; the runner keeps OCRing to disk for whoever else is
    watching, or no one. (The alternative, pausing/cancelling a runner once it has zero
    subscribers, was considered and rejected: it would resurrect the old "closing the tab stops
    OCR" bug this module exists to fix, and it isn't needed for a single local user.)
    """
    state = start_runner(store, engine, job_id)
    queue: asyncio.Queue[object] = asyncio.Queue()
    state.subscribers.add(queue)
    try:
        record = store.load(job_id)
        for page in record.pages:
            if not page.done:
                continue
            yield {"type": "page_started", "index": page.index}
            yield {"type": "page_delta", "index": page.index, "text": page.markdown}
            yield {"type": "page_done", "index": page.index}
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                return
            event = cast(dict, item)
            yield event
            if event["type"] in ("job_done", "error"):
                return
    finally:
        state.subscribers.discard(queue)
