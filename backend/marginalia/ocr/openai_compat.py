"""``OpenAICompatEngine``: a single adapter for Ollama, LM Studio and Gemini.

All three speak the OpenAI-compatible *chat completions* API with vision. The only difference is
``base_url`` + ``api_key`` + ``model`` (see docs/ARCHITECTURE.md §2). That is why this is one class,
with no ``if provider == ...`` branches.
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import AsyncIterator

import httpx

from marginalia.ocr.engine import EngineInfo, EngineKind
from marginalia.ocr.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# BE-09: a bare float timeout on httpx.AsyncClient applies to *every* phase, including connect — so
# an unreachable base_url (LAN box off, VPN down, typo'd host) blocked a page for the full 120s
# before erroring. Splitting connect out keeps that short while the read budget (between chunks on
# the transcription stream) stays generous for legitimately slow token generation.
_CONNECT_TIMEOUT_S = 5.0
_WRITE_TIMEOUT_S = 30.0
_POOL_TIMEOUT_S = 10.0


class OpenAICompatEngine:
    """OCR backend over the OpenAI-compatible API. Satisfies the ``OCREngine`` Protocol."""

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
        # `timeout` is the read budget: applies between chunks on the streamed response, so a slow
        # model still gets its full transcription time even though connect fails fast.
        self._timeout = httpx.Timeout(
            connect=_CONNECT_TIMEOUT_S,
            read=timeout,
            write=_WRITE_TIMEOUT_S,
            pool=_POOL_TIMEOUT_S,
        )

    def models(self) -> list[str]:
        """Models the runtime reports at ``/models``. Empty list if it doesn't respond."""
        try:
            resp = httpx.get(f"{self._base_url}/models", headers=self._headers(), timeout=10.0)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []
        entries = resp.json().get("data", [])
        return [entry["id"] for entry in entries if "id" in entry]

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        """Stream a page's transcription by parsing the chat-completions deltas."""
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
        b64 = base64.b64encode(image_png).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"
        return {
            "model": self._model,
            "stream": True,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        }


def parse_sse_delta(line: str) -> str | None:
    """Extract the text from a chat-completions SSE line. ``None`` if it carries no text.

    OpenAI shape: ``data: {"choices":[{"delta":{"content":"..."}}]}``. Keep-alive lines, the
    ``[DONE]`` sentinel and JSON without content all return ``None``.
    """
    if not line.startswith("data:"):
        return None
    data = line[len("data:") :].strip()
    if not data or data == "[DONE]":
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        logger.debug("Unparseable SSE line: %r", line)
        return None
    choices = payload.get("choices") or []
    if not choices:
        return None
    return choices[0].get("delta", {}).get("content")
