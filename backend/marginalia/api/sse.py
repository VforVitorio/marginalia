"""Format a stream of event dicts as Server-Sent Events.

Native SSE framing (docs/ARCHITECTURE.md §4): one ``data: <json>`` line per event, interleaved with
periodic ``: keep-alive`` comment frames during quiet gaps (BE-08). A cold model load (LM Studio, up
to ~2 min) or a slow first token from a cloud engine can otherwise go silent long enough for an idle
proxy or browser to drop the connection. Comment frames carry no ``data:`` line, so ``EventSource``
never fires ``onmessage`` for them — the frontend's JSON parse there already no-ops on non-JSON
payloads (see ``frontend/src/lib/sse.ts``). Shared by the jobs OCR stream and the model-pull stream.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Final

HEARTBEAT_INTERVAL_S: Final = 15.0

_SENTINEL: Final = object()


async def sse_stream(
    events: AsyncIterator[dict],
    heartbeat_interval: float = HEARTBEAT_INTERVAL_S,
) -> AsyncIterator[str]:
    """Wrap each event dict as an SSE ``data:`` frame; emit ``: keep-alive`` comments on quiet gaps.

    ``events`` (e.g. ``run_ocr``) is drained by one dedicated background task for the lifetime of the
    stream, into a queue this generator reads with a timeout. That indirection matters: a naive loop
    of ``asyncio.wait_for(events.__anext__(), timeout=...)`` would cancel the pending ``__anext__()``
    call on every heartbeat timeout — killing a page that's simply slow (e.g. a cold model load), not
    stuck. Worse, it would hand the work of driving ``events`` to a *different* task on every
    heartbeat cycle, which breaks the per-page ``asyncio.timeout()`` in ``jobs/service.py`` (BE-10):
    that timeout binds to whichever task is executing when its ``async with`` block is entered, and a
    cancellation aimed at a since-replaced task is silently dropped. Draining ``events`` from one
    persistent task sidesteps both failure modes.
    """
    queue: asyncio.Queue[object] = asyncio.Queue()

    async def _pump() -> None:
        try:
            async for event in events:
                await queue.put(event)
        finally:
            await queue.put(_SENTINEL)

    pump = asyncio.ensure_future(_pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if item is _SENTINEL:
                return
            yield f"data: {json.dumps(item)}\n\n"
    finally:
        pump.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump
