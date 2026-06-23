"""Render planned notes with Jinja2 and write them into the Obsidian vault.

The only place in the export path that touches the filesystem and the templates (docs/ARCHITECTURE.md
§10). It knows ``structure/`` and Jinja2 — nothing about OCR, jobs, or HTTP.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from jinja2 import Environment, FileSystemLoader, select_autoescape

from marginalia.structure.mapper import NotePlan, NoteSource, Strategy, build_plan

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _environment() -> Environment:
    # select_autoescape() only escapes html/htm/xml/xhtml templates; our note.md.j2 is Markdown, so it
    # is NOT escaped (HTML-escaping would corrupt the notes). Preferred over a bare autoescape=False —
    # same behaviour for Markdown, but it's the pattern static analysis recognises as safe.
    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(),
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

    Each destination is confined to ``vault_root`` — a plan whose path escapes it (e.g. a ``..`` in a
    loose upload's target folder) is skipped rather than written outside the vault (path-traversal guard).
    """
    env = _environment()
    root = vault_root.resolve()
    written: list[Path] = []
    for plan in build_plan(sources, strategies):
        dest = vault_root / Path(plan.dest_path)
        safe = dest.resolve()  # write through the *validated* path so the guard covers the sink
        if not safe.is_relative_to(root):
            continue  # destination escapes the vault — refuse to write it
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(render_note(env, plan), encoding="utf-8")
        written.append(dest)
    return written
