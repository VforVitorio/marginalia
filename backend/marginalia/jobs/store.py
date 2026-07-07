"""On-disk workspace for jobs — the single source of a job's live state.

Each job is a directory ``data/jobs/{id}/`` holding ``job.json`` (state, pages, paths) plus one
``page_{n}.png`` and the edited ``page_{n}.md`` text inside the record per page (docs/ARCHITECTURE.md
§6). No database: files survive restarts and are trivially inspectable.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from marginalia.config import DATA_DIR, write_text_atomic
from marginalia.ingest.pdf import Notebook

# job_id reaches the filesystem from the URL, so it must be exactly the shape create() produces
# (uuid4().hex). Anything else (path separators, "..", absolute paths) is rejected — path-traversal guard.
_JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _validate_job_id(job_id: str) -> str:
    if not _JOB_ID_RE.fullmatch(job_id):
        raise ValueError(f"Invalid job id: {job_id!r}")
    return job_id


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
    status: Literal["pending", "running", "done", "error"] = "pending"
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

    def list_jobs(self) -> list[JobRecord]:
        """List every job record under the root directory (BE-13).

        Lets a job be rediscovered after a browser refresh, since today the id lives only in
        frontend memory. A directory that isn't a valid job (bad id shape, missing/corrupt
        ``job.json``) is skipped rather than raising, so one broken job doesn't break the whole
        listing. Ordering is by directory name (uuid4 hex — not chronological); callers that need
        recency should sort by a field on the record.
        """
        if not self._root.is_dir():
            return []
        records: list[JobRecord] = []
        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir() or not _JOB_ID_RE.fullmatch(entry.name):
                continue
            try:
                records.append(self.load(entry.name))
            except (OSError, ValueError):
                continue
        return records

    def delete(self, job_id: str) -> bool:
        """Delete a job's entire workspace directory: ``job.json`` and every page PNG (BE-13).

        Keeps ``data/jobs/`` from growing unbounded (each job holds full-resolution page images).
        Returns ``True`` if the job existed and was removed, ``False`` if there was nothing to
        delete — idempotent, so callers can retry without checking existence first.
        """
        job_dir = self._job_dir(job_id)
        if not job_dir.is_dir():
            return False
        shutil.rmtree(job_dir)
        return True

    def read_image(self, job_id: str, index: int) -> bytes:
        """Read one page's rendered PNG."""
        return self.page_image_path(job_id, index).read_bytes()

    def page_image_path(self, job_id: str, index: int) -> Path:
        """Filesystem path of a page's PNG (the API serves it as an image)."""
        return self._job_dir(job_id) / f"page_{index}.png"

    def set_status(self, job_id: str, status: Literal["pending", "running", "done", "error"]) -> JobRecord:
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
        raise ValueError(f"Page {index} not found in job {job_id}")

    def _job_dir(self, job_id: str) -> Path:
        return self._root / _validate_job_id(job_id)

    def _record_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    def _write(self, record: JobRecord) -> None:
        write_text_atomic(self._record_path(record.job_id), record.model_dump_json(indent=2))
