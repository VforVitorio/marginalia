"""List and pull models from local runtimes (Ollama, LM Studio) over HTTP.

Model management by buttons (the brief): the app never assumes installed models — it asks the runtime.
Pulling is Ollama-only for now; other providers report unsupported (the UI degrades gracefully).
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from urllib.parse import urlsplit

import httpx

from marginalia import lms_bridge
from marginalia.config import ProviderConfig

_HTTP_STATUS_TIMEOUT = 4.0


def runtime_status(provider: ProviderConfig) -> tuple[bool, list[str]]:
    """Return ``(reachable, models)`` for a provider.

    For local runtimes (Ollama / LM Studio) this pings ``/models`` with a short timeout so the UI can
    tell "runtime down" from "running but no model loaded". For Claude there is no HTTP runtime.
    LM Studio gets a fast TCP pre-check first so a closed runtime fails in ~0.5s, not the HTTP timeout.
    """
    if not provider.base_url:  # Claude (Agent SDK) or a misconfigured entry
        return True, ([provider.default_model] if provider.default_model else [])
    if provider.id == "lmstudio":
        host, port = _host_port(provider.base_url, lms_bridge.DEFAULT_PORT)
        if not lms_bridge.is_server_up(host, port):
            return False, []  # server closed — skip the multi-second HTTP wait
    headers = {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
    try:
        resp = httpx.get(f"{provider.base_url.rstrip('/')}/models", headers=headers, timeout=_HTTP_STATUS_TIMEOUT)
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


def supports_load(provider: ProviderConfig) -> bool:
    """LM Studio can start its server and load a model headless via the ``lms`` CLI (issue #44)."""
    return provider.id == "lmstudio"


def loadable_models(provider: ProviderConfig) -> list[str]:
    """Downloaded models available to load headless (LM Studio). Empty for other providers.

    LM Studio's ``/v1/models`` lists only *loaded* models, so the "Load a model" UI needs this
    separate list of what's on disk (``lms ls``).
    """
    if provider.id != "lmstudio":
        return []
    return lms_bridge.downloaded_model_ids()


def ensure_runtime_ready(provider: ProviderConfig) -> bool:
    """For LM Studio, start its server (headless if possible) and report whether it's reachable.

    Non-LM-Studio providers are always "ready" here (nothing to start). Lets the API tell
    "LM Studio isn't running" apart from "running but no models downloaded" — note that when the
    GUI is closed, ``lms daemon up`` may fail to cold-start (LM Studio limitation, see lms #97),
    so this returns False and the UI asks the user to open the app.
    """
    if provider.id != "lmstudio":
        return True
    host, port = _host_port(provider.base_url or "", lms_bridge.DEFAULT_PORT)
    return lms_bridge.ensure_server_up(host, port)


def ensure_loaded(provider: ProviderConfig, model: str) -> bool:
    """Start LM Studio's server (headless if needed) and load *model*. LM Studio only; blocking.

    Returns True once the model is loaded. Call from async routes via ``asyncio.to_thread`` — the
    VRAM load can take ~2 min and must not block the event loop.
    """
    if provider.id != "lmstudio":
        return False
    if not ensure_runtime_ready(provider):
        return False
    return lms_bridge.load_model(model)


def _host_port(base_url: str, default_port: int) -> tuple[str, int]:
    """Split host/port out of a base URL, falling back to localhost / *default_port*."""
    parts = urlsplit(base_url)
    return (parts.hostname or lms_bridge.DEFAULT_HOST, parts.port or default_port)


async def pull_model(provider: ProviderConfig, model: str) -> AsyncGenerator[dict, None]:
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
