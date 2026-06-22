"""Settings, provider selection, and model-admin endpoints (thin: delegate to services)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from marginalia.api.schemas import (
    ProviderOut,
    ProvidersOut,
    ProvidersStatusOut,
    ProviderStatus,
    PullBody,
    SelectProvider,
    SettingsUpdate,
)
from marginalia.api.sse import sse_stream
from marginalia.config import ProviderConfig, Settings, load_providers, load_settings, save_settings
from marginalia.models_admin import list_models, pull_model, runtime_status, supports_pull

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
        for provider in load_providers()
    ]
    return ProvidersOut(
        providers=providers,
        active=settings.active_provider,
        claude_authenticated=_claude_authenticated(),
    )


@router.get("/providers/status")
def providers_status() -> ProvidersStatusOut:
    """Live per-provider status: runtime reachable? which models loaded? what's the next step?"""
    settings = load_settings()
    return ProvidersStatusOut(providers=[_provider_status(provider, settings) for provider in load_providers()])


def _provider_status(provider: ProviderConfig, settings: Settings) -> ProviderStatus:
    current = _current_model(provider, settings)
    base = {
        "id": provider.id,
        "display_name": provider.display_name,
        "kind": provider.kind,
        "current_model": current,
    }
    if provider.id == "claude":
        return ProviderStatus(
            **base,
            reachable=True,
            models=[current] if current else [],
            state="unknown",
            hint="Uses your Claude Code subscription login (run `claude login` if needed).",
        )
    if provider.kind == "cloud":
        configured = bool(provider.api_key) and "PUT_YOUR" not in (provider.api_key or "")
        if not configured:
            return ProviderStatus(**base, reachable=False, models=[], state="needs_key", hint="Add your API key.")
        return ProviderStatus(**base, reachable=True, models=[current] if current else [], state="ready", hint="")
    reachable, models = runtime_status(provider)
    if not reachable:
        return ProviderStatus(
            **base,
            reachable=False,
            models=[],
            state="unreachable",
            hint=f"Start {provider.display_name} — its server isn't reachable.",
        )
    if not models:
        return ProviderStatus(**base, reachable=True, models=[], state="no_model", hint="Running, but no model loaded.")
    return ProviderStatus(**base, reachable=True, models=models, state="ready", hint="")


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
    return list_models(_provider_or_404(provider_id))


@router.post("/providers/{provider_id}/pull")
async def pull(provider_id: str, body: PullBody) -> StreamingResponse:
    provider = _provider_or_404(provider_id)
    if not supports_pull(provider):
        raise HTTPException(status_code=501, detail="This provider does not support pulling models.")
    return StreamingResponse(sse_stream(pull_model(provider, body.model)), media_type="text/event-stream")


def _current_model(provider: ProviderConfig, settings: Settings) -> str | None:
    if settings.active_provider == provider.id and settings.active_model:
        return settings.active_model
    return provider.default_model


def _provider_or_404(provider_id: str) -> ProviderConfig:
    provider = next((entry for entry in load_providers() if entry.id == provider_id), None)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown provider.")
    return provider


def _claude_authenticated() -> bool:
    # ponytail: optimistic — a real probe (a cheap auth check) is backlog; an actual auth failure
    # surfaces as an `error` SSE event during OCR (see docs/ARCHITECTURE.md §11, risk 1).
    return True
