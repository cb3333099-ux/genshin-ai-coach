"""
web_scraper.py
--------------
Fetches Genshin Impact character build data from trusted community sources:
  - Keqing Mains (keqingmains.com)
  - Genshin Impact Fandom Wiki (genshin-impact.fandom.com)
  - Honey Hunter World (honeyhunterworld.com)

All methods are async and handle errors gracefully so that a failure in one
source never blocks others.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known artifact set names (game metadata – not character-specific advice)
# Used to identify artifact recommendations inside guide text.
# ---------------------------------------------------------------------------
KNOWN_ARTIFACT_SETS: list[str] = [
    "Archaic Petra",
    "Blizzard Strayer",
    "Bloodstained Chivalry",
    "Crimson Witch of Flames",
    "Deepwood Memories",
    "Desert Pavilion Chronicle",
    "Echoes of an Offering",
    "Emblem of Severed Fate",
    "Finale of the Deep",
    "Flower of Paradise Lost",
    "Fragment of Harmonic Whimsy",
    "Gilded Dreams",
    "Golden Troupe",
    "Heart of Depth",
    "Husk of Opulent Dreams",
    "Lavawalker",
    "Longing of the Resonant Life",
    "Long Night's Oath",
    "Maiden Beloved",
    "Marechaussee Hunter",
    "Nighttime Whispers in the Echoing Woods",
    "Noblesse Oblige",
    "Obsidian Codex",
    "Ocean-Hued Clam",
    "Pale Flame",
    "Retracing Bolide",
    "Scroll of the Hero of Cinder City",
    "Shimenawa's Reminiscence",
    "Tenacity of the Millelith",
    "Thundering Fury",
    "Thundersoother",
    "Unfinished Reverie",
    "Vermillion Hereafter",
    "Viridescent Venerer",
    "Wanderer's Troupe",
]

# Regex that matches any known artifact set (case-insensitive)
_ARTIFACT_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(s) for s in KNOWN_ARTIFACT_SETS) + r")",
    re.IGNORECASE,
)

# Common stat names used in build guides
_STAT_KEYWORDS: list[str] = [
    "ATK%",
    "HP%",
    "DEF%",
    "Energy Recharge",
    "Elemental Mastery",
    "Crit Rate",
    "CRIT Rate",
    "Crit DMG",
    "CRIT DMG",
    "Healing Bonus",
    "Physical DMG",
    "Anemo DMG",
    "Pyro DMG",
    "Hydro DMG",
    "Cryo DMG",
    "Electro DMG",
    "Dendro DMG",
    "Geo DMG",
]

_STAT_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(s) for s in _STAT_KEYWORDS) + r")",
    re.IGNORECASE,
)

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class GenshinWebScraper:
    """Fetch and parse Genshin Impact build guides from multiple community sources."""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=_HEADERS,
                timeout=_REQUEST_TIMEOUT,
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # Low-level HTTP fetch
    # ------------------------------------------------------------------

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Return the raw HTML of *url*, or None on any error."""
        try:
            session = await self._get_session()
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
                logger.warning("HTTP %s from %s", resp.status, url)
                return None
        except Exception as exc:
            logger.warning("Could not fetch %s: %s", url, exc)
            return None

    # ------------------------------------------------------------------
    # Per-source scrapers
    # ------------------------------------------------------------------

    async def scrape_kqm(self, character_name: str) -> Optional[dict]:
        """Scrape Keqing Mains guide for *character_name*."""
        slug = _to_slug(character_name)
        url = f"https://keqingmains.com/{slug}/"
        html = await self._fetch_html(url)
        if not html:
            return None
        return self._parse_generic(
            html,
            character_name,
            source_label="Keqing Mains",
            source_url=url,
        )

    async def scrape_fandom(self, character_name: str) -> Optional[dict]:
        """Scrape Genshin Impact Fandom Wiki builds page for *character_name*."""
        wiki_name = character_name.replace(" ", "_")
        url = f"https://genshin-impact.fandom.com/wiki/{wiki_name}/Builds"
        html = await self._fetch_html(url)
        if not html:
            return None
        return self._parse_generic(
            html,
            character_name,
            source_label="Genshin Impact Wiki (Fandom)",
            source_url=url,
        )

    async def scrape_honey_hunter(self, character_name: str) -> Optional[dict]:
        """Scrape Honey Hunter World for *character_name*."""
        slug = character_name.lower().replace(" ", "").replace("'", "").replace("-", "")
        url = f"https://honeyhunterworld.com/{slug}/"
        html = await self._fetch_html(url)
        if not html:
            return None
        return self._parse_generic(
            html,
            character_name,
            source_label="Honey Hunter World",
            source_url=url,
        )

    # ------------------------------------------------------------------
    # Generic HTML parser
    # ------------------------------------------------------------------

    def _parse_generic(
        self,
        html: str,
        character_name: str,
        source_label: str,
        source_url: str,
    ) -> Optional[dict]:
        """Parse any guide HTML into a structured build dict."""
        try:
            soup = BeautifulSoup(html, "lxml")

            # Remove navigation, footer, and sidebar noise
            for tag in soup.find_all(["nav", "footer", "aside", "script", "style"]):
                tag.decompose()

            full_text = soup.get_text(" ", strip=True)

            artifacts = self._extract_artifacts(full_text)
            weapons = self._extract_weapons(soup, full_text)
            stats = self._extract_stats(full_text)
            notes = self._extract_notes(soup)

            if not artifacts and not weapons and not stats:
                logger.info(
                    "%s: no build data found for %s", source_label, character_name
                )
                return None

            return {
                "source": source_label,
                "source_url": source_url,
                "character": character_name,
                "artifacts": artifacts,
                "weapons": weapons,
                "stats": stats,
                "notes": notes,
            }
        except Exception as exc:
            logger.warning("%s parse error for %s: %s", source_label, character_name, exc)
            return None

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_artifacts(self, text: str) -> list[str]:
        """Return deduplicated artifact set names found in *text*."""
        found: list[str] = []
        seen: set[str] = set()
        for match in _ARTIFACT_PATTERN.finditer(text):
            name = _canonical_artifact_name(match.group(0))
            if name not in seen:
                seen.add(name)
                found.append(name)
        return found

    def _extract_weapons(self, soup: BeautifulSoup, text: str) -> list[str]:
        """
        Extract weapon names from the guide.

        Strategy:
          1. Look for list items or table cells that appear inside a section
             whose heading contains "weapon".
          2. Fall back to looking for bold/italic text near the word "weapon".
          3. As a last resort, scan for capitalised multi-word phrases that
             follow a weapons-related keyword.
        """
        weapons: list[str] = []

        # Strategy 1: heading-based extraction
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            heading_text = heading.get_text(strip=True).lower()
            if "weapon" not in heading_text:
                continue
            # Collect list items and table rows after this heading
            sibling = heading.next_sibling
            for _ in range(30):  # limit look-ahead
                if sibling is None:
                    break
                if isinstance(sibling, Tag):
                    if sibling.name and re.match(r"^h[1-6]$", sibling.name):
                        break  # next section – stop
                    for item in sibling.find_all(["li", "td", "strong", "b"]):
                        candidate = item.get_text(strip=True)
                        weapon = _clean_weapon_candidate(candidate)
                        if weapon and weapon not in weapons:
                            weapons.append(weapon)
                sibling = getattr(sibling, "next_sibling", None)

        # Strategy 2: bold text near "weapon"
        if not weapons:
            pattern = re.compile(r"weapon[s]?\s*[:\-–—]?\s*([A-Z][^\n.]{3,50})", re.IGNORECASE)
            for m in pattern.finditer(text):
                candidate = _clean_weapon_candidate(m.group(1))
                if candidate and candidate not in weapons:
                    weapons.append(candidate)

        return weapons[:10]  # cap at 10

    def _extract_stats(self, text: str) -> dict[str, list[str]]:
        """
        Extract stat priority per artifact slot (Sands, Goblet, Circlet)
        and substat priorities.
        """
        stats: dict[str, list[str]] = {}

        # Look for slot-specific stat mentions
        slot_patterns = {
            "sands": re.compile(
                r"sands?\s*[:\-–—]?\s*([^\n]{0,80})", re.IGNORECASE
            ),
            "goblet": re.compile(
                r"goblet\s*[:\-–—]?\s*([^\n]{0,80})", re.IGNORECASE
            ),
            "circlet": re.compile(
                r"circlet\s*[:\-–—]?\s*([^\n]{0,80})", re.IGNORECASE
            ),
            "substats": re.compile(
                r"substat[s]?\s*[:\-–—]?\s*([^\n]{0,120})", re.IGNORECASE
            ),
        }
        for slot, pattern in slot_patterns.items():
            matches = pattern.findall(text)
            if matches:
                # Extract only recognised stat keywords from the matched text
                found = []
                for m in matches[:3]:
                    for stat in _STAT_PATTERN.findall(m):
                        canonical = _canonical_stat(stat)
                        if canonical not in found:
                            found.append(canonical)
                if found:
                    stats[slot] = found

        return stats

    def _extract_notes(self, soup: BeautifulSoup) -> str:
        """Return a short excerpt from the guide's introductory paragraphs."""
        paragraphs = soup.find_all("p")
        parts = []
        for p in paragraphs[:5]:
            t = p.get_text(strip=True)
            if len(t) > 40:  # skip trivially short paragraphs
                parts.append(t)
            if len(" ".join(parts)) > 500:
                break
        return " ".join(parts)[:500]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def scrape_all(self, character_name: str) -> list[dict]:
        """
        Scrape all sources concurrently and return a list of successful results.
        Failures in individual sources are silently dropped.
        """
        tasks = [
            self.scrape_kqm(character_name),
            self.scrape_fandom(character_name),
            self.scrape_honey_hunter(character_name),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    def build_consensus(self, sources: list[dict]) -> dict:
        """
        Build a consensus build from multiple source dicts.

        An item is *consensus* if it appears in 2+ sources.
        Confidence = (number of sources agreeing) / (total sources).
        """
        if not sources:
            return {"consensus": False, "sources_used": [], "artifacts": [], "weapons": [], "stats": {}}

        all_artifacts: dict[str, int] = {}
        all_weapons: dict[str, int] = {}
        all_stats: dict[str, dict[str, int]] = {}

        for src in sources:
            for art in src.get("artifacts", []):
                all_artifacts[art] = all_artifacts.get(art, 0) + 1
            for wep in src.get("weapons", []):
                all_weapons[wep] = all_weapons.get(wep, 0) + 1
            for slot, stat_list in src.get("stats", {}).items():
                if slot not in all_stats:
                    all_stats[slot] = {}
                for stat in stat_list:
                    all_stats[slot][stat] = all_stats[slot].get(stat, 0) + 1

        n = len(sources)
        consensus_threshold = max(1, n - 1)  # mentioned by at least (n-1) sources

        consensus_artifacts = [
            art for art, cnt in sorted(all_artifacts.items(), key=lambda x: -x[1])
            if cnt >= consensus_threshold
        ]
        popular_artifacts = sorted(all_artifacts.items(), key=lambda x: -x[1])

        consensus_weapons = [
            wep for wep, cnt in sorted(all_weapons.items(), key=lambda x: -x[1])
            if cnt >= consensus_threshold
        ]
        popular_weapons = sorted(all_weapons.items(), key=lambda x: -x[1])

        consensus_stats: dict[str, list[str]] = {}
        for slot, stat_counts in all_stats.items():
            agreed = [s for s, c in sorted(stat_counts.items(), key=lambda x: -x[1]) if c >= consensus_threshold]
            if agreed:
                consensus_stats[slot] = agreed

        return {
            "consensus": bool(consensus_artifacts or consensus_weapons),
            "sources_used": [s["source"] for s in sources],
            "source_urls": [s.get("source_url", "") for s in sources],
            "artifacts": consensus_artifacts or [a for a, _ in popular_artifacts[:4]],
            "all_artifacts": popular_artifacts,
            "weapons": consensus_weapons or [w for w, _ in popular_weapons[:5]],
            "all_weapons": popular_weapons,
            "stats": consensus_stats or {
                slot: list(stat_counts.keys())[:3]
                for slot, stat_counts in all_stats.items()
            },
            "notes": _merge_notes(sources),
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _to_slug(name: str) -> str:
    """Convert a character name to a URL-safe slug."""
    return name.lower().replace(" ", "-").replace("'", "").replace(".", "")


def _canonical_artifact_name(raw: str) -> str:
    """Return the canonical capitalisation of an artifact set name."""
    raw_lower = raw.lower()
    for known in KNOWN_ARTIFACT_SETS:
        if known.lower() == raw_lower:
            return known
    return raw


def _canonical_stat(raw: str) -> str:
    """Normalise stat name capitalisation."""
    mapping = {
        "atk%": "ATK%",
        "hp%": "HP%",
        "def%": "DEF%",
        "energy recharge": "Energy Recharge",
        "elemental mastery": "Elemental Mastery",
        "crit rate": "Crit Rate",
        "crit dmg": "Crit DMG",
        "healing bonus": "Healing Bonus",
        "physical dmg": "Physical DMG Bonus",
        "anemo dmg": "Anemo DMG Bonus",
        "pyro dmg": "Pyro DMG Bonus",
        "hydro dmg": "Hydro DMG Bonus",
        "cryo dmg": "Cryo DMG Bonus",
        "electro dmg": "Electro DMG Bonus",
        "dendro dmg": "Dendro DMG Bonus",
        "geo dmg": "Geo DMG Bonus",
    }
    return mapping.get(raw.lower(), raw)


def _clean_weapon_candidate(text: str) -> str:
    """
    Clean up a potential weapon name extracted from guide text.

    Returns an empty string if the candidate does not look like a weapon name.
    """
    # Strip surrounding whitespace / punctuation
    text = re.sub(r"^[\s\W]+|[\s\W]+$", "", text)
    text = re.sub(r"\s{2,}", " ", text)

    # Must start with an uppercase letter and be between 4 and 60 chars
    if not text or not text[0].isupper() or not (4 <= len(text) <= 60):
        return ""

    # Skip obviously non-weapon phrases
    skip_words = {
        "note", "notes", "see", "also", "refer", "chapter",
        "recommended", "best", "good", "use", "these",
    }
    if text.lower().split()[0] in skip_words:
        return ""

    return text


def _merge_notes(sources: list[dict]) -> str:
    """Combine notes from all sources into a single excerpt."""
    parts = []
    for src in sources:
        note = src.get("notes", "")
        if note:
            parts.append(f"[{src['source']}] {note}")
    return "\n\n".join(parts)[:1000]
