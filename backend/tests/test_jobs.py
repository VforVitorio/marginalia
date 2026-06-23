"""Job store round-trips on disk; run_ocr streams events and persists page markdown."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from marginalia.ingest.pdf import Notebook, Page
from marginalia.jobs.service import run_ocr
from marginalia.jobs.store import JobStore
from marginalia.ocr.engine import EngineInfo


class _FakeEngine:
    info = EngineInfo(id="fake", display_name="Fake", kind="local", current_model="m")

    def models(self) -> list[str]:
        return ["m"]

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        for chunk in ("Hel", "lo"):
            yield chunk


class _BrokenEngine(_FakeEngine):
    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        raise RuntimeError("engine down")
        yield ""  # unreachable; makes this an async generator


def _notebook() -> Notebook:
    return Notebook(name="nb", source_rel_path="nb.pdf", pages=[Page(index=1, image_png=b"\x89PNGfake")])


def test_store_create_and_load(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    assert store.page_image_path(record.job_id, 1).exists()
    loaded = store.load(record.job_id)
    assert loaded.name == "nb"
    assert loaded.pages[0].markdown == ""


def test_store_rejects_path_traversal_job_id(tmp_path) -> None:
    # job_id comes from the URL and builds a filesystem path — only uuid hex is allowed.
    store = JobStore(root=tmp_path)
    for bad in ("../../etc", "..", "a/b", "nothex"):
        with pytest.raises(ValueError):
            store.load(bad)
        with pytest.raises(ValueError):
            store.page_image_path(bad, 1)


def test_save_page_markdown(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    store.save_page_markdown(record.job_id, 1, "edited", done=True)
    page = store.load(record.job_id).pages[0]
    assert page.markdown == "edited"
    assert page.done is True


def test_save_page_markdown_missing_index_raises(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    with pytest.raises(ValueError, match="Page 99 not found"):
        store.save_page_markdown(record.job_id, 99, "ghost")


async def test_run_ocr_streams_and_persists(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    events = [event async for event in run_ocr(store, _FakeEngine(), record.job_id)]
    assert [event["type"] for event in events] == [
        "page_started",
        "page_delta",
        "page_delta",
        "page_done",
        "job_done",
    ]
    final = store.load(record.job_id)
    assert final.status == "done"
    assert final.pages[0].markdown == "Hello"
    assert final.pages[0].done is True


async def test_run_ocr_reports_engine_failure(tmp_path) -> None:
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    events = [event async for event in run_ocr(store, _BrokenEngine(), record.job_id)]
    assert events[-1]["type"] == "error"
    assert store.load(record.job_id).status == "error"
