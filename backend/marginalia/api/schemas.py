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
    """Summary of one provider for the catalogue list (models omitted — fetched on demand)."""

    id: str
    display_name: str
    kind: str
    current_model: str | None
    models: list[str]


class ProvidersOut(BaseModel):
    """Full provider catalogue with the currently active provider id."""

    providers: list[ProviderOut]
    active: str | None


class ProviderStatus(BaseModel):
    """Live status of one provider as seen by the UI.

    ``state`` vocabulary: ``ready`` | ``no_model`` | ``unreachable`` | ``needs_key`` | ``invalid_key`` |
    ``unknown``. ``invalid_key`` (BE-07): a cloud key is present but the provider rejected it.
    ``hint`` is a human-readable next step shown when the provider is not ready.
    """

    id: str
    display_name: str
    kind: str
    reachable: bool
    models: list[str]
    current_model: str | None
    state: str
    hint: str


class ProvidersStatusOut(BaseModel):
    """Live status for every configured provider."""

    providers: list[ProviderStatus]


class SelectProvider(BaseModel):
    """Request body for ``POST /providers/select``."""

    provider_id: str
    model: str | None = None


class PullBody(BaseModel):
    """Request body for ``POST /providers/{id}/pull`` and ``POST /providers/{id}/load``."""

    model: str


class KeyBody(BaseModel):
    """Request body for ``POST /providers/{id}/key``."""

    api_key: str


class ScannedPdfOut(BaseModel):
    """One PDF found in the scan folder: its path relative to the scan root and its notebook name."""

    rel_path: str
    name: str


class ScanOut(BaseModel):
    """Response for ``GET /scan``: the PDFs under the configured Scribe scan folder."""

    pdfs: list[ScannedPdfOut]


class CreateJobOut(BaseModel):
    """Response for ``POST /jobs``: the new job id and the number of pages detected."""

    job_id: str
    name: str
    pages: int


class JobPageOut(BaseModel):
    """One page as returned by the review API: its index, image URL, transcript, and done flag."""

    index: int
    image_url: str
    markdown: str
    done: bool


class JobOut(BaseModel):
    """Full job state as returned by ``GET /jobs/{id}``."""

    job_id: str
    name: str
    status: str
    pages: list[JobPageOut]


class PageEdit(BaseModel):
    """Request body for ``PUT /jobs/{id}/pages/{index}``."""

    markdown: str


class ExportBody(BaseModel):
    """Request body for ``POST /jobs/{id}/export``."""

    vault_path: str
    strategies: list[str]
    target_dir: str = ""  # destination subfolder for loose uploads (ignored for scanned notebooks)


class ExportOut(BaseModel):
    """Response for ``POST /jobs/{id}/export``: absolute paths of the written Markdown files."""

    written: list[str]
