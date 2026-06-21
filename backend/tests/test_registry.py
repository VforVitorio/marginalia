"""``build_engine`` elige el adapter correcto según el proveedor."""

import pytest
from marginalia.config import ProviderConfig
from marginalia.ocr.agent_sdk import AgentSDKEngine
from marginalia.ocr.openai_compat import OpenAICompatEngine
from marginalia.ocr.registry import build_engine


def test_openai_compat_for_local_provider() -> None:
    provider = ProviderConfig(
        id="ollama",
        display_name="Ollama",
        kind="local",
        base_url="http://localhost:11434/v1",
        default_model="qwen3-vl:4b",
    )
    engine = build_engine(provider)
    assert isinstance(engine, OpenAICompatEngine)
    assert engine.info.kind == "local"
    assert engine.info.current_model == "qwen3-vl:4b"


def test_agent_sdk_for_claude_provider() -> None:
    provider = ProviderConfig(id="claude", display_name="Claude", kind="cloud", default_model="claude-sonnet-4-6")
    engine = build_engine(provider)
    assert isinstance(engine, AgentSDKEngine)
    assert engine.info.kind == "cloud"


def test_local_provider_without_base_url_raises() -> None:
    provider = ProviderConfig(id="broken", display_name="Broken", kind="local", default_model="x")
    with pytest.raises(ValueError, match="base_url"):
        build_engine(provider)
