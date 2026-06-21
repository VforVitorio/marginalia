"""``OpenAICompatEngine``: un solo adapter para Ollama, LM Studio y Gemini.

Los tres hablan el API OpenAI-compatible de *chat completions* con visión. La única diferencia es
``base_url`` + ``api_key`` + ``model`` (ver docs/ARCHITECTURE.md §2). Por eso es una sola clase, sin
ramas ``if provider == ...``.
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator

import httpx

from marginalia.ocr.engine import EngineInfo, EngineKind


class OpenAICompatEngine:
    """Backend OCR sobre el API OpenAI-compatible. Cumple el Protocol ``OCREngine``."""

    def __init__(
        self,
        *,
        id: str,
        display_name: str,
        kind: EngineKind,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.info = EngineInfo(id=id, display_name=display_name, kind=kind, current_model=model)
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    def models(self) -> list[str]:
        """Modelos que el runtime reporta en ``/models``. Lista vacía si no responde."""
        try:
            resp = httpx.get(f"{self._base_url}/models", headers=self._headers(), timeout=10.0)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []
        entries = resp.json().get("data", [])
        return [entry["id"] for entry in entries if "id" in entry]

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        """Streamea la transcripción de una página parseando los deltas de chat completions."""
        payload = self._build_payload(image_png, prompt)
        async with (
            httpx.AsyncClient(timeout=self._timeout) as client,
            client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
            ) as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                chunk = parse_sse_delta(line)
                if chunk:
                    yield chunk

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

    def _build_payload(self, image_png: bytes, prompt: str) -> dict:
        data_url = "data:image/png;base64," + base64.b64encode(image_png).decode("ascii")
        return {
            "model": self._model,
            "stream": True,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }


def parse_sse_delta(line: str) -> str | None:
    """Extrae el texto de una línea SSE de *chat completions*. ``None`` si no aporta texto.

    Formato OpenAI: ``data: {"choices":[{"delta":{"content":"..."}}]}``. Las líneas de keep-alive,
    el centinela ``[DONE]`` y el JSON sin contenido devuelven ``None``.
    """
    if not line.startswith("data:"):
        return None
    data = line[len("data:") :].strip()
    if not data or data == "[DONE]":
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    choices = payload.get("choices") or []
    if not choices:
        return None
    return choices[0].get("delta", {}).get("content")
