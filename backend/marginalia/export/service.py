"""Render planned notes with Jinja2 and write them into the Obsidian vault.

The only place in the export path that touches the filesystem and the templates (docs/ARCHITECTURE.md
§10). It knows ``structure/`` and Jinja2 — nothing about OCR, jobs, or HTTP.
"""

from __future__ import annotations

import os
import re
from dataclasses import replace
from pathlib import Path, PurePosixPath

from jinja2 import Environment, FileSystemLoader

from marginalia.structure.mapper import NotePlan, NoteSource, Strategy, build_plan

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _environment() -> Environment:
    # autoescape=False on purpose: the output is Markdown, not HTML — escaping would corrupt it.
    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_note(env: Environment, plan: NotePlan) -> str:
    """Render one planned note: a content note (Jinja2 template) or a wikilinks index."""
    if plan.source is not None:
        return _render_content(env, plan.source)
    return _render_index(plan.links or ())


def _render_content(env: Environment, source: NoteSource) -> str:
    template = env.get_template("note.md.j2")
    source_label = (PurePosixPath(source.source_rel_dir) / source.name).as_posix()
    return template.render(source=source_label, pages=source.pages_markdown)


def _render_index(links: tuple[str, ...]) -> str:
    return "".join(f"- [[{name}]]\n" for name in links)


def _merge_index_links(planned: tuple[str, ...], existing_markdown: str) -> tuple[str, ...]:
    """Union an index note's planned links with the ``[[wikilinks]]`` already present in its markdown.

    Index notes accumulate (BE-06): exporting notebook B into a folder must not erase the ``[[A]]``
    link a previous export of notebook A wrote into that same folder index. Pure — the caller reads
    the file and passes its text in, so no filesystem path crosses this boundary. Sorted
    lexicographically for deterministic output.
    """
    existing = _WIKILINK_RE.findall(existing_markdown)
    merged = sorted(set(existing) | set(planned))
    return tuple(merged)


def export_notes(sources: list[NoteSource], strategies: list[Strategy], vault_root: Path) -> list[Path]:
    """Plan, render, and write the notes into the vault. Returns the written file paths.

    Raises ``ValueError`` if a planned note path escapes ``vault_root`` — a path traversal via a
    crafted source folder (``..`` in the upload filename or target dir). The API layer maps it to a 400.
    """
    env = _environment()
    root = os.path.realpath(vault_root)
    written: list[Path] = []
    for plan in build_plan(sources, strategies):
        # Normalize with realpath, then require the result to stay under the vault root — a crafted
        # "../" source folder must not escape it (the API maps the raise to a 400). realpath +
        # startswith(root + sep) is the containment barrier; every filesystem op below runs on the
        # `dest` derived from this checked string, so no unvalidated path reaches a read/write sink.
        checked = os.path.realpath(os.path.join(root, str(plan.dest_path)))
        if checked != root and not checked.startswith(root + os.sep):
            raise ValueError(f"Note path escapes the vault: {plan.dest_path}")
        dest = Path(checked)
        # BE-06: index notes accumulate — merge with the existing file so a second export into the
        # same folder keeps earlier links; content notes overwrite (re-exporting replaces the note).
        write_plan = plan
        if plan.source is None and dest.is_file():
            merged = _merge_index_links(plan.links or (), dest.read_text(encoding="utf-8"))
            write_plan = replace(plan, links=merged)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_note(env, write_plan), encoding="utf-8")
        written.append(dest)
    return written
