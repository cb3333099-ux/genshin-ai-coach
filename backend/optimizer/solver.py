"""
Optimization solver for artifact combinations.

Algorithm:
1. Group available artifacts by slot.
2. Apply constraints to filter artifacts.
3. Generate all valid (flower, plume, sands, goblet, circlet) combinations.
4. Score each combination against target stats with early pruning.
5. Return the top-N builds sorted by score.

The algorithm uses a hybrid approach:
- Pre-scoring per-artifact for fast pruning
- Keeping top-K candidates per slot to limit enumeration
- Lazy evaluation with combination limit for large inventories
"""

from __future__ import annotations

import itertools
import logging
from typing import Dict, List, Optional, Tuple

from .calculator import (
    calculate_build_score,
    calculate_character_stats,
    score_artifact,
    score_mainstat,
    get_default_weights,
)
from .constraints import filter_artifacts_by_constraints
from .models import Artifact, Build, Constraint, SLOTS, Weapon
from .utils import normalize_stat_name, normalize_target_stats, ARTIFACT_SLOTS, PERCENT_STATS

logger = logging.getLogger(__name__)

# Maximum candidates per slot kept before full combination enumeration.
_CANDIDATES_PER_SLOT = 10

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

    Uses a hybrid pruning strategy:
      1. Group artifacts by slot
      2. Apply user constraints (set requirements, stat minimums, etc.)
      3. Pre-score each artifact and keep top K per slot
      4. Enumerate combinations with early termination
      5. Score against target stats and return top N

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

    # Use provided target stats or get defaults for character
    weights = target_stats if target_stats else get_default_weights(character_key)
    norm_weights = normalize_target_stats(weights)

    # Group artifacts by slot
    artifacts_by_slot: Dict[str, List[Artifact]] = {}
    for art in available_artifacts:
        artifacts_by_slot.setdefault(art.slot, []).append(art)

    # Apply constraints
    if constraints:
        artifacts_by_slot = filter_artifacts_by_constraints(artifacts_by_slot, constraints)

    # Pre-score each artifact for efficient ranking
    def _total_score(art: Artifact) -> float:
        """Score = substat score + main stat contribution."""
        if art is None:
            return 0.0
        return score_artifact(art, norm_weights) + score_mainstat(art, norm_weights)

    # Keep top K candidates per slot to limit enumeration
    slot_candidates: List[List[Optional[Artifact]]] = []
    combo_estimate = 1

    for slot in ARTIFACT_SLOTS:
        candidates = sorted(artifacts_by_slot.get(slot, []), key=_total_score, reverse=True)
        # Keep top K to reduce search space
        candidates = candidates[:_CANDIDATES_PER_SLOT]
        if not candidates:
            candidates = [None]  # Allow empty slot
        slot_candidates.append(candidates)
        combo_estimate *= len(candidates)

    # Sanity-check: warn if still very large
    if combo_estimate > MAX_COMBINATIONS:
        logger.warning(
            "Combination estimate (%d) exceeds limit (%d) for %s. "
            "Results may be partial. Consider adding constraints.",
            combo_estimate, MAX_COMBINATIONS, character_key,
        )

    ordered_slots = list(SLOTS)
    top_builds: List[Build] = []
    evaluated = 0

    # Enumerate combinations with early termination
    for combo in itertools.product(*slot_candidates):
        if evaluated >= MAX_COMBINATIONS:
            logger.warning("Hit combination limit; results may be incomplete.")
            break

        # Build slot -> artifact mapping (skip None sentinels)
        slot_map: Dict[str, Artifact] = {}
        for slot, art in zip(ordered_slots, combo):
            if art is not None:
                slot_map[slot] = art

        # Calculate final stats
        stats = calculate_character_stats(character_key, slot_map, weapon, buffs)
        
        # Score build
        score = calculate_build_score(stats, weights)

        build = Build(
            character=character_key,
            artifacts=slot_map,
            weapon=weapon,
            total_score=score,
            stat_values=stats,
        )

        # Maintain a top-N list using incremental min-heap approach
        if len(top_builds) < top_n:
            top_builds.append(build)
            top_builds.sort(key=lambda b: b.total_score)
        elif score > top_builds[0].total_score:
            # Replace worst build if this one is better
            top_builds[0] = build
            top_builds.sort(key=lambda b: b.total_score)

        evaluated += 1

    # Return sorted best-first (highest score first)
    top_builds.sort(key=lambda b: b.total_score, reverse=True)
    
    logger.info(
        "Optimized %s: evaluated %d combinations (estimate %d), returning top %d.",
        character_key, evaluated, combo_estimate, len(top_builds),
    )
    return top_builds


def _satisfies_constraints(
    total_stats: Dict[str, float], constraints: Dict[str, float]
) -> bool:
    """
    Return True if *total_stats* meets all minimum *constraints*.

    Constraints for percentage stats (e.g. Crit Rate) are expected as
    fractions (0.5 = 50 %), while ``total_stats`` holds these in percentage
    form (50.0 = 50 %).  The comparison is normalised accordingly.
    Constraints for flat stats (e.g. Elemental Mastery) are compared directly.
    """
    for stat, minimum in constraints.items():
        actual = total_stats.get(stat, 0.0)
        if stat in PERCENT_STATS:
            # total_stats stores percentage values (e.g. 50.0 for 50 %),
            # but constraints are fractions (e.g. 0.5 for 50 %).
            threshold = minimum * 100.0
        else:
            threshold = minimum
        if actual < threshold:
            return False
    return True