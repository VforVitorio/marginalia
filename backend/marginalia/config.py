"""Load and unify marginalia's configuration.

Two sources, two purposes (see docs/ARCHITECTURE.md §7):
- ``providers.toml``     : catalogue of OCR providers + secrets. Static; the dev edits it once.
- ``data/settings.json`` : day-to-day choices the UI writes. Mutable at runtime.

Keeping them separate is what enables the product principle "the user never edits config for daily
use": ``providers.toml`` is seed/credentials, ``settings.json`` is written by the app.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

DATA_DIR = Path("data")
SETTINGS_PATH = DATA_DIR / "settings.json"
PROVIDERS_PATH = Path("providers.toml")


class ProviderConfig(BaseModel):
    """An OCR backend from the catalogue (``providers.toml``)."""

    id: str
    display_name: str
    kind: str  # "local" | "cloud"
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None


class Settings(BaseModel):
    """The user's live choices (``data/settings.json``), editable from the UI."""

    vault_path: str | None = None
    scan_folder: str | None = None
    active_provider: str | None = None
    active_model: str | None = None
    strategies: list[str] = Field(default_factory=lambda: ["mirror"])


def load_providers(path: Path = PROVIDERS_PATH) -> list[ProviderConfig]:
    """Read the provider catalogue. Empty list if the file does not exist yet."""
    if not path.exists():
        return []
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return [ProviderConfig(**entry) for entry in raw.get("providers", [])]


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Read the user's choices. Defaults if nothing has been saved yet."""
    if not path.exists():
        return Settings()
    return Settings.model_validate_json(path.read_text(encoding="utf-8"))


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    """Persist the user's choices (the UI calls this whenever something changes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
