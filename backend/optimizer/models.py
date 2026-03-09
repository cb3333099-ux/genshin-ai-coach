"""
Data models for the artifact optimizer.

These dataclasses mirror the structures used in genshin-optimizer and the
Enka.Network API response so that data flows naturally between the two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Artifact slot constants
# ---------------------------------------------------------------------------

SLOTS = ("flower", "plume", "sands", "goblet", "circlet")

# ---------------------------------------------------------------------------
# Stat name constants (matching Enka / genshin-optimizer conventions)
# ---------------------------------------------------------------------------

STAT_HP = "HP"
STAT_HP_PERCENT = "HP%"
STAT_ATK = "ATK"
STAT_ATK_PERCENT = "ATK%"
STAT_DEF = "DEF"
STAT_DEF_PERCENT = "DEF%"
STAT_EM = "Elemental Mastery"
STAT_ER = "Energy Recharge"
STAT_CRIT_RATE = "Crit Rate"
STAT_CRIT_DMG = "Crit DMG"
STAT_HEALING = "Healing Bonus"
STAT_PYRO_DMG = "Pyro DMG Bonus"
STAT_HYDRO_DMG = "Hydro DMG Bonus"
STAT_CRYO_DMG = "Cryo DMG Bonus"
STAT_ELECTRO_DMG = "Electro DMG Bonus"
STAT_ANEMO_DMG = "Anemo DMG Bonus"
STAT_GEO_DMG = "Geo DMG Bonus"
STAT_DENDRO_DMG = "Dendro DMG Bonus"
STAT_PHYSICAL_DMG = "Physical DMG Bonus"


@dataclass
class Substat:
    """A single artifact substat (key + value)."""

    stat: str
    value: float


@dataclass
class Artifact:
    """Represents one artifact piece."""

    id: str
    slot: str                        # flower | plume | sands | goblet | circlet
    set_key: str                     # e.g. "GladiatorsFinale"
    rarity: int                      # 1-5 stars
    level: int                       # 0-20
    main_stat: str                   # e.g. "Crit Rate"
    main_stat_value: float           # absolute value (%, flat, etc.)
    substats: List[Substat] = field(default_factory=list)


@dataclass
class Weapon:
    """Simplified weapon representation."""

    key: str                         # e.g. "AmosBow"
    level: int = 90
    ascension: int = 6
    refinement: int = 1
    base_atk: float = 0.0
    sub_stat: str = ""
    sub_stat_value: float = 0.0


@dataclass
class Build:
    """A complete artifact build for one character."""

    character: str
    artifacts: Dict[str, Artifact]   # slot -> Artifact
    weapon: Optional[Weapon]
    total_score: float
    stat_values: Dict[str, float]    # computed final stats

    def to_dict(self) -> dict:
        return {
            "character": self.character,
            "total_score": round(self.total_score, 4),
            "stat_values": {k: round(v, 4) for k, v in self.stat_values.items()},
            "artifacts": {
                slot: {
                    "id": art.id,
                    "set_key": art.set_key,
                    "slot": art.slot,
                    "rarity": art.rarity,
                    "level": art.level,
                    "main_stat": art.main_stat,
                    "main_stat_value": art.main_stat_value,
                    "substats": [
                        {"stat": s.stat, "value": s.value} for s in art.substats
                    ],
                }
                for slot, art in self.artifacts.items()
            },
            "weapon": {
                "key": self.weapon.key,
                "level": self.weapon.level,
                "base_atk": self.weapon.base_atk,
                "sub_stat": self.weapon.sub_stat,
                "sub_stat_value": self.weapon.sub_stat_value,
            } if self.weapon else None,
        }


@dataclass
class Constraint:
    """A constraint on artifact selection."""

    type: str                        # "set", "main_stat", "min_stat", "max_stat"
    slot: Optional[str] = None       # applies to which slot (None = any)
    value: Optional[str] = None      # set key or stat name
    threshold: Optional[float] = None  # numeric threshold for stat constraints


@dataclass
class OptimizationRequest:
    """Incoming optimization request payload."""

    uid: str
    character: str
    target_stats: Dict[str, float]   # desired stat -> weight
    constraints: List[Constraint] = field(default_factory=list)
    top_n: int = 5
