"""
Helper utilities for the artifact optimizer module.

Provides stat-name normalisation so that user-supplied stat keys
(e.g. "Crit Rate", "CRIT_RATE", "crit rate") all map to the same
canonical key used internally and returned by the Enka service.
"""

from typing import Dict

# ---------------------------------------------------------------------------
# Canonical stat names (as returned by the Enka service after normalisation)
# ---------------------------------------------------------------------------
STAT_ALIASES: Dict[str, str] = {
    # Crit
    "crit rate": "Crit Rate",
    "critrate": "Crit Rate",
    "crit_rate": "Crit Rate",
    "cr": "Crit Rate",

    "crit dmg": "Crit Dmg",
    "crit damage": "Crit Dmg",
    "critdmg": "Crit Dmg",
    "crit_dmg": "Crit Dmg",
    "cd": "Crit Dmg",

    # ATK
    "atk": "Atk",
    "attack": "Atk",
    "flat atk": "Atk",
    "flat_atk": "Atk",

    "atk%": "Atk Percent",
    "atk percent": "Atk Percent",
    "atk_percent": "Atk Percent",
    "attack percent": "Atk Percent",
    "attack%": "Atk Percent",

    # HP
    "hp": "Hp",
    "flat hp": "Hp",
    "flat_hp": "Hp",

    "hp%": "Hp Percent",
    "hp percent": "Hp Percent",
    "hp_percent": "Hp Percent",

    # DEF
    "def": "Def",
    "defense": "Def",
    "flat def": "Def",
    "flat_def": "Def",

    "def%": "Def Percent",
    "def percent": "Def Percent",
    "def_percent": "Def Percent",
    "defense percent": "Def Percent",
    "defense%": "Def Percent",

    # Elemental Mastery
    "em": "Elemental Mastery",
    "elemental mastery": "Elemental Mastery",
    "elemental_mastery": "Elemental Mastery",
    "mastery": "Elemental Mastery",

    # Energy Recharge
    "er": "Energy Recharge",
    "energy recharge": "Energy Recharge",
    "energy_recharge": "Energy Recharge",
    "recharge": "Energy Recharge",

    # Elemental DMG
    "physical dmg": "Physical Dmg Bonus",
    "physical_dmg": "Physical Dmg Bonus",
    "phys dmg": "Physical Dmg Bonus",

    "pyro dmg": "Pyro Dmg Bonus",
    "hydro dmg": "Hydro Dmg Bonus",
    "electro dmg": "Electro Dmg Bonus",
    "cryo dmg": "Cryo Dmg Bonus",
    "anemo dmg": "Anemo Dmg Bonus",
    "geo dmg": "Geo Dmg Bonus",
    "dendro dmg": "Dendro Dmg Bonus",

    # Healing
    "healing": "Healing Bonus",
    "healing bonus": "Healing Bonus",
    "healing_bonus": "Healing Bonus",
    "outgoing healing": "Healing Bonus",
}

# Percentage-valued stats (their raw values are fractions, e.g. 0.05 = 5%)
PERCENT_STATS = {
    "Crit Rate",
    "Crit Dmg",
    "Atk Percent",
    "Hp Percent",
    "Def Percent",
    "Energy Recharge",
    "Pyro Dmg Bonus",
    "Hydro Dmg Bonus",
    "Electro Dmg Bonus",
    "Cryo Dmg Bonus",
    "Anemo Dmg Bonus",
    "Geo Dmg Bonus",
    "Dendro Dmg Bonus",
    "Physical Dmg Bonus",
    "Healing Bonus",
}

# Flat-valued stats
FLAT_STATS = {"Atk", "Hp", "Def", "Elemental Mastery"}

# The five artifact slot names used by the Enka service
ARTIFACT_SLOTS = ["Bracer", "Necklace", "Shoes", "Ring", "Dress"]

# Friendly slot names for display
SLOT_DISPLAY_NAMES: Dict[str, str] = {
    "Bracer": "Flower of Life",
    "Necklace": "Plume of Death",
    "Shoes": "Sands of Eon",
    "Ring": "Goblet of Eonothem",
    "Dress": "Circlet of Logos",
}


def normalize_stat_name(stat: str) -> str:
    """
    Normalise a user-supplied stat name to the canonical internal form.

    Examples
    --------
    >>> normalize_stat_name("crit rate")
    'Crit Rate'
    >>> normalize_stat_name("CRIT_RATE")
    'Crit Rate'
    >>> normalize_stat_name("Crit Rate")
    'Crit Rate'
    """
    key = stat.lower().strip().replace("_", " ")
    if key in STAT_ALIASES:
        return STAT_ALIASES[key]
    # Fall back to title-casing the input (handles already-canonical names)
    return stat.replace("_", " ").title()


def normalize_target_stats(target_stats: Dict[str, float]) -> Dict[str, float]:
    """Normalise all keys in a target_stats mapping."""
    return {normalize_stat_name(k): v for k, v in target_stats.items()}


def is_percent_stat(stat_name: str) -> bool:
    """Return True if the stat is stored as a fraction (0–1) in the Enka data."""
    return stat_name in PERCENT_STATS
