"""Render a Scribe PDF into per-page PNG images with PyMuPDF.

This module knows nothing about OCR or the vault (see docs/ARCHITECTURE.md §10): it only turns bytes
into images. A ``Notebook`` is one PDF; its folder context (``source_rel_path``) is what the export's
``StructureMapper`` later projects into Obsidian.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

_PDF_POINTS_PER_INCH = 72  # PDF user-space unit; zoom = dpi / 72 to rasterize at a target DPI


@dataclass(frozen=True)
class Page:
    """One rendered page. ``index`` is 1-based to match how humans count pages."""

    index: int
    image_png: bytes


@dataclass
class Notebook:
    """A single PDF turned into pages, plus where it came from."""

    name: str
    source_rel_path: str  # POSIX path relative to the scanned root, or just the filename for drag & drop
    pages: list[Page]


def render_pdf(data: bytes, dpi: int = 200) -> list[Page]:
    """Rasterize every page of a PDF (given as bytes) to a PNG at the requested DPI."""
    zoom = dpi / _PDF_POINTS_PER_INCH
    matrix = pymupdf.Matrix(zoom, zoom)
    pages: list[Page] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for index, page in enumerate(doc, start=1):
            pixmap = page.get_pixmap(matrix=matrix)
            pages.append(Page(index=index, image_png=pixmap.tobytes("png")))
    return pages


def load_notebook(pdf_path: Path, root: Path | None = None, dpi: int = 200) -> Notebook:
    """Read a PDF file and render it into a ``Notebook``.

    ``root`` is the scanned folder: when given, ``source_rel_path`` is the path relative to it (so the
    folder hierarchy survives to export); otherwise it's just the filename (loose drag & drop).
    """
    rel_path = pdf_path.relative_to(root).as_posix() if root else pdf_path.name
    pages = render_pdf(pdf_path.read_bytes(), dpi=dpi)
    return Notebook(name=pdf_path.stem, source_rel_path=rel_path, pages=pages)
