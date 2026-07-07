"""Orchestrate ingest → OCR per page, persist results, and emit SSE events.

This is the ONLY place that wires the OCR engine, the job store, and the event stream together
(docs/ARCHITECTURE.md §10). Events are plain dicts; the API layer serializes them as SSE.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

import httpx

from marginalia.jobs.store import JobStore
from marginalia.ocr.engine import OCREngine
from marginalia.ocr.prompts import HANDWRITING_PROMPT

logger = logging.getLogger(__name__)

_GENERIC_OCR_ERROR = "OCR failed — check the selected provider and model, then try again."
_PREFLIGHT_UNREACHABLE_ERROR = (
    "Can't reach the selected provider, or no model is loaded — check its status and try again."
)


def _error_message(exc: Exception) -> str:
    """Map a known OCR failure class (BE-15) to an actionable message; unknown failures stay generic.

    The engines don't catch these themselves (``ocr/openai_compat.py`` lets httpx errors propagate
    from the chat-completions stream), so this is the one place that turns "ConnectError" or a bare
    401 into something a non-technical user can act on, without leaking internals.
    """
    if isinstance(exc, httpx.ConnectError):
        return "Can't reach the OCR provider — is it running and reachable?"
    if isinstance(exc, httpx.TimeoutException):
        return "The provider didn't respond in time — the model may still be loading; try again."
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in (401, 403):
            return "The provider rejected the API key."
        if status_code == 404:
            return "The selected model isn't available on the provider."
    return _GENERIC_OCR_ERROR


async def run_ocr(
    store: JobStore,
    engine: OCREngine,
    job_id: str,
    prompt: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Transcribe every page of a job, persisting each page as it completes and yielding events.

    Event shapes (see CLAUDE.md §6): ``page_started`` / ``page_delta`` / ``page_done`` / ``job_done`` /
    ``error``. Each page is saved on completion, so a dropped stream can resume from disk.

    Before touching any page, a lightweight preflight (BE-15) calls ``engine.models()`` — off the
    event loop — so a provider that's down or has nothing loaded fails once, immediately, instead of
    hanging on page 1's own timeout or repeating the same failure page after page.
    """
    prompt = prompt or HANDWRITING_PROMPT
    record = store.set_status(job_id, "running")
    try:
        has_pending_pages = any(not page.done for page in record.pages)
        if has_pending_pages and not await asyncio.to_thread(engine.models):
            store.set_status(job_id, "error")
            yield {"type": "error", "message": _PREFLIGHT_UNREACHABLE_ERROR}
            return
        for page in record.pages:
            if page.done:
                # Already transcribed in a previous run — the client restored it from disk via
                # GET /jobs/{id}. Re-OCRing would waste tokens/GPU and clobber the user's edits.
                continue
            yield {"type": "page_started", "index": page.index}
            image = store.read_image(job_id, page.index)
            chunks: list[str] = []
            async for chunk in engine.transcribe_page(image, prompt):
                chunks.append(chunk)
                yield {"type": "page_delta", "index": page.index, "text": chunk}
            store.save_page_markdown(job_id, page.index, "".join(chunks), done=True)
            yield {"type": "page_done", "index": page.index}
        store.set_status(job_id, "done")
        yield {"type": "job_done"}
    except Exception as exc:  # OCR calls external engines; surface a failure instead of crashing the stream
        # Log the full exception server-side; send the client a named-if-possible message (BE-15).
        logger.exception("OCR failed for job %s", job_id)
        store.set_status(job_id, "error")
        yield {"type": "error", "message": _error_message(exc)}
    finally:
        # If the client disconnected mid-run (Stop, tab close, network drop), GeneratorExit unwinds
        # through here before either terminal branch set a final status — so it's still "running".
        # Reset it to "pending" so the job is resumable (the loop above skips done pages) instead of
        # stuck "running" forever, which would also 409 every future stream (see api/jobs.py).
        if store.load(job_id).status == "running":
            store.set_status(job_id, "pending")
