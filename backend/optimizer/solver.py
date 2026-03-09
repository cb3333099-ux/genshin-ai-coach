"""
Optimization solver for the artifact optimizer.

Algorithm:
1. Group available artifacts by slot.
2. Pre-score every artifact so that cheap per-artifact comparisons drive pruning.
3. Keep the top K candidates per slot (reduces search space to K^5 combinations).
4. Evaluate all remaining combinations and apply stat-constraint filtering.
5. Return the top N builds by total score.

This approach gives near-optimal results for typical player inventories without
the combinatorial explosion of an exhaustive search.
"""

import itertools
import logging
from typing import Dict, List, Optional, Tuple

from .models import Artifact, Build
from .calculator import (
    aggregate_stats,
    get_default_weights,
    score_artifact,
    score_mainstat,
)
from .utils import ARTIFACT_SLOTS, normalize_stat_name, normalize_target_stats

logger = logging.getLogger(__name__)

# Maximum candidates per slot kept before full combination enumeration.
_CANDIDATES_PER_SLOT = 10


def optimize(
    character: str,
    artifacts: List[Artifact],
    target_stats: Optional[Dict[str, float]] = None,
    constraints: Optional[Dict[str, float]] = None,
    top_n: int = 5,
) -> List[Build]:
    """
    Find the top N artifact builds for *character* from the available *artifacts*.

    Parameters
    ----------
    character:
        Name of the character to optimise for.
    artifacts:
        All artifacts available for consideration.
    target_stats:
        Stat weights (higher = more important).  Uses character defaults when empty.
    constraints:
        Minimum required stat values (percentage stats expressed as 0–1,
        e.g. ``{"Crit Rate": 0.5}`` for ≥ 50 % crit rate).
    top_n:
        Number of builds to return.

    Returns
    -------
    List of :class:`Build` objects sorted best-first.
    """
    weights = target_stats if target_stats else get_default_weights(character)
    norm_weights = normalize_target_stats(weights)
    constraints = {normalize_stat_name(k): v for k, v in (constraints or {}).items()}

    # Group artifacts by slot
    by_slot: Dict[str, List[Artifact]] = {slot: [] for slot in ARTIFACT_SLOTS}
    for art in artifacts:
        slot = art.slot
        if slot in by_slot:
            by_slot[slot].append(art)

    # Pre-score each artifact (substats + main stat contribution)
    def _total_score(art: Artifact) -> float:
        return score_artifact(art, norm_weights) + score_mainstat(art, norm_weights)

    # Keep top K candidates per slot to limit enumeration
    slot_candidates: List[List[Optional[Artifact]]] = []
    for slot in ARTIFACT_SLOTS:
        candidates = sorted(by_slot[slot], key=_total_score, reverse=True)
        # Pad with None to allow "empty slot" in partial builds
        candidates = candidates[:_CANDIDATES_PER_SLOT]
        if not candidates:
            candidates = [None]  # empty slot allowed
        slot_candidates.append(candidates)

    # Enumerate all combinations
    builds: List[Tuple[float, Dict[str, float], Dict[str, Optional[Artifact]], Dict[str, float]]] = []
    for combo in itertools.product(*slot_candidates):
        slot_dict: Dict[str, Optional[Artifact]] = {
            slot: art for slot, art in zip(ARTIFACT_SLOTS, combo)
        }
        filled = [a for a in combo if a is not None]
        total_stats = aggregate_stats(filled)

        # Apply constraints
        if not _satisfies_constraints(total_stats, constraints):
            continue

        build_score = sum(_total_score(a) for a in filled)
        score_breakdown = {
            slot: round(_total_score(a), 6) if a else 0.0
            for slot, a in slot_dict.items()
        }

        builds.append((build_score, total_stats, slot_dict, score_breakdown))

    # Sort best-first, take top N
    builds.sort(key=lambda x: x[0], reverse=True)
    best = builds[:top_n]

    result: List[Build] = []
    for build_score, total_stats, slot_dict, score_breakdown in best:
        result.append(
            Build(
                character=character,
                artifacts=slot_dict,
                total_stats=total_stats,
                score=round(build_score, 6),
                score_breakdown=score_breakdown,
            )
        )

    logger.info(
        f"Optimized {character}: evaluated {_combo_count(slot_candidates)} "
        f"combinations → {len(result)} results returned"
    )
    return result


def _satisfies_constraints(
    total_stats: Dict[str, float], constraints: Dict[str, float]
) -> bool:
    """Return True if *total_stats* meets all minimum *constraints*.

    Constraints for percentage stats (e.g. Crit Rate) are expected as
    fractions (0.5 = 50 %), while ``total_stats`` holds these in percentage
    form (50.0 = 50 %).  The comparison is normalised accordingly.
    Constraints for flat stats (e.g. Elemental Mastery) are compared directly.
    """
    from .utils import PERCENT_STATS

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


def _combo_count(slot_candidates: List[List[Optional[Artifact]]]) -> int:
    total = 1
    for slot in slot_candidates:
        total *= len(slot)
    return total
