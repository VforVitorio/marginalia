"""``AgentSDKEngine``: Claude via ``claude-agent-sdk``, authenticated by the Claude Code subscription.

The Agent SDK does not document inline image input in the prompt (confirmed in the package README), so
we use its real primitives: write the page to a temporary PNG and ask the agent to read it with its
``Read`` tool (which renders images) and transcribe it, streaming the assistant text.

--- WHERE TO CHANGE IF X CHANGES ---
- If the Agent SDK adds inline images in the prompt: replace the temp file with content blocks.
- Auth: depends on the Claude Code session (subscription, no API key). If it fails, ``ocr/registry.py``
  lets Gemini/local cover the job (see docs/ARCHITECTURE.md §11, risk 1).
"""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

from marginalia.ocr.engine import EngineInfo


class AgentSDKEngine:
    """OCR backend over Claude (subscription, no API key). Satisfies the ``OCREngine`` Protocol."""

    def __init__(self, *, model: str, display_name: str = "Claude (subscription)") -> None:
        self.info = EngineInfo(id="claude", display_name=display_name, kind="cloud", current_model=model)
        self._model = model

    def models(self) -> list[str]:
        """The Agent SDK exposes no model catalogue; return the configured one."""
        return [self._model]

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        """Write the page to a temporary PNG and let the agent read and transcribe it."""
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            image_path.write_bytes(image_png)
            options = ClaudeAgentOptions(
                model=self._model,
                allowed_tools=["Read"],
                permission_mode="bypassPermissions",  # ponytail: our own temp PNG, no permission prompts
                max_turns=3,  # read the image + answer, with headroom
                cwd=tmp,
            )
            full_prompt = f"Read the image at {image_path} and {prompt}"
            async for message in query(prompt=full_prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            yield block.text
