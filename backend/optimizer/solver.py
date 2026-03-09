"""
Optimization solver for artifact combinations.

Searches the Cartesian product of artifact slots, scores each combination
against the user's target stats, and returns the top-N builds.

The algorithm is intentionally simple (brute-force with early pruning) so
that it is easy to understand and validate.  For large inventories (>200
artifacts per slot) consider adding a beam-search or pruning heuristic.
"""

from __future__ import annotations

import itertools
import logging
from typing import Dict, List, Optional

from .calculator import calculate_build_score, calculate_character_stats
from .constraints import filter_artifacts_by_constraints
from .models import Artifact, Build, Constraint, SLOTS, Weapon

logger = logging.getLogger(__name__)

# Maximum number of artifact combinations to evaluate before giving up.
# 5 slots × 20 artifacts each → 3.2 million combos, which is too slow for a
# synchronous API call.  Cap at a reasonable value.
MAX_COMBINATIONS = 100_000


def generate_artifact_combinations(
    artifacts_by_slot: Dict[str, List[Artifact]],
) -> itertools.product:
    """
    Generate all valid (flower, plume, sands, goblet, circlet) combinations.

    Returns an ``itertools.product`` iterator so that callers can consume
    combinations lazily without materialising the full list in memory.
    """
    ordered_slots = list(SLOTS)
    slot_lists = []
    for slot in ordered_slots:
        arts = artifacts_by_slot.get(slot, [])
        if arts:
            slot_lists.append(arts)
        else:
            # If a slot has no artifacts, emit a sentinel None so the
            # combination is still generated but will score poorly.
            slot_lists.append([None])

    return itertools.product(*slot_lists)


def optimize_artifacts(
    character_key: str,
    available_artifacts: List[Artifact],
    target_stats: Dict[str, float],
    constraints: Optional[List[Constraint]] = None,
    weapon: Optional[Weapon] = None,
    buffs: Optional[Dict[str, float]] = None,
    top_n: int = 5,
) -> List[Build]:
    """
    Find the top-N artifact builds for *character_key*.

    Args:
        character_key:       Character name (must match ``calculator.CHARACTER_BASE_STATS``).
        available_artifacts: All artifact pieces available for this character.
        target_stats:        Desired stat -> weight mapping, e.g.
                             ``{"Crit Rate": 0.7, "Crit DMG": 1.4}``.
        constraints:         Optional list of :class:`~optimizer.models.Constraint`.
        weapon:              Optional equipped weapon.
        buffs:               Optional external stat buffs (team, food, etc.).
        top_n:               How many top builds to return.

    Returns:
        A list of :class:`~optimizer.models.Build` objects sorted by
        ``total_score`` descending (best first).
    """
    if not available_artifacts:
        logger.warning("No artifacts provided for %s – returning empty result.", character_key)
        return []

    # Group artifacts by slot
    artifacts_by_slot: Dict[str, List[Artifact]] = {}
    for art in available_artifacts:
        artifacts_by_slot.setdefault(art.slot, []).append(art)

    # Apply constraints
    if constraints:
        artifacts_by_slot = filter_artifacts_by_constraints(artifacts_by_slot, constraints)

    # Sanity-check: estimate combination count and warn if very large
    combo_count = 1
    for arts in artifacts_by_slot.values():
        combo_count *= max(len(arts), 1)

    if combo_count > MAX_COMBINATIONS:
        logger.warning(
            "Combination count (%d) exceeds limit (%d) for %s. "
            "Results may be a partial optimum. Consider adding constraints.",
            combo_count, MAX_COMBINATIONS, character_key,
        )

    ordered_slots = list(SLOTS)

    top_builds: List[Build] = []
    evaluated = 0

    for combo in generate_artifact_combinations(artifacts_by_slot):
        if evaluated >= MAX_COMBINATIONS:
            break

        # Build slot -> artifact mapping (skip None sentinels)
        slot_map: Dict[str, Artifact] = {}
        for slot, art in zip(ordered_slots, combo):
            if art is not None:
                slot_map[slot] = art

        stats = calculate_character_stats(character_key, slot_map, weapon, buffs)
        score = calculate_build_score(stats, target_stats)

        build = Build(
            character=character_key,
            artifacts=slot_map,
            weapon=weapon,
            total_score=score,
            stat_values=stats,
        )

        # Maintain a top-N list (sorted ascending so we can compare the minimum)
        if len(top_builds) < top_n:
            top_builds.append(build)
            top_builds.sort(key=lambda b: b.total_score)
        elif score > top_builds[0].total_score:
            top_builds[0] = build
            top_builds.sort(key=lambda b: b.total_score)

        evaluated += 1

    # Return sorted best-first
    top_builds.sort(key=lambda b: b.total_score, reverse=True)
    logger.info(
        "Optimized %s: evaluated %d combinations, returning top %d.",
        character_key, evaluated, len(top_builds),
    )
    return top_builds
