"""
Genshin Impact artifact optimizer module.

Provides optimization of artifact builds for characters based on
target stats and player-owned artifacts from Enka.Network data.
"""

from .artifact_optimizer import ArtifactOptimizer
from .models import (
    Artifact,
    Build,
    OptimizationRequest,
    RecommendBuildRequest,
    TeamOptimizeRequest,
)

__all__ = [
    "ArtifactOptimizer",
    "Artifact",
    "Build",
    "OptimizationRequest",
    "RecommendBuildRequest",
    "TeamOptimizeRequest",
]
