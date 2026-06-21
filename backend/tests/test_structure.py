"""Structure planning: mirror mirrors folders, wikilinks adds folder-index notes."""

from __future__ import annotations

from marginalia.structure.mapper import NoteSource, build_plan


def _src(name: str, rel_dir: str, pages: tuple[str, ...] = ("x",)) -> NoteSource:
    return NoteSource(name=name, source_rel_dir=rel_dir, pages_markdown=list(pages))


def test_mirror_mirrors_folder_paths() -> None:
    sources = [_src("a", ""), _src("b", "sub")]
    plans = build_plan(sources, ["mirror"])
    dests = {plan.dest_path.as_posix() for plan in plans}
    assert dests == {"a.md", "sub/b.md"}
    assert all(plan.source is not None for plan in plans)


def test_wikilinks_adds_one_index_per_folder() -> None:
    sources = [_src("a", "sub"), _src("b", "sub")]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    indexes = [plan for plan in plans if plan.links is not None]
    assert len(indexes) == 1
    assert indexes[0].dest_path.as_posix() == "sub/sub.md"
    assert indexes[0].links == ("a", "b")


def test_mirror_is_unconditional() -> None:
    plans = build_plan([_src("a", "")], [])  # no strategies passed
    assert any(plan.source is not None for plan in plans)


def test_wikilinks_index_does_not_clobber_a_same_named_note() -> None:
    # A notebook "sub" inside folder "sub" would otherwise collide with the folder index.
    sources = [_src("sub", "sub"), _src("b", "sub")]
    plans = build_plan(sources, ["mirror", "wikilinks"])
    note_dests = {plan.dest_path.as_posix() for plan in plans if plan.source is not None}
    index_dests = {plan.dest_path.as_posix() for plan in plans if plan.links is not None}
    assert "sub/sub.md" in note_dests  # the notebook keeps its path
    assert note_dests.isdisjoint(index_dests)  # the index avoids every note path
