"""List and pull models from local runtimes (Ollama, LM Studio) over HTTP.

Model management by buttons (the brief): the app never assumes installed models — it asks the runtime.
Pulling is Ollama-only for now; other providers report unsupported (the UI degrades gracefully).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from marginalia.config import ProviderConfig


def runtime_status(provider: ProviderConfig) -> tuple[bool, list[str]]:
    """Return ``(reachable, models)`` for a provider.

    For local runtimes (Ollama / LM Studio) this pings ``/models`` with a short timeout so the UI can
    tell "runtime down" from "running but no model loaded". For Claude there is no HTTP runtime.
    """
    if not provider.base_url:  # Claude (Agent SDK) or a misconfigured entry
        return True, ([provider.default_model] if provider.default_model else [])
    headers = {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
    try:
        resp = httpx.get(f"{provider.base_url.rstrip('/')}/models", headers=headers, timeout=4.0)
        resp.raise_for_status()
    except httpx.HTTPError:
        return False, []
    models = [entry["id"] for entry in resp.json().get("data", []) if "id" in entry]
    return True, models


def list_models(provider: ProviderConfig) -> list[str]:
    """List the models a provider reports. Empty list if it can't be reached."""
    return runtime_status(provider)[1]


def supports_pull(provider: ProviderConfig) -> bool:
    """Only Ollama exposes a model-pull HTTP API we drive from a button."""
    return provider.id == "ollama"


async def pull_model(provider: ProviderConfig, model: str) -> AsyncIterator[dict]:
    """Stream progress while Ollama pulls a model. Yields ``{status, percent}`` events."""
    base = (provider.base_url or "").rstrip("/").removesuffix("/v1")  # Ollama's pull API is at the root
    async with (
        httpx.AsyncClient(timeout=None) as client,
        client.stream("POST", f"{base}/api/pull", json={"name": model}) as resp,
    ):
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield {"status": data.get("status", ""), "percent": _percent(data)}


def _percent(data: dict) -> int | None:
    total = data.get("total")
    completed = data.get("completed")
    if not total:
        return None
    return round(100 * completed / total) if completed else 0
