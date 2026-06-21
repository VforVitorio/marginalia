"""Ingest checks: a PDF renders to PNG pages and a folder scan keeps relative paths."""

from __future__ import annotations

import pymupdf

from marginalia.ingest.pdf import load_notebook, render_pdf
from marginalia.ingest.scan import scan_pdfs

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _one_page_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_render_pdf_yields_png_pages() -> None:
    pages = render_pdf(_one_page_pdf(), dpi=72)
    assert len(pages) == 1
    assert pages[0].index == 1
    assert pages[0].image_png.startswith(_PNG_SIGNATURE)


def test_scan_pdfs_preserves_relative_path(tmp_path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.pdf").write_bytes(_one_page_pdf())
    (tmp_path / "b.pdf").write_bytes(_one_page_pdf())
    rel_paths = [ref.rel_path for ref in scan_pdfs(tmp_path)]
    assert rel_paths == ["b.pdf", "sub/a.pdf"]  # sorted by relative path


def test_scan_pdfs_missing_root_is_empty(tmp_path) -> None:
    assert scan_pdfs(tmp_path / "nope") == []


def test_load_notebook_keeps_source_path(tmp_path) -> None:
    (tmp_path / "sub").mkdir()
    pdf_path = tmp_path / "sub" / "notes.pdf"
    pdf_path.write_bytes(_one_page_pdf())
    notebook = load_notebook(pdf_path, root=tmp_path, dpi=72)
    assert notebook.name == "notes"
    assert notebook.source_rel_path == "sub/notes.pdf"
    assert len(notebook.pages) == 1
