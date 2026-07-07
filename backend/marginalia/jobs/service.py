"""Orchestrate ingest → OCR per page, persist results, and emit SSE events.

This is the ONLY place that wires the OCR engine, the job store, and the event stream together
(docs/ARCHITECTURE.md §10). Events are plain dicts; the API layer serializes them as SSE.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from marginalia.jobs.store import JobStore
from marginalia.ocr.engine import OCREngine
from marginalia.ocr.prompts import HANDWRITING_PROMPT

logger = logging.getLogger(__name__)


async def run_ocr(
    store: JobStore,
    engine: OCREngine,
    job_id: str,
    prompt: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Transcribe every page of a job, persisting each page as it completes and yielding events.

    Event shapes (see CLAUDE.md §6): ``page_started`` / ``page_delta`` / ``page_done`` / ``job_done`` /
    ``error``. Each page is saved on completion, so a dropped stream can resume from disk.
    """
    prompt = prompt or HANDWRITING_PROMPT
    record = store.set_status(job_id, "running")
    try:
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
    except Exception:  # OCR calls external engines; surface a failure instead of crashing the stream
        # Log the full exception server-side; send the client a generic message (don't leak internals).
        logger.exception("OCR failed for job %s", job_id)
        store.set_status(job_id, "error")
        yield {"type": "error", "message": "OCR failed — check the selected provider and model, then try again."}
    finally:
        # If the client disconnected mid-run (Stop, tab close, network drop), GeneratorExit unwinds
        # through here before either terminal branch set a final status — so it's still "running".
        # Reset it to "pending" so the job is resumable (the loop above skips done pages) instead of
        # stuck "running" forever, which would also 409 every future stream (see api/jobs.py).
        if store.load(job_id).status == "running":
            store.set_status(job_id, "pending")
