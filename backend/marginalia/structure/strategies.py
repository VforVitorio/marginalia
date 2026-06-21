"""Mapping strategies: project Scribe folders into Obsidian as notes and links.

Pure planning only — no file I/O, no templating, no knowledge of OCR or HTTP (docs/ARCHITECTURE.md §3).
A strategy turns a list of ``NoteSource`` into a list of ``NotePlan`` (where a note goes + what it holds).
Adding a strategy (tags, dataview) = one more function here; the export stage renders + writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

Strategy = Literal["mirror", "wikilinks"]


@dataclass(frozen=True)
class NoteSource:
    """One notebook ready to export: its name, its source folder, and the per-page Markdown."""

    name: str
    source_rel_dir: str  # POSIX dir relative to the vault root; "" for the root
    pages_markdown: list[str]


@dataclass(frozen=True)
class NotePlan:
    """A planned output note: where it goes, and either its source (content) or its links (index)."""

    dest_path: PurePosixPath  # relative to the vault root
    source: NoteSource | None = None
    links: tuple[str, ...] | None = None


def mirror_plans(sources: list[NoteSource]) -> list[NotePlan]:
    """One note per notebook at the mirrored folder path (mirror is always applied)."""
    plans: list[NotePlan] = []
    for source in sources:
        dest = PurePosixPath(source.source_rel_dir) / f"{source.name}.md"
        plans.append(NotePlan(dest_path=dest, source=source))
    return plans


def wikilinks_index_plans(sources: list[NoteSource]) -> list[NotePlan]:
    """One folder-index note per distinct source folder, linking its notebooks with ``[[wikilinks]]``."""
    names_by_dir: dict[str, list[str]] = {}
    for source in sources:
        names_by_dir.setdefault(source.source_rel_dir, []).append(source.name)
    plans: list[NotePlan] = []
    for rel_dir, names in names_by_dir.items():
        index_name = PurePosixPath(rel_dir).name or "index"
        if index_name in names:  # a notebook already claims <folder>.md — don't clobber its content
            index_name = f"{index_name} (index)"
        dest = PurePosixPath(rel_dir) / f"{index_name}.md"
        plans.append(NotePlan(dest_path=dest, links=tuple(sorted(names))))
    return plans
