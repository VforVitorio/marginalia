"""On-disk workspace for jobs — the single source of a job's live state.

Each job is a directory ``data/jobs/{id}/`` holding ``job.json`` (state, pages, paths) plus one
``page_{n}.png`` and the edited ``page_{n}.md`` text inside the record per page (docs/ARCHITECTURE.md
§6). No database: files survive restarts and are trivially inspectable.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from marginalia.config import DATA_DIR
from marginalia.ingest.pdf import Notebook


class JobPage(BaseModel):
    """One page of a job: its number, the (editable) transcription, and whether OCR finished it."""

    index: int
    markdown: str = ""
    done: bool = False


class JobRecord(BaseModel):
    """A job's full state, persisted as ``job.json``. The page images live beside it as PNG files."""

    job_id: str
    name: str
    source_rel_path: str
    status: str = "pending"  # pending | running | done | error
    pages: list[JobPage] = Field(default_factory=list)


class JobStore:
    """Reads and writes job workspaces under a root directory (default ``data/jobs``)."""

    def __init__(self, root: Path = DATA_DIR / "jobs") -> None:
        self._root = root

    def create(self, notebook: Notebook) -> JobRecord:
        """Create a job from a rendered notebook: persist the page images and the initial record."""
        job_id = uuid4().hex
        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        for page in notebook.pages:
            (job_dir / f"page_{page.index}.png").write_bytes(page.image_png)
        record = JobRecord(
            job_id=job_id,
            name=notebook.name,
            source_rel_path=notebook.source_rel_path,
            pages=[JobPage(index=page.index) for page in notebook.pages],
        )
        self._write(record)
        return record

    def load(self, job_id: str) -> JobRecord:
        """Read a job's record from disk."""
        return JobRecord.model_validate_json(self._record_path(job_id).read_text(encoding="utf-8"))

    def read_image(self, job_id: str, index: int) -> bytes:
        """Read one page's rendered PNG."""
        return self.page_image_path(job_id, index).read_bytes()

    def page_image_path(self, job_id: str, index: int) -> Path:
        """Filesystem path of a page's PNG (the API serves it as an image)."""
        return self._job_dir(job_id) / f"page_{index}.png"

    def set_status(self, job_id: str, status: str) -> JobRecord:
        """Update and persist a job's status."""
        record = self.load(job_id)
        record.status = status
        self._write(record)
        return record

    def save_page_markdown(self, job_id: str, index: int, markdown: str, done: bool = False) -> JobRecord:
        """Persist a page's transcription (from OCR or from a manual edit in the review UI)."""
        # ponytail: non-atomic load-modify-write; fine for one local user. Add per-job locking if a
        # manual edit ever races OCR's own page save.
        record = self.load(job_id)
        for page in record.pages:
            if page.index == index:
                page.markdown = markdown
                page.done = done or page.done
        self._write(record)
        return record

    def _job_dir(self, job_id: str) -> Path:
        return self._root / job_id

    def _record_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    def _write(self, record: JobRecord) -> None:
        self._record_path(record.job_id).write_text(record.model_dump_json(indent=2), encoding="utf-8")
