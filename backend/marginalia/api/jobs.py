"""Job lifecycle endpoints: create, fetch, page image, OCR stream (SSE), edit, export.

Thin router: each route delegates to the ingest / jobs / export services and shapes the response.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from marginalia.api.deps import get_active_engine, get_store
from marginalia.api.schemas import (
    CreateJobOut,
    ExportBody,
    ExportOut,
    JobOut,
    JobPageOut,
    PageEdit,
)
from marginalia.api.sse import sse_stream
from marginalia.config import load_settings
from marginalia.export.service import export_notes
from marginalia.ingest.pdf import Notebook, load_notebook, render_pdf
from marginalia.jobs.service import run_ocr
from marginalia.jobs.store import JobRecord, JobStore
from marginalia.ocr.engine import OCREngine
from marginalia.structure.mapper import NoteSource, Strategy

router = APIRouter()


@router.post("/jobs")
async def create_job(
    file: UploadFile | None = File(default=None),
    rel_path: str | None = Form(default=None),
    store: JobStore = Depends(get_store),
) -> CreateJobOut:
    """Create a job from an uploaded PDF (``file``) or a scanned one (``rel_path``)."""
    notebook = await _notebook_from_request(file, rel_path)
    record = store.create(notebook)
    return CreateJobOut(job_id=record.job_id, name=record.name, pages=len(record.pages))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, store: JobStore = Depends(get_store)) -> JobOut:
    record = _load_or_404(store, job_id)
    return _job_out(record)


@router.get("/jobs/{job_id}/pages/{index}/image")
def get_page_image(job_id: str, index: int, store: JobStore = Depends(get_store)) -> FileResponse:
    path = store.page_image_path(job_id, index)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Page image not found.")
    return FileResponse(path, media_type="image/png")


@router.get("/jobs/{job_id}/stream")
async def stream_job(
    job_id: str,
    store: JobStore = Depends(get_store),
    engine: OCREngine = Depends(get_active_engine),
) -> StreamingResponse:
    _load_or_404(store, job_id)
    return StreamingResponse(sse_stream(run_ocr(store, engine, job_id)), media_type="text/event-stream")


@router.put("/jobs/{job_id}/pages/{index}")
def edit_page(
    job_id: str,
    index: int,
    body: PageEdit,
    store: JobStore = Depends(get_store),
) -> JobPageOut:
    _load_or_404(store, job_id)
    record = store.save_page_markdown(job_id, index, body.markdown)
    page = next((entry for entry in record.pages if entry.index == index), None)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found.")
    return _page_out(job_id, page.index, page.markdown, page.done)


@router.post("/jobs/{job_id}/export")
def export_job(job_id: str, body: ExportBody, store: JobStore = Depends(get_store)) -> ExportOut:
    record = _load_or_404(store, job_id)
    source = _note_source(record)
    strategies = cast(list[Strategy], body.strategies)
    written = export_notes([source], strategies, Path(body.vault_path))
    return ExportOut(written=[str(path) for path in written])


async def _notebook_from_request(file: UploadFile | None, rel_path: str | None) -> Notebook:
    if file is not None:
        data = await file.read()
        filename = file.filename or "upload.pdf"
        try:
            pages = render_pdf(data)
        except Exception:  # PyMuPDF raises on a non-PDF / corrupt upload — a client error, not a 500
            raise HTTPException(status_code=400, detail="Could not read the PDF.") from None
        return Notebook(name=Path(filename).stem, source_rel_path=filename, pages=pages)
    if rel_path:
        root = _scan_root()
        return load_notebook(_safe_join(root, rel_path), root=root)
    raise HTTPException(status_code=400, detail="Provide a file or a rel_path.")


def _scan_root() -> Path:
    settings = load_settings()
    if not settings.scan_folder:
        raise HTTPException(status_code=400, detail="No scan folder configured.")
    return Path(settings.scan_folder)


def _safe_join(root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` under ``root``, rejecting anything that escapes it (path traversal)."""
    target = (root / rel_path).resolve()
    if root.resolve() not in (target, *target.parents):
        raise HTTPException(status_code=400, detail="Path escapes the scan folder.")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="PDF not found.")
    return target


def _note_source(record: JobRecord) -> NoteSource:
    rel = PurePosixPath(record.source_rel_path)
    source_rel_dir = "" if str(rel.parent) == "." else str(rel.parent)
    return NoteSource(
        name=rel.stem,
        source_rel_dir=source_rel_dir,
        pages_markdown=[page.markdown for page in record.pages],
    )


def _job_out(record: JobRecord) -> JobOut:
    pages = [_page_out(record.job_id, page.index, page.markdown, page.done) for page in record.pages]
    return JobOut(job_id=record.job_id, name=record.name, status=record.status, pages=pages)


def _page_out(job_id: str, index: int, markdown: str, done: bool) -> JobPageOut:
    return JobPageOut(
        index=index,
        image_url=f"/api/jobs/{job_id}/pages/{index}/image",
        markdown=markdown,
        done=done,
    )


def _load_or_404(store: JobStore, job_id: str) -> JobRecord:
    try:
        return store.load(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found.") from None
