"""
Artifact Optimizer Module for Genshin AI Coach.

Provides stat calculation, artifact combination search, and build scoring
inspired by genshin-optimizer logic.
"""

from .models import Artifact, Substat, Weapon, Build, OptimizationRequest
from .calculator import calculate_character_stats, apply_artifact_set_bonus, calculate_build_score
from .solver import optimize_artifacts, generate_artifact_combinations
from .constraints import filter_artifacts_by_constraints

__all__ = [
    "Artifact",
    "Substat",
    "Weapon",
    "Build",
    "OptimizationRequest",
    "calculate_character_stats",
    "apply_artifact_set_bonus",
    "calculate_build_score",
    "optimize_artifacts",
    "generate_artifact_combinations",
    "filter_artifacts_by_constraints",
]