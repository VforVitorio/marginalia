"""StructureMapper: turn notebooks + chosen strategies into a plan of notes to write.

A pure function and the public face of the structure stage. ``mirror`` is always applied; ``wikilinks``
is opt-in. Consumers import ``NoteSource`` / ``NotePlan`` / ``build_plan`` from here.
"""

from __future__ import annotations

from collections.abc import Iterable

from marginalia.structure.strategies import (
    NotePlan,
    NoteSource,
    Strategy,
    mirror_plans,
    wikilinks_index_plans,
)

__all__ = ["NotePlan", "NoteSource", "Strategy", "build_plan"]


def build_plan(sources: list[NoteSource], strategies: Iterable[Strategy]) -> list[NotePlan]:
    """Plan the output notes. ``mirror`` is unconditional; ``wikilinks`` adds folder-index notes."""
    chosen = set(strategies)
    plans = mirror_plans(sources)
    if "wikilinks" in chosen:
        plans = plans + wikilinks_index_plans(sources)
    return plans
