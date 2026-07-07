"""``runtime_status``'s honesty guards (BE-21): no base_url must never mean "ready"."""

from __future__ import annotations

from marginalia.config import ProviderConfig
from marginalia.models_admin import runtime_status


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
