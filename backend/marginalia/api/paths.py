"""Filesystem path suggestions for the settings / onboarding inputs (issue #46, thin router).

Lets the UI offer one-click vault and scan-folder paths instead of making the user type them.
All logic (and the cross-platform/graceful-fail behaviour) lives in ``marginalia.paths``.
"""

from __future__ import annotations

from fastapi import APIRouter

from marginalia.paths import detect_obsidian_vaults, suggest_scan_folders

router = APIRouter()


@router.get("/paths/vaults")
def vault_suggestions() -> list[str]:
    """Existing Obsidian vault paths detected from ``obsidian.json`` (newest first)."""
    return detect_obsidian_vaults()


@router.get("/paths/scan-folders")
def scan_folder_suggestions() -> list[str]:
    """Common sync-folder roots that exist on disk (for the Scribe scan folder)."""
    return suggest_scan_folders()
