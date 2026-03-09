"""
Data models for the artifact optimizer module.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class Substat(BaseModel):
    """A single artifact substat."""

    name: str
    value: float


class Artifact(BaseModel):
    """Represents a single Genshin Impact artifact."""

    slot: str
    set_name: str = ""
    icon: str = ""
    rarity: int = 5
    level: int = 20
    main_stat: str = ""
    main_stat_value: float = 0.0
    substats: List[Substat] = []

    # The character this artifact is currently equipped on (empty = unequipped)
    equipped_by: str = ""


class Build(BaseModel):
    """Represents a complete artifact build (one artifact per slot)."""

    character: str
    artifacts: Dict[str, Optional[Artifact]]
    total_stats: Dict[str, float] = {}
    score: float = 0.0
    score_breakdown: Dict[str, float] = {}


class OptimizationRequest(BaseModel):
    """Request body for the /api/optimizer/optimize endpoint."""

    uid: str
    character: str
    target_stats: Dict[str, float] = Field(
        default={},
        description=(
            "Stat weights to optimise for. "
            "Keys are stat names (e.g. 'Crit Rate', 'Crit Dmg', 'Atk Percent', "
            "'Hp Percent', 'Def Percent', 'Elemental Mastery', 'Energy Recharge'). "
            "Values are the importance weights (higher = more important)."
        ),
    )
    constraints: Dict[str, Any] = Field(
        default={},
        description=(
            "Optional minimum stat requirements. "
            "Example: {'Crit Rate': 0.5} means Crit Rate must be >= 50%."
        ),
    )
    top_n: int = Field(default=5, ge=1, le=20)
    allow_equipped: bool = Field(
        default=True,
        description="If False, skip artifacts already equipped on other characters.",
    )


class RecommendBuildRequest(BaseModel):
    """Request body for /api/optimizer/recommend-build."""

    uid: str
    character: str


class TeamOptimizeRequest(BaseModel):
    """Request body for /api/optimizer/team-optimize."""

    uid: str
    team_characters: List[str] = Field(..., min_length=1, max_length=4)
