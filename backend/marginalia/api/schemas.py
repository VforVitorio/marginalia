"""Pydantic request/response models for the ``/api`` contract (see CLAUDE.md §6)."""

from __future__ import annotations

from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    """Partial settings update from the UI; unset fields are left unchanged."""

    vault_path: str | None = None
    scan_folder: str | None = None
    active_provider: str | None = None
    active_model: str | None = None
    strategies: list[str] | None = None


class ProviderOut(BaseModel):
    id: str
    display_name: str
    kind: str
    current_model: str | None
    models: list[str]


class ProvidersOut(BaseModel):
    providers: list[ProviderOut]
    active: str | None
    claude_authenticated: bool


class ProviderStatus(BaseModel):
    id: str
    display_name: str
    kind: str
    reachable: bool
    models: list[str]
    current_model: str | None
    state: str  # ready | no_model | unreachable | needs_key | unknown
    hint: str


class ProvidersStatusOut(BaseModel):
    providers: list[ProviderStatus]


class SelectProvider(BaseModel):
    provider_id: str
    model: str | None = None


class PullBody(BaseModel):
    model: str


class CreateJobOut(BaseModel):
    job_id: str
    name: str
    pages: int


class JobPageOut(BaseModel):
    index: int
    image_url: str
    markdown: str
    done: bool


class JobOut(BaseModel):
    job_id: str
    name: str
    status: str
    pages: list[JobPageOut]


class PageEdit(BaseModel):
    markdown: str


class ExportBody(BaseModel):
    vault_path: str
    strategies: list[str]
    target_dir: str = ""  # destination subfolder for loose uploads (ignored for scanned notebooks)


class ExportOut(BaseModel):
    written: list[str]
