"""
Constraint handling for the artifact optimizer.

Constraints allow callers to restrict which artifacts are considered during
optimization, e.g. requiring a specific set, a particular main stat on a
slot, or minimum substat values.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from .models import Artifact, Constraint

logger = logging.getLogger(__name__)


def filter_artifacts_by_constraints(
    artifacts_by_slot: Dict[str, List[Artifact]],
    constraints: List[Constraint],
) -> Dict[str, List[Artifact]]:
    """
    Apply all constraints and return a filtered copy of *artifacts_by_slot*.

    Each constraint specifies:
      - ``type``      : "set" | "main_stat" | "min_stat" | "max_stat"
      - ``slot``      : which slot the constraint applies to (None = all)
      - ``value``     : set key or stat name (string)
      - ``threshold`` : numeric threshold for stat-based constraints
    """
    filtered: Dict[str, List[Artifact]] = {
        slot: list(arts) for slot, arts in artifacts_by_slot.items()
    }

    for constraint in constraints:
        ctype = constraint.type
        cslot = constraint.slot
        cvalue = constraint.value
        cthreshold = constraint.threshold

        if ctype == "set":
            # Require a specific artifact set in the given slot (or all slots)
            filtered = _apply_set_constraint(filtered, cslot, cvalue)

        elif ctype == "main_stat":
            # Require a specific main stat on a slot
            filtered = _apply_main_stat_constraint(filtered, cslot, cvalue)

        elif ctype == "min_stat":
            # Require that an artifact has at least *threshold* of *value* stat
            # (either as main stat or sum of substats)
            filtered = _apply_stat_threshold_constraint(
                filtered, cslot, cvalue, cthreshold, minimum=True
            )

        elif ctype == "max_stat":
            filtered = _apply_stat_threshold_constraint(
                filtered, cslot, cvalue, cthreshold, minimum=False
            )

        else:
            logger.warning("Unknown constraint type '%s'; skipping.", ctype)

    return filtered


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_set_constraint(
    artifacts_by_slot: Dict[str, List[Artifact]],
    slot: str | None,
    set_key: str | None,
) -> Dict[str, List[Artifact]]:
    if not set_key:
        return artifacts_by_slot
    result = {}
    for s, arts in artifacts_by_slot.items():
        if slot is None or s == slot:
            result[s] = [a for a in arts if a.set_key == set_key]
        else:
            result[s] = arts
    return result


def _apply_main_stat_constraint(
    artifacts_by_slot: Dict[str, List[Artifact]],
    slot: str | None,
    stat: str | None,
) -> Dict[str, List[Artifact]]:
    if not stat:
        return artifacts_by_slot
    result = {}
    for s, arts in artifacts_by_slot.items():
        if slot is None or s == slot:
            result[s] = [a for a in arts if a.main_stat == stat]
        else:
            result[s] = arts
    return result


def _apply_stat_threshold_constraint(
    artifacts_by_slot: Dict[str, List[Artifact]],
    slot: str | None,
    stat: str | None,
    threshold: float | None,
    *,
    minimum: bool,
) -> Dict[str, List[Artifact]]:
    if not stat or threshold is None:
        return artifacts_by_slot

    def _total_stat(art: Artifact) -> float:
        total = 0.0
        if art.main_stat == stat:
            total += art.main_stat_value
        for sub in art.substats:
            if sub.stat == stat:
                total += sub.value
        return total

    result = {}
    for s, arts in artifacts_by_slot.items():
        if slot is None or s == slot:
            if minimum:
                result[s] = [a for a in arts if _total_stat(a) >= threshold]
            else:
                result[s] = [a for a in arts if _total_stat(a) <= threshold]
        else:
            result[s] = arts
    return result
