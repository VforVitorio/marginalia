"""Job lifecycle endpoints: create, fetch, page image, OCR stream (SSE), edit, export.

Thin router: each route delegates to the ingest / jobs / export services and shapes the response.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from marginalia.api.deps import get_active_engine, get_store
from marginalia.api.schemas import (
    CreateJobOut,
    ExportBody,
    ExportOut,
    JobOut,
    JobPageOut,
    PageEdit,
    ScannedPdfOut,
    ScanOut,
)
from marginalia.api.sse import sse_stream
from marginalia.config import load_settings
from marginalia.export.service import export_notes
from marginalia.ingest.pdf import Notebook, load_notebook, render_pdf
from marginalia.ingest.scan import scan_pdfs
from marginalia.jobs.runner import tail_job
from marginalia.jobs.store import JobRecord, JobStore
from marginalia.ocr.engine import OCREngine
from marginalia.structure.mapper import NoteSource

router = APIRouter()


@router.get("/scan")
def scan() -> ScanOut:
    """List the PDFs under the configured Scribe scan folder, for the synced-folder import flow.

    Feeds the Import step: each entry's ``rel_path`` is what a later ``POST /jobs`` sends back to
    ingest that notebook (and carries the folder hierarchy to export). 400 if no scan folder is set.
    """
    root = _scan_root()
    pdfs = [ScannedPdfOut(rel_path=ref.rel_path, name=PurePosixPath(ref.rel_path).stem) for ref in scan_pdfs(root)]
    return ScanOut(pdfs=pdfs)


@router.post("/jobs")
async def create_job(
    file: UploadFile | None = File(default=None),
    rel_path: str | None = Form(default=None),
    store: JobStore = Depends(get_store),
) -> CreateJobOut:
    """Create a job from an uploaded PDF (``file``) or a scanned one (``rel_path``)."""
    notebook = await _notebook_from_request(file, rel_path)
    # BE-05: store.create writes every page PNG + job.json; off the loop so it can't stall live SSE streams.
    record = await run_in_threadpool(store.create, notebook)
    return CreateJobOut(job_id=record.job_id, name=record.name, pages=len(record.pages))


@router.get("/jobs/{job_id}")
def get_job(job_id: str, store: JobStore = Depends(get_store)) -> JobOut:
    record = _load_or_404(store, job_id)
    return _job_out(record)


@router.get("/jobs/{job_id}/pages/{index}/image")
def get_page_image(job_id: str, index: int, store: JobStore = Depends(get_store)) -> FileResponse:
    _load_or_404(store, job_id)  # validates the job id (it builds a filesystem path) and that the job exists
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
    """Tail a job's OCR: replay whatever's already done, then observe the live run (AR-01).

    This route no longer *triggers* OCR — ``tail_job`` starts (or reuses) the job's background
    runner and only observes it. A second tab opening the same stream attaches to that same
    runner instead of starting a competing OCR pass, and closing this connection only detaches
    the observer: the runner keeps transcribing to disk regardless of who's watching.
    """
    _load_or_404(store, job_id)  # 404 for a missing/invalid job id before opening the stream
    return StreamingResponse(sse_stream(tail_job(store, engine, job_id)), media_type="text/event-stream")


@router.put("/jobs/{job_id}/pages/{index}")
def edit_page(
    job_id: str,
    index: int,
    body: PageEdit,
    store: JobStore = Depends(get_store),
) -> JobPageOut:
    _load_or_404(store, job_id)
    try:
        record = store.save_page_markdown(job_id, index, body.markdown)
    except ValueError:
        raise HTTPException(status_code=404, detail="Page not found.") from None
    page = next(entry for entry in record.pages if entry.index == index)
    return _page_out(job_id, page.index, page.markdown, page.done)


@router.post("/jobs/{job_id}/export")
def export_job(job_id: str, body: ExportBody, store: JobStore = Depends(get_store)) -> ExportOut:
    record = _load_or_404(store, job_id)
    source = _note_source(record, body.target_dir)
    try:
        written = export_notes([source], body.strategies, Path(body.vault_path))
    except ValueError:
        raise HTTPException(status_code=400, detail="Export path escapes the vault.") from None
    return ExportOut(written=[str(path) for path in written])


async def _notebook_from_request(file: UploadFile | None, rel_path: str | None) -> Notebook:
    if file is not None:
        data = await file.read()
        filename = file.filename or "upload.pdf"
        try:
            # BE-05: PyMuPDF rasterizes every page (CPU-bound); off the loop so it can't stall live SSE streams.
            pages = await run_in_threadpool(render_pdf, data)
        # pymupdf raises FileDataError (a RuntimeError) / ValueError on a non-PDF — a client error, not a 500.
        except (ValueError, RuntimeError):
            raise HTTPException(status_code=400, detail="Could not read the PDF.") from None
        # Basename only: a loose upload must never define folders (that's target_dir's job), and a
        # crafted "../" filename must not reach the export path as a traversal.
        return Notebook(name=Path(filename).stem, source_rel_path=Path(filename).name, pages=pages)
    if rel_path:
        root = _scan_root()
        path = _safe_join(root, rel_path)
        # BE-05: load_notebook rasterizes the scanned PDF; off the loop so it can't stall live SSE streams.
        return await run_in_threadpool(load_notebook, path, root)
    raise HTTPException(status_code=400, detail="Provide a file or a rel_path.")


def _scan_root() -> Path:
    settings = load_settings()
    if not settings.scan_folder:
        raise HTTPException(status_code=400, detail="No scan folder configured.")
    return Path(settings.scan_folder)


def _safe_join(root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` under ``root``, rejecting anything that escapes it (path traversal)."""
    target = (root / rel_path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise HTTPException(status_code=400, detail="Path escapes the scan folder.")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="PDF not found.")
    return target


def _note_source(record: JobRecord, target_dir: str = "") -> NoteSource:
    rel = PurePosixPath(record.source_rel_path)
    mirror_dir = "" if str(rel.parent) == "." else str(rel.parent)
    # Scanned notebooks mirror their source folder; loose uploads use the user-chosen target folder.
    source_rel_dir = mirror_dir or target_dir.strip("/")
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
    except (FileNotFoundError, ValueError):  # missing job, or an invalid (path-traversal) job id
        raise HTTPException(status_code=404, detail="Job not found.") from None
