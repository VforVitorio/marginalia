"""Best-effort, no-network probe of Claude (subscription) auth state (issue #11).

``AgentSDKEngine`` uses the Claude Code subscription login (no API key). There is no
cheap SDK call to verify that session without spending tokens, so this checks the
*presence* of a credential the SDK would resolve: an environment token, or the
on-disk credentials Claude Code / the ``anthropic`` CLI writes at login.

Presence is a real signal ("you have signed in somewhere") but **not** a validity
guarantee — an expired or revoked token still surfaces as an ``error`` SSE event
during OCR (see docs/ARCHITECTURE.md §11). This is deliberately conservative: it
upgrades the picker from a hardcoded lie to an honest "signed in / not signed in".

--- WHERE TO CHANGE IF AUTH MOVES ---
If Claude Code / claude-agent-sdk changes where it stores credentials, update
``_credential_paths``. A true active probe (a cheap billed call, cached) would
replace :func:`is_claude_authenticated`.
"""

from __future__ import annotations

import os
from pathlib import Path


def is_claude_authenticated() -> bool:
    """True if a Claude credential is present (env token, or a login file on disk)."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    return any(_has_content(path) for path in _credential_paths())


def _credential_paths() -> list[Path]:
    """Known credential locations for Claude Code and the ``anthropic`` CLI, per OS."""
    home = Path.home()
    paths = [home / ".claude" / ".credentials.json"]  # Claude Code subscription login
    appdata = os.environ.get("APPDATA")
    if appdata:  # Windows: anthropic CLI profile store
        paths.append(Path(appdata) / "Anthropic" / "credentials")
    paths.append(home / ".config" / "anthropic" / "credentials")  # Linux/macOS XDG
    return paths


def _has_content(path: Path) -> bool:
    """True if *path* is a non-empty file, or a directory holding a non-empty file."""
    try:
        if path.is_file():
            return path.stat().st_size > 0
        if path.is_dir():
            return any(child.is_file() and child.stat().st_size > 0 for child in path.iterdir())
    except OSError:
        return False
    return False
