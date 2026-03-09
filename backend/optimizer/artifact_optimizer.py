"""
Main artifact optimizer that orchestrates data fetching and optimization.

Pulls player artifact data via the existing EnkaService, converts it to
the optimizer's internal Artifact model, and delegates to the solver.
"""

import logging
from typing import Any, Dict, List, Optional

from api.enka_service import EnkaService

from .calculator import get_default_weights
from .models import Artifact, Build, Substat
from .solver import optimize
from .utils import ARTIFACT_SLOTS

logger = logging.getLogger(__name__)


class ArtifactOptimizer:
    """
    High-level artifact optimiser.

    Usage::

        optimizer = ArtifactOptimizer(enka_service)
        builds = await optimizer.optimize(uid, character, target_stats, constraints)
    """

    def __init__(self, enka_service: EnkaService) -> None:
        self._enka = enka_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def optimize(
        self,
        uid: str,
        character: str,
        target_stats: Optional[Dict[str, float]] = None,
        constraints: Optional[Dict[str, float]] = None,
        top_n: int = 5,
        allow_equipped: bool = True,
    ) -> List[Build]:
        """
        Return the top *top_n* builds for *character* using the artifacts
        visible in the player's Enka showcase.

        Parameters
        ----------
        uid:
            Genshin Impact UID.
        character:
            Character name (e.g. "Ganyu").
        target_stats:
            Stat weights; if None the character's default weights are used.
        constraints:
            Minimum stat requirements (fractions, e.g. ``{"Crit Rate": 0.5}``).
        top_n:
            Number of builds to return.
        allow_equipped:
            If True (default), consider artifacts equipped on any character.
            If False, skip artifacts equipped on characters other than the target.
        """
        account = await self._enka.fetch_account(uid)
        artifacts = self._collect_artifacts(account, character, allow_equipped)

        if not artifacts:
            logger.warning(f"No artifacts found for UID {uid}")
            return []

        if target_stats is None:
            target_stats = get_default_weights(character)

        return optimize(
            character=character,
            artifacts=artifacts,
            target_stats=target_stats,
            constraints=constraints,
            top_n=top_n,
        )

    async def recommend_build(self, uid: str, character: str) -> Optional[Build]:
        """
        Return the single best build for *character* using default stat weights.
        """
        builds = await self.optimize(uid, character, top_n=1)
        return builds[0] if builds else None

    async def optimize_team(
        self, uid: str, team_characters: List[str]
    ) -> Dict[str, Optional[Build]]:
        """
        Optimise each character in *team_characters* independently.

        Artifacts are shared across all characters in the showcase but each
        character is optimised using its own default weights.
        """
        account = await self._enka.fetch_account(uid)
        results: Dict[str, Optional[Build]] = {}

        for character in team_characters:
            artifacts = self._collect_artifacts(account, character, allow_equipped=True)
            if not artifacts:
                results[character] = None
                continue
            weights = get_default_weights(character)
            builds = optimize(character=character, artifacts=artifacts, target_stats=weights, top_n=1)
            results[character] = builds[0] if builds else None

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_artifacts(
        self,
        account: Dict[str, Any],
        target_character: str,
        allow_equipped: bool,
    ) -> List[Artifact]:
        """
        Extract all artifacts from every character in the Enka showcase.

        Parameters
        ----------
        account:
            Parsed account dict from :meth:`EnkaService.fetch_account`.
        target_character:
            The character we're optimising for.
        allow_equipped:
            Whether to include artifacts equipped on *other* characters.
        """
        all_artifacts: List[Artifact] = []
        seen_keys: set = set()

        for char_data in account.get("characters", []):
            char_name: str = char_data.get("name", "")
            is_target = char_name.lower() == target_character.lower()

            for raw_art in char_data.get("artifacts", []):
                if not allow_equipped and not is_target:
                    continue

                artifact = self._parse_artifact(raw_art, equipped_by=char_name)
                if artifact is None:
                    continue

                # Deduplicate artifacts (same slot + level + main stat + substats)
                key = (
                    artifact.slot,
                    artifact.level,
                    artifact.main_stat,
                    artifact.main_stat_value,
                    tuple(
                        (s.name, s.value) for s in sorted(artifact.substats, key=lambda s: s.name)
                    ),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_artifacts.append(artifact)

        return all_artifacts

    @staticmethod
    def _parse_artifact(raw: Dict[str, Any], equipped_by: str = "") -> Optional[Artifact]:
        """Convert a raw Enka artifact dict to an :class:`Artifact` model."""
        slot = raw.get("slot", "")
        if slot not in ARTIFACT_SLOTS:
            return None

        substats = [
            Substat(name=s.get("name", ""), value=float(s.get("value", 0.0)))
            for s in raw.get("substats", [])
            if s.get("name")
        ]

        return Artifact(
            slot=slot,
            set_name=raw.get("set_name", ""),
            icon=raw.get("icon", ""),
            rarity=int(raw.get("rarity") or 5),
            level=int(raw.get("level") or 0),
            main_stat=raw.get("main_stat", ""),
            main_stat_value=float(raw.get("main_stat_value") or 0.0),
            substats=substats,
            equipped_by=equipped_by,
        )
