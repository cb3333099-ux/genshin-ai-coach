"""
Data models for the artifact optimizer.

These dataclasses and Pydantic models mirror the structures used in genshin-optimizer and the
Enka.Network API response so that data flows naturally between the two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

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


# ---------------------------------------------------------------------------
# Domain Models (Dataclasses - for internal optimizer logic)
# ---------------------------------------------------------------------------

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
class Constraint:
    """A constraint on artifact selection."""

    type: str                        # "set", "main_stat", "min_stat", "max_stat"
    slot: Optional[str] = None       # applies to which slot (None = any)
    value: Optional[str] = None      # set key or stat name
    threshold: Optional[float] = None  # numeric threshold for stat constraints


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


# ---------------------------------------------------------------------------
# Request Models (Pydantic - for API validation)
# ---------------------------------------------------------------------------

class SubstatModel(BaseModel):
    """API model for a single substat."""

    stat: str
    value: float


class ArtifactModel(BaseModel):
    """API model for an artifact."""

    id: str
    slot: str
    set_key: str
    rarity: int = 5
    level: int = 20
    main_stat: str = ""
    main_stat_value: float = 0.0
    substats: List[SubstatModel] = []
    equipped_by: str = ""  # The character this artifact is currently equipped on (empty = unequipped)


class WeaponModel(BaseModel):
    """API model for a weapon."""

    key: str
    level: int = 90
    ascension: int = 6
    refinement: int = 1
    base_atk: float = 0.0
    sub_stat: str = ""
    sub_stat_value: float = 0.0


class ConstraintModel(BaseModel):
    """API model for a constraint."""

    type: str
    slot: Optional[str] = None
    value: Optional[str] = None
    threshold: Optional[float] = None


class OptimizationRequest(BaseModel):
    """Request body for the /api/optimize endpoint."""

    uid: Optional[str] = None
    character: str
    artifacts: List[ArtifactModel]
    target_stats: Dict[str, float] = Field(
        default={},
        description=(
            "Stat weights to optimise for. "
            "Keys are stat names (e.g. 'Crit Rate', 'Crit DMG', 'ATK%', "
            "'HP%', 'DEF%', 'Elemental Mastery', 'Energy Recharge'). "
            "Values are the importance weights (higher = more important)."
        ),
    )
    constraints: List[ConstraintModel] = Field(
        default=[],
        description=(
            "Optional constraints on artifact selection. "
            "Example: {'type': 'min_stat', 'value': 'Crit Rate', 'threshold': 0.5}"
        ),
    )
    weapon: Optional[WeaponModel] = None
    buffs: Optional[Dict[str, float]] = None
    top_n: int = Field(default=5, ge=1, le=20)


class RecommendedBuildRequest(BaseModel):
    """Request body for /api/recommended-build."""

    uid: Optional[str] = None
    character: str
    artifacts: List[ArtifactModel]
    weapon: Optional[WeaponModel] = None
    buffs: Optional[Dict[str, float]] = None
    top_n: int = Field(default=5, ge=1, le=20)


class OptimizeTeamRequest(BaseModel):
    """Request body for /api/optimize-team."""

    uid: Optional[str] = None
    team: List[str] = Field(..., min_length=1, max_length=4)
    artifacts_by_character: Dict[str, List[ArtifactModel]]
    target_stats_by_character: Optional[Dict[str, Dict[str, float]]] = None
    weapons_by_character: Optional[Dict[str, WeaponModel]] = None
    buffs_by_character: Optional[Dict[str, Dict[str, float]]] = None
    top_n: int = Field(default=3, ge=1, le=20)