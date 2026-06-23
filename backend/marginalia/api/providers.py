"""Settings, provider selection, status, and model-admin endpoints (thin: delegate to services)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from marginalia.api.schemas import (
    KeyBody,
    ProviderOut,
    ProvidersOut,
    ProvidersStatusOut,
    ProviderStatus,
    PullBody,
    SelectProvider,
    SettingsUpdate,
)
from marginalia.api.sse import sse_stream
from marginalia.config import (
    ProviderConfig,
    Settings,
    load_settings,
    resolve_providers,
    save_settings,
)
from marginalia.models_admin import (
    ensure_loaded,
    list_models,
    loadable_models,
    pull_model,
    runtime_status,
    supports_load,
    supports_pull,
)

router = APIRouter()


@router.get("/settings")
def read_settings() -> Settings:
    return load_settings()


@router.put("/settings")
def write_settings(update: SettingsUpdate) -> Settings:
    data = load_settings().model_dump()
    data.update(update.model_dump(exclude_none=True))
    settings = Settings(**data)
    save_settings(settings)
    return settings


@router.get("/providers")
def list_provider_catalogue() -> ProvidersOut:
    settings = load_settings()
    providers = [
        ProviderOut(
            id=provider.id,
            display_name=provider.display_name,
            kind=provider.kind,
            current_model=_current_model(provider, settings),
            models=[],  # fetched on demand via /providers/{id}/models — keeps this endpoint non-blocking
        )
        for provider in resolve_providers(settings)
    ]
    return ProvidersOut(providers=providers, active=settings.active_provider)


@router.get("/providers/status")
def providers_status() -> ProvidersStatusOut:
    """Live per-provider status: runtime reachable? which models loaded? what's the next step?"""
    settings = load_settings()
    return ProvidersStatusOut(
        providers=[_provider_status(provider, settings) for provider in resolve_providers(settings)]
    )


def _provider_status(provider: ProviderConfig, settings: Settings) -> ProviderStatus:
    current = _current_model(provider, settings)

    def status(reachable: bool, models: list[str], state: str, hint: str) -> ProviderStatus:
        return ProviderStatus(
            id=provider.id,
            display_name=provider.display_name,
            kind=provider.kind,
            current_model=current,
            reachable=reachable,
            models=models,
            state=state,
            hint=hint,
        )

    if provider.id == "claude":
        # ponytail: no cheap offline auth check exists — report honestly as "unknown" rather than a
        # fake "authenticated"; a real failure surfaces as an OCR `error` event. Active cached probe = #11.
        models = [current] if current else []
        return status(True, models, "unknown", "Uses your Claude Code subscription (run `claude login`).")
    if provider.kind == "cloud":
        configured = bool(provider.api_key) and "PUT_YOUR" not in (provider.api_key or "")
        if not configured:
            return status(False, [], "needs_key", "Add your API key.")
        return status(True, [current] if current else [], "ready", "")
    reachable, models = runtime_status(provider)
    if not reachable:
        return status(False, [], "unreachable", f"Start {provider.display_name} — its server isn't reachable.")
    if not models:
        return status(True, [], "no_model", "Running, but no model loaded.")
    return status(True, models, "ready", "")


@router.post("/providers/select")
def select_provider(body: SelectProvider) -> Settings:
    settings = load_settings()
    settings.active_provider = body.provider_id
    if body.model:
        settings.active_model = body.model
    save_settings(settings)
    return settings


@router.get("/providers/{provider_id}/models")
def provider_models(provider_id: str) -> list[str]:
    return list_models(_provider_or_404(provider_id, load_settings()))


@router.get("/providers/{provider_id}/loadable")
def loadable(provider_id: str) -> list[str]:
    """Downloaded models the app can load headless (LM Studio); empty for other providers."""
    return loadable_models(_provider_or_404(provider_id, load_settings()))


@router.post("/providers/{provider_id}/pull")
async def pull(provider_id: str, body: PullBody) -> StreamingResponse:
    provider = _provider_or_404(provider_id, load_settings())
    if not supports_pull(provider):
        raise HTTPException(status_code=501, detail="This provider does not support pulling models.")
    return StreamingResponse(sse_stream(pull_model(provider, body.model)), media_type="text/event-stream")


@router.post("/providers/{provider_id}/load")
async def load(provider_id: str, body: PullBody) -> ProviderStatus:
    """Load a model into a local runtime that supports headless loading (LM Studio, issue #44)."""
    settings = load_settings()
    provider = _provider_or_404(provider_id, settings)
    if not supports_load(provider):
        raise HTTPException(status_code=501, detail="This provider cannot load models from the app.")
    loaded = await asyncio.to_thread(ensure_loaded, provider, body.model)
    if not loaded:
        raise HTTPException(
            status_code=502,
            detail=f"Could not load '{body.model}'. Is LM Studio's `lms` CLI installed (`lmstudio install-cli`)?",
        )
    return _provider_status(provider, settings)


@router.post("/providers/{provider_id}/key")
def set_key(provider_id: str, body: KeyBody) -> ProviderStatus:
    """Save a cloud API key entered in the UI (overlaid via settings.json, never written to providers.toml)."""
    settings = load_settings()
    provider = _provider_or_404(provider_id, settings)
    if provider.kind != "cloud" or provider.id == "claude":
        raise HTTPException(status_code=400, detail="This provider does not take an API key.")
    settings.api_keys[provider_id] = body.api_key.strip()
    save_settings(settings)
    return _provider_status(_provider_or_404(provider_id, settings), settings)


def _current_model(provider: ProviderConfig, settings: Settings) -> str | None:
    if settings.active_provider == provider.id and settings.active_model:
        return settings.active_model
    return provider.default_model


def _provider_or_404(provider_id: str, settings: Settings) -> ProviderConfig:
    """Resolve a provider with its UI-entered key overlaid (404 if the id is unknown)."""
    provider = next((entry for entry in resolve_providers(settings) if entry.id == provider_id), None)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown provider.")
    return provider
