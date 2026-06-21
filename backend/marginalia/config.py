"""Carga y unifica la configuración de marginalia.

Dos fuentes, dos propósitos (ver docs/ARCHITECTURE.md §7):
- ``providers.toml``     : catálogo de proveedores OCR + secretos. Estático; lo edita el dev una vez.
- ``data/settings.json`` : elecciones de uso diario que fija la UI. Mutables en runtime.

Mantenerlas separadas es lo que permite el principio de producto "el usuario nunca edita config
para el uso diario": ``providers.toml`` es seed/credenciales, ``settings.json`` lo escribe la app.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

DATA_DIR = Path("data")
SETTINGS_PATH = DATA_DIR / "settings.json"
PROVIDERS_PATH = Path("providers.toml")


class ProviderConfig(BaseModel):
    """Un backend OCR del catálogo (``providers.toml``)."""

    id: str
    display_name: str
    kind: str  # "local" | "cloud"
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None


class Settings(BaseModel):
    """Elecciones vivas del usuario (``data/settings.json``), editables por la UI."""

    vault_path: str | None = None
    scan_folder: str | None = None
    active_provider: str | None = None
    active_model: str | None = None
    strategies: list[str] = Field(default_factory=lambda: ["mirror"])


def load_providers(path: Path = PROVIDERS_PATH) -> list[ProviderConfig]:
    """Lee el catálogo de proveedores. Lista vacía si el fichero no existe todavía."""
    if not path.exists():
        return []
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return [ProviderConfig(**entry) for entry in raw.get("providers", [])]


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    """Lee las elecciones del usuario. Defaults si aún no se ha guardado nada."""
    if not path.exists():
        return Settings()
    return Settings.model_validate_json(path.read_text(encoding="utf-8"))


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    """Persiste las elecciones del usuario (la UI llama aquí al cambiar algo)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
