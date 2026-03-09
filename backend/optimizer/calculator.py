"""
Stat calculator for the artifact optimizer.

Handles:
- Scoring individual artifacts based on substat weights
- Aggregating stats across an artifact set
- Applying artifact set bonuses (simplified)
"""

from typing import Dict, List, Optional

from .models import Artifact, Substat
from .utils import normalize_stat_name, normalize_target_stats, PERCENT_STATS, FLAT_STATS


# ---------------------------------------------------------------------------
# Default stat weights per character archetype / role
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS_BY_ROLE: Dict[str, Dict[str, float]] = {
    "dps": {
        "Crit Rate": 2.0,
        "Crit Dmg": 1.0,
        "Atk Percent": 0.5,
        "Atk": 0.1,
        "Elemental Mastery": 0.2,
        "Energy Recharge": 0.1,
    },
    "sub_dps": {
        "Crit Rate": 1.5,
        "Crit Dmg": 1.0,
        "Atk Percent": 0.5,
        "Elemental Mastery": 0.5,
        "Energy Recharge": 0.3,
    },
    "support": {
        "Hp Percent": 1.0,
        "Hp": 0.05,
        "Energy Recharge": 1.5,
        "Elemental Mastery": 0.5,
        "Crit Rate": 0.3,
    },
    "healer": {
        "Hp Percent": 1.5,
        "Hp": 0.05,
        "Healing Bonus": 2.0,
        "Energy Recharge": 1.0,
        "Def Percent": 0.3,
    },
    "shielder": {
        "Def Percent": 2.0,
        "Def": 0.05,
        "Hp Percent": 0.5,
        "Energy Recharge": 0.5,
    },
    "em_dps": {
        "Elemental Mastery": 3.0,
        "Crit Rate": 0.5,
        "Crit Dmg": 0.5,
        "Energy Recharge": 0.3,
    },
}

# Character → default role mapping (used when no target_stats provided)
CHARACTER_ROLES: Dict[str, str] = {
    "Ganyu": "dps",
    "Hu Tao": "dps",
    "Ayaka": "dps",
    "Kamisato Ayaka": "dps",
    "Raiden Shogun": "sub_dps",
    "Kazuha": "support",
    "Kaedehara Kazuha": "support",
    "Zhongli": "shielder",
    "Bennett": "support",
    "Fischl": "sub_dps",
    "Xingqiu": "sub_dps",
    "Kokomi": "healer",
    "Sangonomiya Kokomi": "healer",
    "Nahida": "em_dps",
    "Sucrose": "em_dps",
    "Venti": "support",
    "Albedo": "sub_dps",
    "Yelan": "sub_dps",
    "Noelle": "shielder",
    "Gorou": "shielder",
    "Diona": "healer",
    "Qiqi": "healer",
    "Barbara": "healer",
    "Klee": "dps",
    "Diluc": "dps",
    "Eula": "dps",
    "Itto": "dps",
    "Arataki Itto": "dps",
    "Wanderer": "dps",
    "Neuvilette": "dps",
    "Furina": "sub_dps",
    "Wriothesley": "dps",
    "Navia": "dps",
    "Arlecchino": "dps",
    "Clorinde": "dps",
    "Citlali": "support",
    "Mavuika": "dps",
}


def get_default_weights(character: str) -> Dict[str, float]:
    """
    Return sensible default stat weights for a character.

    Uses the character role mapping, falling back to generic DPS weights.
    """
    role = CHARACTER_ROLES.get(character, "dps")
    return DEFAULT_WEIGHTS_BY_ROLE.get(role, DEFAULT_WEIGHTS_BY_ROLE["dps"])


def score_artifact(artifact: Artifact, weights: Dict[str, float]) -> float:
    """
    Score a single artifact based on its substats and the provided weights.

    Percentage stats (e.g. Crit Rate = 3.5%) are passed as their raw float
    value (3.5), so we divide by 100 to normalise before applying weights.
    Flat stats are normalised against a typical maximum reference value so
    they are comparable to percentage stats.

    Returns a non-negative float; higher is better.
    """
    score = 0.0
    norm_weights = normalize_target_stats(weights)

    for substat in artifact.substats:
        stat_name = normalize_stat_name(substat.name)
        weight = norm_weights.get(stat_name, 0.0)
        if weight == 0.0:
            continue

        value = substat.value
        # Percentage stats come from Enka as percentages (e.g. 3.5 for 3.5%)
        if stat_name in PERCENT_STATS:
            value = value / 100.0  # normalise to 0–1 range
        elif stat_name in FLAT_STATS:
            # Normalise flat stats: use typical max roll reference values
            value = _normalise_flat(stat_name, value)

        score += weight * value

    return round(score, 6)


def score_mainstat(artifact: Artifact, weights: Dict[str, float]) -> float:
    """Return the weighted score contribution of an artifact's main stat."""
    norm_weights = normalize_target_stats(weights)
    stat_name = normalize_stat_name(artifact.main_stat)
    weight = norm_weights.get(stat_name, 0.0)
    if weight == 0.0:
        return 0.0

    value = artifact.main_stat_value
    if stat_name in PERCENT_STATS:
        value = value / 100.0
    elif stat_name in FLAT_STATS:
        value = _normalise_flat(stat_name, value)

    return round(weight * value, 6)


def _normalise_flat(stat_name: str, value: float) -> float:
    """
    Normalise a flat stat value to a 0–1 range for fair comparison with
    percentage stats.  Reference maxima are approximate max-roll values on a
    5-star +20 artifact.
    """
    ref = {
        "Atk": 311.0,
        "Hp": 4780.0,
        "Def": 58.3,
        "Elemental Mastery": 187.0,
    }
    divisor = ref.get(stat_name, 1.0)
    return value / divisor if divisor else value


def aggregate_stats(artifacts: List[Artifact]) -> Dict[str, float]:
    """
    Sum all substat values across a list of artifacts.

    Percentage stats are summed as percentages (e.g. two 3.5% Crit Rate
    substats give 7.0 in the result dict).  Main stats are NOT included
    here; they can be added separately if needed.
    """
    totals: Dict[str, float] = {}
    for artifact in artifacts:
        for sub in artifact.substats:
            name = normalize_stat_name(sub.name)
            totals[name] = totals.get(name, 0.0) + sub.value
        # Include main stat
        ms = normalize_stat_name(artifact.main_stat)
        if ms:
            totals[ms] = totals.get(ms, 0.0) + artifact.main_stat_value
    return {k: round(v, 4) for k, v in totals.items()}
