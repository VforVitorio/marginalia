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
from marginalia.jobs.runner import get_runner, tail_job
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


class _CountingEngine(_FakeEngine):
    """Counts ``transcribe_page`` calls, to prove already-done pages are skipped on resume (BE-03)."""

    def __init__(self) -> None:
        self.call_count = 0

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        self.call_count += 1
        for chunk in ("Hel", "lo"):
            yield chunk


class _CountingDelayedEngine(_CountingEngine):
    """Like ``_CountingEngine``, but with a real ``await`` between chunks (AR-01 runner tests).

    A fully synchronous fake never yields control back to the event loop mid-page, so a test
    couldn't reliably observe the runner "mid-flight" (e.g. to disconnect, or to attach a second
    subscriber, before it finishes). The sleep is short enough to keep tests fast.
    """

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        self.call_count += 1
        for chunk in ("Hel", "lo"):
            await asyncio.sleep(0.01)
            yield chunk


def _notebook() -> Notebook:
    return Notebook(name="nb", source_rel_path="nb.pdf", pages=[Page(index=1, image_png=b"\x89PNGfake")])


def _two_page_notebook() -> Notebook:
    return Notebook(
        name="nb",
        source_rel_path="nb.pdf",
        pages=[Page(index=1, image_png=b"\x89PNGfake1"), Page(index=2, image_png=b"\x89PNGfake2")],
    )


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


async def test_run_ocr_resume_skips_already_done_pages_without_re_ocring(tmp_path) -> None:
    """BE-03: a re-stream (Stop, drop, refresh) must resume from the first undone page, not re-OCR."""
    store = JobStore(root=tmp_path)
    record = store.create(_two_page_notebook())
    store.save_page_markdown(record.job_id, 1, "already transcribed", done=True)

    engine = _CountingEngine()
    events = [event async for event in run_ocr(store, engine, record.job_id)]

    assert engine.call_count == 1  # only the undone page (2) was sent to the engine
    assert [event["type"] for event in events] == [
        "page_started",
        "page_delta",
        "page_delta",
        "page_done",
        "job_done",
    ]
    assert events[0]["index"] == 2  # resumes at page 2, page 1 is not replayed or re-started

    final = store.load(record.job_id)
    assert final.pages[0].markdown == "already transcribed"  # untouched
    assert final.pages[1].markdown == "Hello"
    assert final.status == "done"


async def test_run_ocr_disconnect_resets_status_to_pending_not_stuck_running(tmp_path) -> None:
    """BE-02: if ``run_ocr``'s own generator is ever closed mid-run, the job must stay resumable,
    not stuck ``running`` forever. Since AR-01 (jobs/runner.py), a client's SSE tab closing no
    longer reaches this path at all — it only unsubscribes from the runner, which keeps OCRing
    (see test_runner_keeps_ocring_after_its_only_subscriber_disconnects below). This safety net
    still matters for a true cancellation of the runner's background task (e.g. app shutdown)."""
    store = JobStore(root=tmp_path)
    record = store.create(_two_page_notebook())

    generator = run_ocr(store, _FakeEngine(), record.job_id)
    await generator.__anext__()  # consume "page_started" for page 1 — job.json now says "running"
    assert store.load(record.job_id).status == "running"

    await generator.aclose()  # simulates the generator being cancelled out from under run_ocr

    assert store.load(record.job_id).status == "pending"


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


async def test_runner_keeps_ocring_after_its_only_subscriber_disconnects(tmp_path) -> None:
    """AR-01: closing the SSE tab must not stop the OCR — only ``tail_job`` should notice."""
    store = JobStore(root=tmp_path)
    record = store.create(_two_page_notebook())
    engine = _CountingDelayedEngine()

    generator = tail_job(store, engine, record.job_id)
    first_event = await generator.__anext__()
    assert first_event == {"type": "page_started", "index": 1}

    await generator.aclose()  # simulates Starlette closing the generator on client disconnect

    state = get_runner(record.job_id)
    assert state is not None, "the runner must still be alive after its only subscriber left"
    await state.task  # wait for the background OCR to finish on its own, unattended

    final = store.load(record.job_id)
    assert final.status == "done"
    assert final.pages[0].done is True
    assert final.pages[0].markdown == "Hello"
    assert final.pages[1].done is True
    assert final.pages[1].markdown == "Hello"


async def test_second_concurrent_stream_tails_without_a_second_ocr_run(tmp_path) -> None:
    """AR-01: two tabs on the same job share one runner — replaces the old 409-on-double-stream."""
    store = JobStore(root=tmp_path)
    record = store.create(_two_page_notebook())
    engine = _CountingDelayedEngine()

    async def _drain(generator: AsyncIterator[dict]) -> list[dict]:
        return [event async for event in generator]

    stream_a = tail_job(store, engine, record.job_id)
    first_event = await stream_a.__anext__()  # tab A opens the stream, starting the one runner
    assert first_event["type"] == "page_started"

    stream_b = tail_job(store, engine, record.job_id)  # tab B opens the SAME job mid-run

    events_a, events_b = await asyncio.gather(_drain(stream_a), _drain(stream_b))
    events_a = [first_event, *events_a]

    assert engine.call_count == 2  # exactly one transcribe_page call per page — never doubled
    assert events_a[-1]["type"] == "job_done"
    assert events_b[-1]["type"] == "job_done"
    final = store.load(record.job_id)
    assert final.status == "done"
    assert [page.markdown for page in final.pages] == ["Hello", "Hello"]


async def test_tail_job_resumes_via_the_runner_without_re_ocring_done_pages(tmp_path) -> None:
    """BE-03 still holds through the runner: a fresh tail replays the done page from disk and
    only sends the undone page to the engine."""
    store = JobStore(root=tmp_path)
    record = store.create(_two_page_notebook())
    store.save_page_markdown(record.job_id, 1, "already transcribed", done=True)
    engine = _CountingEngine()

    events = [event async for event in tail_job(store, engine, record.job_id)]

    assert engine.call_count == 1  # only page 2 (undone) was sent to the engine
    # page 1 is replayed from disk, verbatim, before anything live arrives
    assert events[0] == {"type": "page_started", "index": 1}
    assert events[1] == {"type": "page_delta", "index": 1, "text": "already transcribed"}
    assert events[2] == {"type": "page_done", "index": 1}
    assert events[-1]["type"] == "job_done"
    final = store.load(record.job_id)
    assert final.pages[0].markdown == "already transcribed"  # untouched by the replay
    assert final.pages[1].markdown == "Hello"
    assert final.status == "done"


def test_openai_compat_engine_splits_connect_from_read_timeout() -> None:
    """BE-09: connect must fail fast even when the read budget stays generous for slow generation."""
    engine = OpenAICompatEngine(id="x", display_name="X", kind="local", base_url="http://h/v1", model="m", timeout=45.0)
    assert engine._timeout.connect == 5.0
    assert engine._timeout.read == 45.0
