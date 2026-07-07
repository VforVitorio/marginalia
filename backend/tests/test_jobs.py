"""Job store round-trips on disk; run_ocr streams events and persists page markdown.

Also covers the stream-robustness trio (BE-08/09/10): SSE heartbeats (``api/sse.py``), the per-page
OCR timeout (``jobs/service.py``), and ``OpenAICompatEngine``'s split connect/read timeout.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest

from marginalia.api.sse import sse_stream
from marginalia.ingest.pdf import Notebook, Page
from marginalia.jobs.service import run_ocr
from marginalia.jobs.store import JobStore
from marginalia.ocr.engine import EngineInfo
from marginalia.ocr.openai_compat import OpenAICompatEngine


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


class _UnreachableEngine(_FakeEngine):
    """A provider whose preflight probe (``models()``) finds nothing — down, or no model loaded."""

    def models(self) -> list[str]:
        return []

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        raise AssertionError("transcribe_page must not run once the preflight fails")
        yield ""  # unreachable; makes this an async generator


def _raise(exc: Exception) -> AsyncIterator[str]:
    async def _gen() -> AsyncIterator[str]:
        raise exc
        yield ""  # unreachable; makes this an async generator

    return _gen()


class _ConnectErrorEngine(_FakeEngine):
    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        async for chunk in _raise(httpx.ConnectError("refused")):
            yield chunk


class _UnauthorizedEngine(_FakeEngine):
    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        request = httpx.Request("POST", "https://example.com/chat/completions")
        response = httpx.Response(401, request=request)
        async for chunk in _raise(httpx.HTTPStatusError("unauthorized", request=request, response=response)):
            yield chunk


class _NotFoundEngine(_FakeEngine):
    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        request = httpx.Request("POST", "https://example.com/chat/completions")
        response = httpx.Response(404, request=request)
        async for chunk in _raise(httpx.HTTPStatusError("not found", request=request, response=response)):
            yield chunk


class _TimeoutEngine(_FakeEngine):
    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        async for chunk in _raise(httpx.ReadTimeout("timed out")):
            yield chunk


class _HangingEngine(_FakeEngine):
    """A provider whose ``transcribe_page`` never completes — a wedged runtime or subprocess (BE-10)."""

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        await asyncio.sleep(999)
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


async def test_run_ocr_preflight_fails_fast_without_touching_pages(tmp_path) -> None:
    """BE-15: an unreachable provider is reported once, before any page_started/transcribe_page."""
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    events = [event async for event in run_ocr(store, _UnreachableEngine(), record.job_id)]
    assert [event["type"] for event in events] == ["error"]
    assert "reach" in events[0]["message"].lower()
    assert store.load(record.job_id).status == "error"


async def test_run_ocr_skips_preflight_when_all_pages_already_done(tmp_path) -> None:
    """A re-stream of a finished job must not touch the network at all — nothing left to OCR."""
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    store.save_page_markdown(record.job_id, 1, "already transcribed", done=True)
    events = [event async for event in run_ocr(store, _UnreachableEngine(), record.job_id)]
    assert [event["type"] for event in events] == ["job_done"]
    assert store.load(record.job_id).status == "done"


@pytest.mark.parametrize(
    ("engine_cls", "expected_snippet"),
    [
        (_ConnectErrorEngine, "can't reach"),
        (_UnauthorizedEngine, "rejected the api key"),
        (_NotFoundEngine, "isn't available"),
        (_TimeoutEngine, "didn't respond in time"),
    ],
)
async def test_run_ocr_names_the_failure_class(tmp_path, engine_cls, expected_snippet) -> None:
    """BE-15: known httpx failure classes get an actionable message, not the generic fallback."""
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    events = [event async for event in run_ocr(store, engine_cls(), record.job_id)]
    assert events[-1]["type"] == "error"
    assert expected_snippet in events[-1]["message"].lower()


async def test_run_ocr_page_timeout_fails_the_page_instead_of_hanging_forever(tmp_path) -> None:
    """BE-10: a hung engine must not hang the job (and the SSE stream) forever."""
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    events = [event async for event in run_ocr(store, _HangingEngine(), record.job_id, page_timeout=0.05)]
    assert events[-1]["type"] == "error"
    assert "didn't respond in time" in events[-1]["message"].lower()
    assert store.load(record.job_id).status == "error"


async def test_run_ocr_page_timeout_does_not_trip_on_a_merely_slow_page(tmp_path) -> None:
    """A page that finishes comfortably inside the timeout must transcribe normally."""
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    events = [event async for event in run_ocr(store, _FakeEngine(), record.job_id, page_timeout=5.0)]
    assert events[-1]["type"] == "job_done"
    assert store.load(record.job_id).status == "done"


async def test_sse_stream_emits_heartbeats_during_a_quiet_gap_without_losing_events() -> None:
    """BE-08: a slow producer gets ``: keep-alive`` comments interleaved, but no event is dropped."""

    async def _slow_events() -> AsyncIterator[dict]:
        yield {"type": "a"}
        await asyncio.sleep(0.05)
        yield {"type": "b"}

    frames = [frame async for frame in sse_stream(_slow_events(), heartbeat_interval=0.01)]
    assert frames[0] == 'data: {"type": "a"}\n\n'
    assert frames[-1] == 'data: {"type": "b"}\n\n'
    assert frames.count(": keep-alive\n\n") >= 1


async def test_sse_stream_survives_run_ocr_end_to_end_with_heartbeats(tmp_path) -> None:
    """BE-08 + BE-10 together: heartbeats during a page timeout must not swallow the final error."""
    store = JobStore(root=tmp_path)
    record = store.create(_notebook())
    events_iter = run_ocr(store, _HangingEngine(), record.job_id, page_timeout=0.05)
    frames = [frame async for frame in sse_stream(events_iter, heartbeat_interval=0.01)]
    assert any(frame == ": keep-alive\n\n" for frame in frames)
    assert '"type": "error"' in frames[-1]
    assert store.load(record.job_id).status == "error"


def test_openai_compat_engine_splits_connect_from_read_timeout() -> None:
    """BE-09: connect must fail fast even when the read budget stays generous for slow generation."""
    engine = OpenAICompatEngine(id="x", display_name="X", kind="local", base_url="http://h/v1", model="m", timeout=45.0)
    assert engine._timeout.connect == 5.0
    assert engine._timeout.read == 45.0
