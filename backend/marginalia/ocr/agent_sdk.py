"""``AgentSDKEngine``: Claude vía ``claude-agent-sdk``, autenticado por la suscripción de Claude Code.

El Agent SDK no documenta paso de imágenes inline en el prompt (confirmado en el README del paquete),
así que usamos sus primitivas: escribimos la página a un PNG temporal y pedimos al agente que lo lea con
su herramienta ``Read`` (que renderiza imágenes) y lo transcriba, streameando el texto del asistente.

--- WHERE TO CHANGE IF X CHANGES ---
- Si el Agent SDK añade imágenes inline en el prompt: sustituir el fichero temporal por content blocks.
- Auth: depende de la sesión de Claude Code (suscripción, sin API key). Si falla, ``ocr/registry.py``
  deja que Gemini/local cubran el job (ver docs/ARCHITECTURE.md §11, riesgo 1).
"""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

from marginalia.ocr.engine import EngineInfo


class AgentSDKEngine:
    """Backend OCR sobre Claude (suscripción, sin API key). Cumple el Protocol ``OCREngine``."""

    def __init__(self, *, model: str, display_name: str = "Claude (suscripción)") -> None:
        self.info = EngineInfo(id="claude", display_name=display_name, kind="cloud", current_model=model)
        self._model = model

    def models(self) -> list[str]:
        """El Agent SDK no expone catálogo de modelos; devolvemos el configurado."""
        return [self._model]

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        """Escribe la página a un PNG temporal y deja que el agente lo lea y transcriba."""
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            image_path.write_bytes(image_png)
            options = ClaudeAgentOptions(
                model=self._model,
                allowed_tools=["Read"],
                permission_mode="bypassPermissions",  # ponytail: PNG temporal propio, sin prompts de permiso
                max_turns=3,  # leer la imagen + responder, con holgura
                cwd=tmp,
            )
            full_prompt = f"Read the image at {image_path} and {prompt}"
            async for message in query(prompt=full_prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            yield block.text
