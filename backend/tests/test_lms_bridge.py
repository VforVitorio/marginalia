"""LM Studio bridge (#44): JSON parsing + graceful degradation when ``lms`` is absent."""

from __future__ import annotations

import marginalia.lms_bridge as bridge


def test_identifiers_extracts_ids_and_skips_noise() -> None:
    raw = [
        {"identifier": "gemma-4-e2b"},
        {"modelKey": "qwen3-vl-2b"},  # ls --json uses modelKey
        {"path": "/models/minicpm.gguf"},  # fallback to path
        {"other": "ignored"},  # no usable key
        "not-a-dict",  # skipped
    ]
    assert bridge._identifiers(raw) == ["gemma-4-e2b", "qwen3-vl-2b", "/models/minicpm.gguf"]


def test_identifiers_handles_non_list() -> None:
    assert bridge._identifiers(None) == []
    assert bridge._identifiers({"identifier": "x"}) == []


def test_graceful_when_lms_missing(monkeypatch) -> None:
    monkeypatch.setattr(bridge.shutil, "which", lambda _: None)
    assert bridge.lms_available() is False
    assert bridge.load_model("any") is False
    assert bridge.unload_model("any") is False
    assert bridge.unload_model(all_models=True) is False
    assert bridge.loaded_model_ids() == []
    assert bridge.downloaded_model_ids() == []


def test_unload_needs_a_target(monkeypatch) -> None:
    monkeypatch.setattr(bridge.shutil, "which", lambda _: "/usr/bin/lms")
    # No identifier and not all_models → refuse without shelling out.
    assert bridge.unload_model() is False


def test_is_server_up_false_for_closed_port() -> None:
    # Port 0 is never listening; probe must fail fast, not raise.
    assert bridge.is_server_up(port=0) is False


def test_ensure_server_up_returns_true_when_already_reachable(monkeypatch) -> None:
    monkeypatch.setattr(bridge, "is_server_up", lambda *a, **k: True)
    called = False

    def _fail(*_a, **_k) -> bool:
        nonlocal called
        called = True
        return False

    monkeypatch.setattr(bridge, "_run_ok", _fail)
    assert bridge.ensure_server_up() is True
    assert called is False  # short-circuited — never shelled out
