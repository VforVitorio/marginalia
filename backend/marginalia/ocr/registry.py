"""Construye el engine OCR activo desde la config y lista los proveedores disponibles.

Es el único sitio que sabe qué clase de engine corresponde a cada proveedor: Claude usa el Agent SDK;
el resto (Ollama, LM Studio, Gemini) comparten ``OpenAICompatEngine``. Añadir un backend nuevo = un caso
más aquí, sin tocar el orquestador ni la UI.
"""

from __future__ import annotations

from marginalia.config import ProviderConfig, Settings, load_providers, load_settings
from marginalia.ocr.agent_sdk import AgentSDKEngine
from marginalia.ocr.engine import EngineKind, OCREngine
from marginalia.ocr.openai_compat import OpenAICompatEngine


def build_engine(provider: ProviderConfig, model: str | None = None) -> OCREngine:
    """Crea el engine para un proveedor del catálogo.

    Claude (``id == "claude"``) usa el Agent SDK (suscripción); el resto, el adapter OpenAI-compat.
    """
    chosen_model = model or provider.default_model
    if provider.id == "claude":
        return AgentSDKEngine(model=chosen_model or "claude-sonnet-4-6", display_name=provider.display_name)
    if not provider.base_url:
        raise ValueError(f"El proveedor '{provider.id}' necesita base_url (no es Claude).")
    if not chosen_model:
        raise ValueError(f"El proveedor '{provider.id}' necesita un modelo (ninguno configurado).")
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
    """Resuelve el engine activo desde ``settings.json`` + ``providers.toml``."""
    settings = settings or load_settings()
    providers = providers if providers is not None else load_providers()
    if not providers:
        raise ValueError("No hay proveedores configurados (¿falta providers.toml?).")
    chosen = _pick_provider(settings.active_provider, providers)
    return build_engine(chosen, settings.active_model)


def _pick_provider(active_id: str | None, providers: list[ProviderConfig]) -> ProviderConfig:
    if active_id:
        for provider in providers:
            if provider.id == active_id:
                return provider
    return providers[0]  # ponytail: sin selección del usuario, el primero del catálogo
