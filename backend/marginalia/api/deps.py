"""FastAPI dependencies: the shared job store and the active OCR engine.

These are the seams the tests override (e.g. a fake engine for the SSE stream).
"""

from __future__ import annotations

from marginalia.jobs.store import JobStore
from marginalia.ocr.engine import OCREngine
from marginalia.ocr.registry import active_engine

_store = JobStore()


def get_store() -> JobStore:
    """The process-wide job store (workspace under ``data/jobs``)."""
    return _store


def get_active_engine() -> OCREngine:
    """Build the engine the user has selected (from settings + providers)."""
    return active_engine()
