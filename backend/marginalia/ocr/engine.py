"""El contrato ``OCREngine``: el seam que hace los backends de OCR intercambiables.

Un engine recibe una imagen y un prompt y streamea texto. No conoce jobs, SSE, vault ni FastAPI
(ver docs/ARCHITECTURE.md §2). Romper esa ignorancia rompe la testabilidad de todo el sistema:
el orquestador (``jobs/service.py``) es el único que sabe de páginas y persistencia.

--- WHERE TO CHANGE IF X CHANGES ---
- Nuevo backend OCR: implementa este Protocol y regístralo en ``ocr/registry.py``.
- Cambia la forma del streaming: aquí y en quien consuma ``transcribe_page`` (``jobs/service.py``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

EngineKind = Literal["local", "cloud"]


@dataclass(frozen=True)
class EngineInfo:
    """Metadatos de un backend OCR, para mostrarlo y seleccionarlo en la UI."""

    id: str
    display_name: str
    kind: EngineKind
    current_model: str | None = None


@runtime_checkable
class OCREngine(Protocol):
    """Backend de OCR intercambiable. Imagen -> texto streameado, nada más."""

    info: EngineInfo

    def models(self) -> list[str]:
        """Modelos disponibles en este backend (lista vacía si no se pueden consultar)."""
        ...

    def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        """Streamea la transcripción de una página como trozos de texto."""
        ...
