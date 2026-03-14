"""
source_aggregator.py
--------------------
Aggregate build data from multiple community sources and compute a consensus
build for a Genshin Impact character.

Consensus rules:
  * An artifact set is *consensus* if ≥ 2 sources list it (or all sources if
    only 1 source is available).
  * A weapon is *popular* if it appears in ≥ 1 source; *consensus* if ≥ 2.
  * Stats with the most cross-source agreement are ranked first.
  * Confidence score = (sources agreeing on top artifact / total sources).
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SourceAggregator:
    """Combine raw scraper results into a single consensus build dict."""

    def aggregate(
        self,
        sources: list[dict],
        character_name: str,
    ) -> Optional[dict]:
        """
        Return an aggregated build dict, or None if *sources* is empty.

        Parameters
        ----------
        sources:
            List of dicts returned by :class:`GenshinWebScraper`.
        character_name:
            Human-readable character name (used for labelling only).
        """
        if not sources:
            return None

        n = len(sources)
        consensus_threshold = 2 if n >= 2 else 1

        # ---- Artifact frequency ----------------------------------------
        artifact_counts: dict[str, int] = {}
        for src in sources:
            for art in src.get("artifacts", []):
                artifact_counts[art] = artifact_counts.get(art, 0) + 1

        ranked_artifacts = sorted(artifact_counts.items(), key=lambda x: -x[1])
        consensus_artifacts = [a for a, c in ranked_artifacts if c >= consensus_threshold]
        all_artifacts = [
            {"name": a, "mention_count": c, "sources": _sources_that_mention(sources, "artifacts", a)}
            for a, c in ranked_artifacts
        ]

        # ---- Weapon frequency ------------------------------------------
        weapon_counts: dict[str, int] = {}
        for src in sources:
            for wep in src.get("weapons", []):
                weapon_counts[wep] = weapon_counts.get(wep, 0) + 1

        ranked_weapons = sorted(weapon_counts.items(), key=lambda x: -x[1])
        consensus_weapons = [w for w, c in ranked_weapons if c >= consensus_threshold]
        all_weapons = [
            {"name": w, "mention_count": c, "sources": _sources_that_mention(sources, "weapons", w)}
            for w, c in ranked_weapons
        ]

        # ---- Stat frequency per slot -----------------------------------
        slot_stat_counts: dict[str, dict[str, int]] = {}
        for src in sources:
            for slot, stat_list in src.get("stats", {}).items():
                if slot not in slot_stat_counts:
                    slot_stat_counts[slot] = {}
                for stat in stat_list:
                    slot_stat_counts[slot][stat] = slot_stat_counts[slot].get(stat, 0) + 1

        # Build ranked stat lists per slot
        consensus_stats: dict[str, list[str]] = {}
        for slot, counts in slot_stat_counts.items():
            ranked = sorted(counts.items(), key=lambda x: -x[1])
            consensus_stats[slot] = [s for s, _ in ranked]

        # ---- Confidence score ------------------------------------------
        if ranked_artifacts:
            top_count = ranked_artifacts[0][1]
            confidence = round(top_count / n, 2)
        else:
            confidence = 0.0

        # ---- Conflict detection ----------------------------------------
        conflicts = _detect_conflicts(sources)

        source_labels = [s.get("source", "Unknown") for s in sources]
        source_urls = [s.get("source_url", "") for s in sources]

        return {
            "character": character_name,
            "sources_used": source_labels,
            "source_urls": source_urls,
            "total_sources": n,
            "consensus": bool(consensus_artifacts or consensus_weapons),
            "confidence": confidence,
            # Primary recommendations (consensus or best available)
            "artifacts": consensus_artifacts or [a for a, _ in ranked_artifacts[:4]],
            "weapons": consensus_weapons or [w for w, _ in ranked_weapons[:5]],
            "stats": consensus_stats,
            # Full frequency data (for transparency)
            "all_artifacts": all_artifacts,
            "all_weapons": all_weapons,
            # Conflict info
            "conflicts": conflicts,
            # Raw notes from each source
            "notes": _merge_notes(sources),
        }

    def format_for_prompt(self, build: dict) -> str:
        """
        Return a compact text block suitable for injection into an AI prompt.
        """
        if not build:
            return ""

        lines: list[str] = []
        char = build.get("character", "this character")
        sources = build.get("sources_used", [])
        n = build.get("total_sources", len(sources))

        lines.append(f"=== COMMUNITY BUILD DATA FOR {char.upper()} ===")
        lines.append(f"Sources consulted ({n}): {', '.join(sources)}")
        lines.append(f"Consensus confidence: {int(build.get('confidence', 0) * 100)}%")
        lines.append("")

        artifacts = build.get("artifacts", [])
        if artifacts:
            lines.append("RECOMMENDED ARTIFACT SETS:")
            for art in artifacts[:4]:
                # Show how many sources agree
                all_arts = {a["name"]: a["mention_count"] for a in build.get("all_artifacts", [])}
                count = all_arts.get(art, 1)
                agreement = f"{count}/{n} sources" if n > 1 else "recommended"
                lines.append(f"  • {art}  [{agreement}]")

        weapons = build.get("weapons", [])
        if weapons:
            lines.append("")
            lines.append("RECOMMENDED WEAPONS:")
            all_weps = {w["name"]: w["mention_count"] for w in build.get("all_weapons", [])}
            for wep in weapons[:5]:
                count = all_weps.get(wep, 1)
                agreement = f"{count}/{n} sources" if n > 1 else "recommended"
                lines.append(f"  • {wep}  [{agreement}]")

        stats = build.get("stats", {})
        if stats:
            lines.append("")
            lines.append("STAT PRIORITIES:")
            slot_order = ["sands", "goblet", "circlet", "substats"]
            for slot in slot_order:
                stat_list = stats.get(slot, [])
                if stat_list:
                    lines.append(f"  {slot.capitalize()}: {' / '.join(stat_list)}")

        conflicts = build.get("conflicts", [])
        if conflicts:
            lines.append("")
            lines.append("NOTE (sources disagree on):")
            for c in conflicts[:3]:
                lines.append(f"  • {c}")

        notes = build.get("notes", "")
        if notes:
            lines.append("")
            lines.append(f"GUIDE NOTES: {notes[:300]}")

        lines.append("=== END COMMUNITY BUILD DATA ===")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sources_that_mention(
    sources: list[dict], field: str, item: str
) -> list[str]:
    """Return source labels that include *item* in their *field* list."""
    return [
        s.get("source", "Unknown")
        for s in sources
        if item in s.get(field, [])
    ]


def _detect_conflicts(sources: list[dict]) -> list[str]:
    """
    Flag simple conflicts where sources strongly disagree on artifact sets.

    Currently checks: if source A lists an artifact that source B never
    mentions *and* source B lists a different artifact not in source A.
    Returns human-readable conflict strings.
    """
    if len(sources) < 2:
        return []

    conflicts: list[str] = []
    all_sets = [set(s.get("artifacts", [])) for s in sources]

    # Artifacts unique to only one source (possible conflict)
    union = set().union(*all_sets)
    for art in union:
        mentioning = sum(1 for s in all_sets if art in s)
        if mentioning == 1 and len(sources) >= 3:
            src_name = next(
                s.get("source", "?") for s in sources if art in s.get("artifacts", [])
            )
            conflicts.append(f"{art} (only {src_name} recommends this)")

    return conflicts[:5]


def _merge_notes(sources: list[dict]) -> str:
    """Combine guide notes from all sources."""
    parts = []
    for src in sources:
        note = src.get("notes", "")
        if note:
            parts.append(f"[{src.get('source', '?')}] {note[:200]}")
    return "\n".join(parts)[:800]
