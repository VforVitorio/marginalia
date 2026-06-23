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


# ---------------------------------------------------------------------------
# wikilinks helpers — all pure, all deterministic
# ---------------------------------------------------------------------------


def _all_folders(sources: list[NoteSource]) -> set[str]:
    """Return every non-root folder implied by the sources, including ancestors.

    A notebook in ``a/b/c`` implies folders ``a``, ``a/b``, and ``a/b/c``.
    The vault root (``""``) is never included; it has no index note (issue #35).
    """
    folders: set[str] = set()
    for source in sources:
        rel = source.source_rel_dir
        if not rel:
            continue
        path = PurePosixPath(rel)
        # Walk from the deepest folder up to (but not including) the root.
        while str(path) != ".":
            folders.add(str(path))
            path = path.parent
    return folders


def _notebooks_by_folder(sources: list[NoteSource]) -> dict[str, list[str]]:
    """Map each ``source_rel_dir`` to the notebook names directly inside it.

    The root folder (``""``) is included here so root notebooks still appear
    in the mirror output, even though no index note is created for it.
    """
    result: dict[str, list[str]] = {}
    for source in sources:
        result.setdefault(source.source_rel_dir, []).append(source.name)
    return result


def _children_by_folder(folders: set[str]) -> dict[str, list[str]]:
    """Map each folder to its IMMEDIATE child folder basenames.

    For a folder ``a/b`` that exists in ``folders``, ``a`` maps to ``["b"]``.
    The parent of a top-level folder (``""``) is excluded as a key.
    """
    result: dict[str, list[str]] = {}
    for folder in folders:
        path = PurePosixPath(folder)
        parent = str(path.parent)
        if parent == ".":
            parent = ""  # normalise PurePosixPath("a").parent → "." → ""
        result.setdefault(parent, []).append(path.name)
    return result


def wikilinks_index_plans(sources: list[NoteSource]) -> list[NotePlan]:
    """One folder-index note per non-root folder, linking child folders and notebooks.

    Rules (issues #35 and #36):
    - The vault root (``source_rel_dir == ""``) never gets an index note.
    - An index is created for EVERY non-root folder in the tree, including
      intermediate folders that contain only sub-folders and no notebooks.
    - Each index links, with ``[[wikilinks]]``: child folders first (sorted by
      basename), then notebooks directly in that folder (sorted by name).
      Obsidian resolves wikilinks by note basename, so only the basename is
      needed — the full path is not included in the link text.
    - Collision guard: if the folder's own basename matches a notebook name in
      that same folder, the index is suffixed ``"<name> (index)"`` to avoid
      clobbering the notebook note.
    - Output is sorted at the top level by ``dest_path`` for determinism.

    Link ordering rationale: sub-folders precede notebooks so readers walk the
    tree top-down in Obsidian's graph, mirroring the physical folder hierarchy.
    Within each group, lexicographic order is used for stable output.
    """
    all_folders = _all_folders(sources)
    notebooks_by_folder = _notebooks_by_folder(sources)
    children_by_folder = _children_by_folder(all_folders)

    plans: list[NotePlan] = []
    for folder in sorted(all_folders):  # stable ordering by path
        folder_basename = PurePosixPath(folder).name

        direct_notebooks = sorted(notebooks_by_folder.get(folder, []))
        child_folder_names = sorted(children_by_folder.get(folder, []))

        # Collision guard: a notebook in this folder already claims <basename>.md.
        index_name = folder_basename
        if index_name in direct_notebooks:
            index_name = f"{index_name} (index)"

        dest = PurePosixPath(folder) / f"{index_name}.md"

        # Child folders first, then notebooks — both groups sorted.
        links = tuple(child_folder_names + direct_notebooks)

        plans.append(NotePlan(dest_path=dest, links=links))

    return plans
