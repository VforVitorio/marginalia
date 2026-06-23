"""Render planned notes with Jinja2 and write them into the Obsidian vault.

The only place in the export path that touches the filesystem and the templates (docs/ARCHITECTURE.md
§10). It knows ``structure/`` and Jinja2 — nothing about OCR, jobs, or HTTP.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from jinja2 import Environment, FileSystemLoader

from marginalia.structure.mapper import NotePlan, NoteSource, Strategy, build_plan

_TEMPLATES_DIR = Path(__file__).parent / "templates"


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


def export_notes(sources: list[NoteSource], strategies: list[Strategy], vault_root: Path) -> list[Path]:
    """Plan, render, and write the notes into the vault. Returns the written file paths.

    Raises ``ValueError`` if a planned note path escapes ``vault_root`` — a path traversal via a
    crafted source folder (``..`` in the upload filename or target dir). The API layer maps it to a 400.
    """
    env = _environment()
    root = vault_root.resolve()
    written: list[Path] = []
    for plan in build_plan(sources, strategies):
        dest = vault_root / Path(plan.dest_path)
        if not dest.resolve().is_relative_to(root):
            raise ValueError(f"Note path escapes the vault: {plan.dest_path}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_note(env, plan), encoding="utf-8")
        written.append(dest)
    return written
