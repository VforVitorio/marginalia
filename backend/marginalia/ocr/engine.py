"""The ``OCREngine`` contract: the seam that makes OCR backends interchangeable.

An engine takes one image and a prompt and streams text. It knows nothing about jobs, SSE, the vault,
or FastAPI (see docs/ARCHITECTURE.md §2). Breaking that ignorance breaks the testability of the whole
system: the orchestrator (``jobs/service.py``) is the only place that knows about pages and persistence.

--- WHERE TO CHANGE IF X CHANGES ---
- New OCR backend: implement this Protocol and register it in ``ocr/registry.py``.
- Change the streaming shape: here and in whoever consumes ``transcribe_page`` (``jobs/service.py``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

EngineKind = Literal["local", "cloud"]


@dataclass(frozen=True)
class EngineInfo:
    """Metadata for an OCR backend, used to display and select it in the UI."""

    id: str
    display_name: str
    kind: EngineKind
    current_model: str | None = None


@runtime_checkable
class OCREngine(Protocol):
    """Interchangeable OCR backend. Image -> streamed text, nothing else."""

    info: EngineInfo

    def models(self) -> list[str]:
        """Models available on this backend (empty list if they can't be queried)."""
        ...

    def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        """Stream the transcription of one page as text chunks."""
        ...
