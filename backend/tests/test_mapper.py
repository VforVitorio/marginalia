"""Tests for StructureMapper: mirror + wikilinks strategies (issues #35 and #36).

Covers:
- mirror still produces one note per notebook at the correct path.
- wikilinks never creates a root index.md (issue #35).
- wikilinks creates index notes for every non-root ancestor folder, including
  intermediate folders that contain only sub-folders and no notebooks (issue #36).
- Child-folder links appear before notebook links within each index.
- The name-collision guard suffixes the index ``"<name> (index)"`` when a
  notebook in that folder already claims the folder basename as its note name.
"""

from __future__ import annotations

from marginalia.structure.mapper import NoteSource, build_plan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src(name: str, rel_dir: str, pages: tuple[str, ...] = ("x",)) -> NoteSource:
    return NoteSource(name=name, source_rel_dir=rel_dir, pages_markdown=list(pages))


def _mirror_dests(plans) -> set[str]:
    return {p.dest_path.as_posix() for p in plans if p.source is not None}


def _index_dests(plans) -> set[str]:
    return {p.dest_path.as_posix() for p in plans if p.links is not None}


def _index_links(plans, dest_posix: str) -> tuple[str, ...] | None:
    """Return the links tuple for the index at ``dest_posix``, or None if not found."""
    for p in plans:
        if p.links is not None and p.dest_path.as_posix() == dest_posix:
            return p.links
    return None


# ---------------------------------------------------------------------------
# Mirror tests
# ---------------------------------------------------------------------------


def test_mirror_places_note_in_correct_folder() -> None:
    """Mirror reproduces the source_rel_dir hierarchy as-is."""
    sources = [_src("MyNotes", "Books"), _src("Physics", "Science/Lectures")]
    plans = build_plan(sources, ["mirror"])
    dests = _mirror_dests(plans)
    assert "Books/MyNotes.md" in dests
    assert "Science/Lectures/Physics.md" in dests


def test_mirror_root_notebook_has_no_parent_dir() -> None:
    """A notebook at the vault root lands at ``<name>.md`` with no directory prefix."""
    sources = [_src("ReadingLog", "")]
    plans = build_plan(sources, ["mirror"])
    assert "ReadingLog.md" in _mirror_dests(plans)


def test_mirror_is_unconditional_even_with_no_strategies() -> None:
    """Mirror runs even when the strategies list is empty."""
    sources = [_src("Diary", "Journal")]
    plans = build_plan(sources, [])
    assert any(p.source is not None for p in plans)
    assert "Journal/Diary.md" in _mirror_dests(plans)


# ---------------------------------------------------------------------------
# Issue #35 — no root index
# ---------------------------------------------------------------------------


def test_wikilinks_never_creates_root_index() -> None:
    """No index.md (or any index note) should be planned at the vault root."""
    sources = [_src("Intro", ""), _src("Chapter1", "Part1")]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    index_dests = _index_dests(plans)
    # Nothing directly at the root (no parent directory component).
    root_indexes = [d for d in index_dests if "/" not in d]
    assert root_indexes == [], f"Unexpected root index notes: {root_indexes}"


def test_wikilinks_root_notebook_still_gets_mirror_note() -> None:
    """Root-level notebooks are mirrored even though no root index is created."""
    sources = [_src("Overview", "")]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    assert "Overview.md" in _mirror_dests(plans)
    assert _index_dests(plans) == set()


# ---------------------------------------------------------------------------
# Issue #36 — full ancestor tree of index notes
# ---------------------------------------------------------------------------


def test_wikilinks_creates_index_for_every_non_root_ancestor() -> None:
    """Notebooks only in a/b/c must produce index notes for a, a/b, and a/b/c."""
    sources = [_src("Notes", "a/b/c")]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    index_dests = _index_dests(plans)
    assert "a/a.md" in index_dests
    assert "a/b/b.md" in index_dests
    assert "a/b/c/c.md" in index_dests
    # Vault root must not appear.
    root_indexes = [d for d in index_dests if "/" not in d]
    assert root_indexes == []


def test_wikilinks_nested_tree_quantum_example() -> None:
    """A nested tree: notebooks in Quantum and Quantum/Exercises.

    Expected index notes:
    - Quantum/Quantum.md — links: Exercises (child folder), then Quantum notebooks.
    - Quantum/Exercises/Exercises.md — links: its notebooks only.
    """
    sources = [
        _src("Mechanics", "Quantum"),
        _src("Thermodynamics", "Quantum"),
        _src("ProblemSet1", "Quantum/Exercises"),
        _src("ProblemSet2", "Quantum/Exercises"),
    ]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    index_dests = _index_dests(plans)

    assert "Quantum/Quantum.md" in index_dests
    assert "Quantum/Exercises/Exercises.md" in index_dests

    quantum_links = _index_links(plans, "Quantum/Quantum.md")
    assert quantum_links is not None
    # Child folder "Exercises" comes first, then notebooks sorted.
    assert quantum_links == ("Exercises", "Mechanics", "Thermodynamics")

    exercises_links = _index_links(plans, "Quantum/Exercises/Exercises.md")
    assert exercises_links is not None
    assert exercises_links == ("ProblemSet1", "ProblemSet2")


def test_wikilinks_intermediate_folder_with_only_subfolders() -> None:
    """An intermediate folder that has no direct notebooks still gets an index.

    Tree:  a/ (no notebooks)
               b/ (no notebooks)
                   c/ (has notebooks)
    Index for a must link b; index for a/b must link c.
    """
    sources = [_src("NoteX", "a/b/c"), _src("NoteY", "a/b/c")]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    index_dests = _index_dests(plans)

    assert "a/a.md" in index_dests
    assert "a/b/b.md" in index_dests
    assert "a/b/c/c.md" in index_dests

    # a's index links child folder "b" only (no direct notebooks).
    a_links = _index_links(plans, "a/a.md")
    assert a_links == ("b",)

    # a/b's index links child folder "c" only.
    ab_links = _index_links(plans, "a/b/b.md")
    assert ab_links == ("c",)

    # Leaf index links both notebooks.
    abc_links = _index_links(plans, "a/b/c/c.md")
    assert abc_links == ("NoteX", "NoteY")


def test_wikilinks_link_order_subfolders_before_notebooks() -> None:
    """Child folders must precede notebooks in the links tuple, both groups sorted."""
    sources = [
        _src("ZNote", "folder"),
        _src("ANote", "folder"),
        _src("Item", "folder/child1"),
        _src("Item", "folder/child2"),
    ]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    folder_links = _index_links(plans, "folder/folder.md")
    assert folder_links is not None
    # child1 and child2 come first (sorted), then ANote then ZNote.
    assert folder_links == ("child1", "child2", "ANote", "ZNote")


# ---------------------------------------------------------------------------
# Collision guard
# ---------------------------------------------------------------------------


def test_wikilinks_collision_guard_suffixes_index_name() -> None:
    """If a notebook shares the folder basename, the index gets the (index) suffix."""
    # Notebook "sub" inside folder "sub" — the index must become "sub (index).md".
    sources = [_src("sub", "sub"), _src("other", "sub")]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    note_dests = _mirror_dests(plans)
    index_dests = _index_dests(plans)

    assert "sub/sub.md" in note_dests  # the notebook keeps its mirror path
    assert "sub/sub (index).md" in index_dests  # the index uses the suffix
    assert note_dests.isdisjoint(index_dests)  # no overlap


def test_wikilinks_collision_guard_does_not_fire_without_clash() -> None:
    """Collision guard must NOT add a suffix when there is no name clash."""
    sources = [_src("unrelated", "myfolder")]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    index_dests = _index_dests(plans)
    assert "myfolder/myfolder.md" in index_dests
    assert "myfolder/myfolder (index).md" not in index_dests


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_wikilinks_output_is_deterministic() -> None:
    """Calling build_plan twice on the same input must return identical plans."""
    sources = [
        _src("B", "x/y"),
        _src("A", "x/y"),
        _src("C", "x"),
    ]
    plans_1 = build_plan(sources, ["mirror", "wikilinks"])
    plans_2 = build_plan(sources, ["mirror", "wikilinks"])
    dests_1 = [p.dest_path.as_posix() for p in plans_1]
    dests_2 = [p.dest_path.as_posix() for p in plans_2]
    assert dests_1 == dests_2
