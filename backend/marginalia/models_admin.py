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
from marginalia.config import CLOUD_MODELS, ProviderConfig

_HTTP_STATUS_TIMEOUT = 4.0


def runtime_status(provider: ProviderConfig) -> tuple[bool, list[str]]:
    """Return ``(reachable, models)`` for a provider.

    For local runtimes (Ollama / LM Studio) this pings ``/models`` with a short timeout so the UI can
    tell "runtime down" from "running but no model loaded". For Claude there is no HTTP runtime.
    LM Studio gets a fast TCP pre-check first so a closed runtime fails in ~0.5s, not the HTTP timeout.
    """
    if not provider.base_url:
        if provider.id == "claude":  # Claude (Agent SDK) has no HTTP runtime to probe
            return True, ([provider.default_model] if provider.default_model else [])
        # BE-21: any other provider with no base_url is misconfigured, not ready — this used to
        # early-return reachable+ready for every no-base_url entry, which let a broken local
        # provider (e.g. a typo'd/blanked base_url in providers.toml) show a green status.
        return False, []
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


def cloud_models(provider: ProviderConfig, probed: list[str]) -> list[str]:
    """Models to offer in the picker for a reachable cloud provider (issue #148).

    Prefers the curated ``config.CLOUD_MODELS`` entry (hand-picked, vision-capable models) over
    *probed* — the raw list the live ``/models`` probe returned — because a cloud provider's own
    catalogue endpoint (Gemini in particular) mixes in models that are useless for OCR. Falls back
    to *probed* for any cloud provider we haven't curated yet, so a new entry in ``providers.toml``
    still gets *some* model list instead of none.
    """
    return CLOUD_MODELS.get(provider.id) or probed


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


_PULL_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)


async def pull_model(provider: ProviderConfig, model: str) -> AsyncGenerator[dict, None]:
    """Stream progress while Ollama pulls a model.

    Yields ``{type: "pull_progress", status, percent}`` per NDJSON line, using the same
    ``{type: ...}`` envelope as the job/OCR stream (``jobs/service.py``) so the frontend can share
    one SSE frame parser (issue #138 / AR-02).

    A failed pull (bad model name, disk full, ...) surfaces as an Ollama ``{"error": "..."}`` line
    mid-stream, and a dead/unreachable Ollama surfaces as an ``httpx`` exception — either raised on
    connect or mid-stream, *after* the 200 response has already been sent (FastAPI's
    ``StreamingResponse`` flushes headers on the first chunk). Previously both cases were silently
    dropped: the generator just stopped, and the client read the truncated stream as success
    (issue #138 / BE-04). Both are now caught here and turned into one terminal ``{type: "error"}``
    frame the client can act on. ``timeout=None`` on the transport is also replaced with a bounded
    read timeout — a wedged Ollama would otherwise hold the request open forever.
    """
    base = (provider.base_url or "").rstrip("/").removesuffix("/v1")  # Ollama's pull API is at the root
    try:
        async with (
            httpx.AsyncClient(timeout=_PULL_TIMEOUT) as client,
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
                if "error" in data:
                    yield {"type": "error", "message": str(data["error"])}
                    return
                yield {"type": "pull_progress", "status": data.get("status", ""), "percent": _percent(data)}
    except httpx.HTTPError as exc:
        yield {"type": "error", "message": f"Could not pull '{model}': {exc}"}


def _percent(data: dict) -> int | None:
    total = data.get("total")
    completed = data.get("completed")
    if not total:
        return None
    return round(100 * completed / total) if completed else 0
