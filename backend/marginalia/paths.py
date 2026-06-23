"""Suggest filesystem paths so the user picks instead of typing (issue #46).

Two helpers, both cross-platform and graceful (return ``[]`` rather than raise):
- :func:`detect_obsidian_vaults` reads Obsidian's own ``obsidian.json`` to list the
  vaults the user already has — the reliable way to auto-detect a vault path.
- :func:`suggest_scan_folders` lists common sync roots (Drive/Dropbox/OneDrive…)
  that actually exist on disk, for the "synced Scribe folder" field.

Only paths that currently exist are returned, so the UI never offers a dead link.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def detect_obsidian_vaults() -> list[str]:
    """Return existing vault paths from Obsidian's ``obsidian.json`` (newest first)."""
    config = _obsidian_config_path()
    if config is None or not config.exists():
        return []
    try:
        raw = json.loads(config.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    vaults = raw.get("vaults")
    if not isinstance(vaults, dict):
        return []
    # Each entry: {"path": "...", "ts": <ms>, "open": bool}. Sort by ts, newest first.
    entries = [v for v in vaults.values() if isinstance(v, dict) and v.get("path")]
    entries.sort(key=lambda v: v.get("ts", 0), reverse=True)
    return [str(v["path"]) for v in entries if Path(v["path"]).is_dir()]


def suggest_scan_folders() -> list[str]:
    """Return common sync-folder roots that exist on disk (deduped, in priority order)."""
    home = Path.home()
    candidates = [
        home / "Google Drive",
        home / "GoogleDrive",
        *sorted(home.glob("Library/CloudStorage/GoogleDrive-*")),  # macOS Drive mount
        home / "Dropbox",
        home / "OneDrive",
        home / "Documents",
        home / "Desktop",
    ]
    seen: set[str] = set()
    found: list[str] = []
    for path in candidates:
        resolved = str(path)
        if resolved not in seen and path.is_dir():
            seen.add(resolved)
            found.append(resolved)
    return found


def _obsidian_config_path() -> Path | None:
    """Path to ``obsidian.json`` for the current OS (None if the OS is unknown)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return Path(base) / "obsidian" / "obsidian.json" if base else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"
    return Path.home() / ".config" / "obsidian" / "obsidian.json"  # Linux/other XDG
