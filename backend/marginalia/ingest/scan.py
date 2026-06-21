"""Find PDFs under a folder, preserving each one's path relative to that folder.

Scan-on-demand (a button), not a background watcher (see docs/ARCHITECTURE.md §9). The relative path is
what carries the Scribe folder hierarchy through to the Obsidian export.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PdfRef:
    """A PDF found by a scan: its absolute path and its path relative to the scanned root."""

    path: Path
    rel_path: str  # POSIX, relative to the scanned root


def scan_pdfs(root: Path) -> list[PdfRef]:
    """List every ``*.pdf`` under ``root`` (recursive, case-insensitive), sorted by relative path."""
    if not root.exists():
        return []
    refs = [
        PdfRef(path=path, rel_path=path.relative_to(root).as_posix())
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    ]
    return sorted(refs, key=lambda ref: ref.rel_path)
