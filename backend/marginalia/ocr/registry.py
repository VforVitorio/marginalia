"""Build the active OCR engine from config and list the available providers.

This is the only place that knows which engine class maps to each provider: Claude uses the Agent SDK;
everyone else (Ollama, LM Studio, Gemini) shares ``OpenAICompatEngine``. Adding a new backend = one more
case here, without touching the orchestrator or the UI.
"""

from __future__ import annotations

from marginalia.config import ProviderConfig, Settings, load_providers, load_settings
from marginalia.ocr.agent_sdk import AgentSDKEngine
from marginalia.ocr.engine import EngineKind, OCREngine
from marginalia.ocr.openai_compat import OpenAICompatEngine


def build_engine(provider: ProviderConfig, model: str | None = None) -> OCREngine:
    """Create the engine for a catalogue provider.

    Claude (``id == "claude"``) uses the Agent SDK (subscription); everyone else, the OpenAI-compat adapter.
    """
    chosen_model = model or provider.default_model
    if provider.id == "claude":
        return AgentSDKEngine(model=chosen_model or "claude-sonnet-4-6", display_name=provider.display_name)
    if not provider.base_url:
        raise ValueError(f"Provider '{provider.id}' needs a base_url (it is not Claude).")
    if not chosen_model:
        raise ValueError(f"Provider '{provider.id}' needs a model (none configured).")
    kind: EngineKind = "cloud" if provider.kind == "cloud" else "local"
    return OpenAICompatEngine(
        id=provider.id,
        display_name=provider.display_name,
        kind=kind,
        base_url=provider.base_url,
        model=chosen_model,
        api_key=provider.api_key,
    )


def active_engine(
    settings: Settings | None = None,
    providers: list[ProviderConfig] | None = None,
) -> OCREngine:
    """Resolve the active engine from ``settings.json`` + ``providers.toml``."""
    settings = settings or load_settings()
    providers = providers if providers is not None else load_providers()
    if not providers:
        raise ValueError("No providers configured (is providers.toml missing?).")
    chosen = _pick_provider(settings.active_provider, providers)
    return build_engine(chosen, settings.active_model)


def _pick_provider(active_id: str | None, providers: list[ProviderConfig]) -> ProviderConfig:
    if active_id:
        for provider in providers:
            if provider.id == active_id:
                return provider
    return providers[0]  # ponytail: with no user selection, the first in the catalogue
