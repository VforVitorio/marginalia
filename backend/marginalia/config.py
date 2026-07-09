"""Load and unify marginalia's configuration.

Two sources, two purposes (see docs/ARCHITECTURE.md §7):
- ``providers.toml``     : catalogue of OCR providers + secrets. Static; the dev edits it once.
- ``data/settings.json`` : day-to-day choices the UI writes. Mutable at runtime.

Keeping them separate is what enables the product principle "the user never edits config for daily
use": ``providers.toml`` is seed/credentials, ``settings.json`` is written by the app.
"""

from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


def _resolve_home_dir(env_value: str | None) -> Path | None:
    """Pure resolution of the ``MARGINALIA_HOME`` env var.

    ``None`` (unset or empty) means "stay CWD-relative" — the historical, still-default
    behavior that lets tests isolate ``data/`` and ``providers.toml`` with
    ``monkeypatch.chdir(tmp_path)`` (see ``backend/tests/test_api.py``). Only a non-empty
    value anchors the paths to a fixed directory, for running the installed console script
    from outside the repo checkout (BE-11).
    """
    return Path(env_value) if env_value else None


def _resolve_paths(home: Path | None) -> tuple[Path, Path, Path]:
    """Derive ``(data_dir, settings_path, providers_path)`` from an optional anchor dir.

    ``home=None`` keeps every path relative, resolved against the process CWD at each
    filesystem call — exactly the pre-``MARGINALIA_HOME`` behavior.
    """
    data_dir = (home / "data") if home else Path("data")
    settings_path = data_dir / "settings.json"
    providers_path = (home / "providers.toml") if home else Path("providers.toml")
    return data_dir, settings_path, providers_path


_MARGINALIA_HOME = _resolve_home_dir(os.environ.get("MARGINALIA_HOME"))
DATA_DIR, SETTINGS_PATH, PROVIDERS_PATH = _resolve_paths(_MARGINALIA_HOME)


class ProviderConfig(BaseModel):
    """An OCR backend from the catalogue (``providers.toml``)."""

    id: str
    display_name: str
    kind: str  # "local" | "cloud"
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None


# ponytail: curated list; fetch from the API if it drifts. Gemini's own ``/models`` endpoint lists
# dozens of models unrelated to OCR (embeddings, text-only, deprecated previews), so the picker
# offers this hand-picked, vision-capable subset instead of the raw probe result (issue #148).
# Claude has no such list — it's a single subscription surface, picked via the Agent SDK, not a
# model catalogue — so it is deliberately absent here.
CLOUD_MODELS: dict[str, list[str]] = {
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ],
}


class Settings(BaseModel):
    """The user's live choices (``data/settings.json``), editable from the UI."""

    vault_path: str | None = None
    scan_folder: str | None = None
    active_provider: str | None = None
    active_model: str | None = None
    strategies: list[str] = Field(default_factory=lambda: ["mirror"])
    api_keys: dict[str, str] = Field(default_factory=dict)  # provider_id -> cloud API key entered in the UI


def load_providers(path: Path = PROVIDERS_PATH) -> list[ProviderConfig]:
    """Read the provider catalogue. Empty list if the file does not exist yet."""
    if not path.exists():
        return []
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return [ProviderConfig(**entry) for entry in raw.get("providers", [])]


def resolve_providers(settings: Settings) -> list[ProviderConfig]:
    """Provider catalogue with UI-entered API keys overlaid on the seed catalogue.

    Lets a user paste a cloud key from the app (saved to ``settings.json``) without editing
    ``providers.toml``. A settings key wins over the seed; a provider with no override keeps its
    seed key (or ``None``). This is how a UI-entered key reaches both the status probe and the engine.
    """
    overlaid: list[ProviderConfig] = []
    for provider in load_providers():
        key = settings.api_keys.get(provider.id)
        overlaid.append(provider.model_copy(update={"api_key": key}) if key else provider)
    return overlaid


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Read the user's choices. Defaults if nothing has been saved yet, or if the file is corrupt.

    BE-12: every route that touches settings calls this, so a malformed ``settings.json`` (a crash
    mid-write predating ``write_text_atomic``, or manual editing) must not 500 every endpoint in the
    app. ``model_validate_json`` raises ``ValidationError`` for both invalid JSON syntax and schema
    mismatches (pydantic v2 wraps the JSON parser's errors the same way), so catching just that one
    exception type covers both failure shapes. Losing the user's saved choices is an acceptable
    trade for keeping the app usable — the alternative is bricking it until they hand-delete a file
    they were promised never to touch.
    """
    if not path.exists():
        return Settings()
    try:
        return Settings.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError:
        logger.warning("Corrupt settings.json at %s — falling back to defaults.", path)
        return Settings()


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    """Persist the user's choices (the UI calls this whenever something changes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, settings.model_dump_json(indent=2))


def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` without ever leaving a truncated file behind (BE-12).

    Writes to a sibling temp file first, then ``os.replace`` swaps it into place — atomic on
    both POSIX and Windows as long as source and destination share a filesystem, which the
    same-directory temp file guarantees. A crash or power-cut mid-write leaves the temp file
    corrupt and ``path`` untouched, instead of truncating ``path`` itself into invalid JSON that
    would otherwise 500 on the next read. Shared by ``save_settings`` above and
    ``jobs.store.JobStore._write``.
    """
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(text, encoding=encoding)
    os.replace(tmp_path, path)
