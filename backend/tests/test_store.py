"""Durable-persistence coverage for jobs/store.py: list/delete and atomic writes (#143).

Covers BE-13 (jobs are immortal: no list, no delete, no cleanup) and the job.json half of BE-12
(atomic writes). test_jobs.py already covers create/load/save_page_markdown/path-traversal; this
file is additive, not a replacement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from marginalia.ingest.pdf import Notebook, Page
from marginalia.jobs.store import JobStore


def _notebook(name: str = "nb") -> Notebook:
    return Notebook(name=name, source_rel_path=f"{name}.pdf", pages=[Page(index=1, image_png=b"\x89PNGfake")])


def test_list_jobs_empty_when_root_missing(tmp_path) -> None:
    store = JobStore(root=tmp_path / "jobs")  # root directory never created
    assert store.list_jobs() == []


def test_list_jobs_returns_every_created_job(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    first = store.create(_notebook("first"))
    second = store.create(_notebook("second"))
    listed_ids = {record.job_id for record in store.list_jobs()}
    assert listed_ids == {first.job_id, second.job_id}


def test_list_jobs_skips_directory_with_missing_job_json(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    good = store.create(_notebook("good"))
    bad_dir = tmp_path / ("a" * 32)  # valid uuid4-hex shape, but empty — no job.json inside
    bad_dir.mkdir()
    records = store.list_jobs()
    assert [record.job_id for record in records] == [good.job_id]


def test_list_jobs_skips_corrupt_job_json(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    good = store.create(_notebook("good"))
    bad_dir = tmp_path / ("b" * 32)
    bad_dir.mkdir()
    (bad_dir / "job.json").write_text("not valid json", encoding="utf-8")
    records = store.list_jobs()
    assert [record.job_id for record in records] == [good.job_id]


def test_list_jobs_ignores_non_job_entries(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    good = store.create(_notebook("good"))
    (tmp_path / "not-a-job-id").mkdir()
    (tmp_path / "stray-file.txt").write_text("noise", encoding="utf-8")
    records = store.list_jobs()
    assert [record.job_id for record in records] == [good.job_id]


def test_delete_removes_job_directory(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    assert store.delete(record.job_id) is True
    assert not (tmp_path / record.job_id).exists()
    with pytest.raises(FileNotFoundError):
        store.load(record.job_id)


def test_delete_removed_job_is_absent_from_list(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    keep = store.create(_notebook("keep"))
    gone = store.create(_notebook("gone"))
    store.delete(gone.job_id)
    assert [record.job_id for record in store.list_jobs()] == [keep.job_id]


def test_delete_is_idempotent_for_missing_job(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    assert store.delete("a" * 32) is False


def test_delete_rejects_path_traversal_job_id(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    for bad in ("../../etc", "..", "a/b", "nothex"):
        with pytest.raises(ValueError):
            store.delete(bad)


def test_write_atomic_preserves_job_json_on_failed_save(tmp_path, monkeypatch) -> None:
    """A crash mid-write while saving a page must not corrupt the still-readable job.json (BE-12)."""
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    job_json_tmp = tmp_path / record.job_id / "job.json.tmp"

    original_write_text = Path.write_text

    def _boom(self: Path, *args: object, **kwargs: object) -> int:
        if self == job_json_tmp:
            raise OSError("disk full")
        return original_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", _boom)

    with pytest.raises(OSError, match="disk full"):
        store.save_page_markdown(record.job_id, 1, "won't be saved")

    monkeypatch.undo()
    reloaded = store.load(record.job_id)
    assert reloaded.pages[0].markdown == ""  # original content survived the failed write
    assert reloaded.pages[0].done is False
