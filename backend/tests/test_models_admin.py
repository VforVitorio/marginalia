"""``pull_model`` streams Ollama's NDJSON pull progress and surfaces failures (issue #138)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from marginalia.config import ProviderConfig
from marginalia.models_admin import pull_model


def _provider() -> ProviderConfig:
    return ProviderConfig(id="ollama", display_name="Ollama", kind="local", base_url="http://localhost:11434/v1")


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    """Force every ``httpx.AsyncClient`` built inside ``pull_model`` onto a mock transport."""
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self: httpx.AsyncClient, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_pull_model_forwards_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    ndjson = '{"status": "pulling manifest"}\n{"status": "downloading", "total": 100, "completed": 50}\n'
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, content=ndjson))

    events = [event async for event in pull_model(_provider(), "qwen3-vl:4b")]

    assert events == [
        {"type": "pull_progress", "status": "pulling manifest", "percent": None},
        {"type": "pull_progress", "status": "downloading", "percent": 50},
    ]


async def test_pull_model_propagates_ollama_error_line(monkeypatch: pytest.MonkeyPatch) -> None:
    ndjson = '{"status": "pulling manifest"}\n{"error": "model \'bogus\' not found"}\n'
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, content=ndjson))

    events = [event async for event in pull_model(_provider(), "bogus")]

    assert events == [
        {"type": "pull_progress", "status": "pulling manifest", "percent": None},
        {"type": "error", "message": "model 'bogus' not found"},
    ]


async def test_pull_model_reports_http_status_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda request: httpx.Response(500, content=b"internal error"))

    events = [event async for event in pull_model(_provider(), "qwen3-vl:4b")]

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "qwen3-vl:4b" in events[0]["message"]


async def test_pull_model_reports_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_transport(monkeypatch, handler)

    events = [event async for event in pull_model(_provider(), "qwen3-vl:4b")]

    assert len(events) == 1
    assert events[0]["type"] == "error"
