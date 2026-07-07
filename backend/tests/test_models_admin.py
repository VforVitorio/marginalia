"""``models_admin`` tests: ``runtime_status`` honesty guards (BE-21) and ``pull_model`` streaming (#138)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from marginalia.config import CLOUD_MODELS, ProviderConfig
from marginalia.models_admin import cloud_models, pull_model, runtime_status

# ── runtime_status: no base_url must never mean "ready" (BE-21) ──────────────


def test_claude_with_no_base_url_is_reachable() -> None:
    """Claude has no HTTP runtime to probe — presence of a default_model is enough (see claude_auth)."""
    claude = ProviderConfig(id="claude", display_name="Claude", kind="cloud", default_model="claude-sonnet-4-6")
    reachable, models = runtime_status(claude)
    assert reachable is True
    assert models == ["claude-sonnet-4-6"]


def test_misconfigured_local_provider_with_no_base_url_is_not_ready() -> None:
    """BE-21: a non-Claude entry with a missing base_url is broken config, not a healthy provider."""
    broken = ProviderConfig(id="ollama", display_name="Ollama", kind="local", base_url=None)
    assert runtime_status(broken) == (False, [])


def test_misconfigured_cloud_provider_with_no_base_url_is_not_ready() -> None:
    """Same guard for a cloud (non-Claude) entry missing its base_url."""
    broken = ProviderConfig(id="gemini", display_name="Gemini", kind="cloud", base_url=None)
    assert runtime_status(broken) == (False, [])


# ── cloud_models: curated list wins, probe is the fallback (#148) ────────────


def test_cloud_models_prefers_curated_list_over_probe() -> None:
    gemini = ProviderConfig(id="gemini", display_name="Gemini", kind="cloud", base_url="https://x/v1")
    assert cloud_models(gemini, probed=["some-probed-model"]) == CLOUD_MODELS["gemini"]


def test_cloud_models_falls_back_to_probe_when_uncurated() -> None:
    other = ProviderConfig(id="other-cloud", display_name="Other", kind="cloud", base_url="https://x/v1")
    assert cloud_models(other, probed=["model-a", "model-b"]) == ["model-a", "model-b"]


def test_cloud_models_falls_back_to_empty_when_uncurated_and_unprobed() -> None:
    other = ProviderConfig(id="other-cloud", display_name="Other", kind="cloud", base_url="https://x/v1")
    assert cloud_models(other, probed=[]) == []


# ── pull_model: stream Ollama NDJSON progress and surface failures (#138) ────


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
