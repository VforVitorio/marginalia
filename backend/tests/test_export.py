"""Export writes mirrored notes and wikilinks indexes into the vault."""

from __future__ import annotations

import pytest

from marginalia.export.service import export_notes
from marginalia.structure.mapper import NoteSource


def test_export_writes_mirror_and_wikilinks(tmp_path) -> None:
    vault = tmp_path / "vault"
    sources = [NoteSource(name="notes", source_rel_dir="journal", pages_markdown=["# Day 1", "more"])]

    written = export_notes(sources, ["mirror", "wikilinks"], vault)

    note = vault / "journal" / "notes.md"
    index = vault / "journal" / "journal.md"
    assert note in written
    assert index in written

    note_text = note.read_text(encoding="utf-8")
    assert "source: journal/notes" in note_text
    assert "## Page 1" in note_text
    assert "## Page 2" in note_text
    assert "# Day 1" in note_text

    assert "[[notes]]" in index.read_text(encoding="utf-8")


def test_export_mirror_only_skips_index(tmp_path) -> None:
    vault = tmp_path / "vault"
    sources = [NoteSource(name="a", source_rel_dir="", pages_markdown=["x"])]
    written = export_notes(sources, ["mirror"], vault)
    assert written == [vault / "a.md"]


def test_export_rejects_path_traversal(tmp_path) -> None:
    vault = tmp_path / "vault"
    outside = tmp_path / "outside.md"
    sources = [NoteSource(name="outside", source_rel_dir="../..", pages_markdown=["x"])]

    with pytest.raises(ValueError, match="escapes the vault"):
        export_notes(sources, ["mirror"], vault)

    assert not outside.exists()
