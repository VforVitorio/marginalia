"""Orchestrate ingest → OCR per page, persist results, and emit SSE events.

This is the ONLY place that wires the OCR engine, the job store, and the event stream together
(docs/ARCHITECTURE.md §10). Events are plain dicts; the API layer serializes them as SSE.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from marginalia.jobs.store import JobStore
from marginalia.ocr.engine import OCREngine
from marginalia.ocr.prompts import handwriting_prompt

logger = logging.getLogger(__name__)


async def run_ocr(
    store: JobStore,
    engine: OCREngine,
    job_id: str,
    prompt: str | None = None,
) -> AsyncIterator[dict]:
    """Transcribe every page of a job, persisting each page as it completes and yielding events.

    Event shapes (see CLAUDE.md §6): ``page_started`` / ``page_delta`` / ``page_done`` / ``job_done`` /
    ``error``. Each page is saved on completion, so a dropped stream can resume from disk.
    """
    prompt = prompt or handwriting_prompt()
    record = store.set_status(job_id, "running")
    try:
        for page in record.pages:
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
    except Exception as exc:  # OCR calls external engines; surface any failure instead of crashing the stream
        logger.exception("OCR failed for job %s", job_id)
        store.set_status(job_id, "error")
        yield {"type": "error", "message": str(exc)}
