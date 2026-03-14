"""
character_cache.py
------------------
A file-backed cache for Genshin Impact character build data fetched from
community sources.

TTL: 7 days (604 800 seconds).
Cache location: system temp directory / genshin_build_cache/
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from typing import Optional

from data.web_scraper import GenshinWebScraper
from data.source_aggregator import SourceAggregator

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
_CACHE_DIR = os.path.join(tempfile.gettempdir(), "genshin_build_cache")


class DynamicCharacterCache:
    """
    Cache character build data fetched from web sources.

    * Builds are stored as JSON files in a temp directory.
    * Each entry expires after 7 days.
    * ``force_refresh=True`` bypasses the TTL and re-fetches immediately.
    """

    def __init__(self) -> None:
        self._scraper = GenshinWebScraper()
        self._aggregator = SourceAggregator()
        self._in_progress: set[str] = set()
        os.makedirs(_CACHE_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_character_build(
        self,
        character_name: str,
        force_refresh: bool = False,
    ) -> Optional[dict]:
        """
        Return the consensus build for *character_name*.

        Returns None if all sources fail and no cached data is available.
        """
        key = _cache_key(character_name)

        if not force_refresh:
            cached = self._load_cache(key)
            if cached is not None:
                logger.info("Cache hit for %s", character_name)
                return cached

        # Avoid duplicate concurrent fetches for the same character
        if key in self._in_progress:
            logger.info("Fetch already in progress for %s – waiting", character_name)
            for _ in range(30):
                await asyncio.sleep(1)
                cached = self._load_cache(key)
                if cached is not None:
                    return cached
            return None

        self._in_progress.add(key)
        try:
            return await self._fetch_and_cache(character_name, key)
        finally:
            self._in_progress.discard(key)

    async def close(self) -> None:
        """Clean up the underlying HTTP session."""
        await self._scraper.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_and_cache(
        self, character_name: str, key: str
    ) -> Optional[dict]:
        logger.info("Fetching build data for %s from web sources…", character_name)
        raw_sources = await self._scraper.scrape_all(character_name)
        build = self._aggregator.aggregate(raw_sources, character_name)

        if build is None:
            logger.warning("No build data obtained for %s", character_name)
            return None

        self._save_cache(key, build)
        return build

    # ------------------------------------------------------------------
    # Cache I/O
    # ------------------------------------------------------------------

    def _cache_path(self, key: str) -> str:
        return os.path.join(_CACHE_DIR, f"{key}.json")

    def _load_cache(self, key: str) -> Optional[dict]:
        path = self._cache_path(key)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

        cached_at = data.get("_cached_at", 0)
        age = time.time() - cached_at
        if age > _CACHE_TTL_SECONDS:
            logger.info("Cache expired for key %s (age %.0f s)", key, age)
            return None

        data["_cache_age_hours"] = round(age / 3600, 1)
        return data

    def _save_cache(self, key: str, data: dict) -> None:
        path = self._cache_path(key)
        data["_cached_at"] = time.time()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            logger.info("Build cached for key %s", key)
        except OSError as exc:
            logger.warning("Failed to write cache for %s: %s", key, exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cache_key(character_name: str) -> str:
    """Return a safe filename key for *character_name*."""
    return re.sub(r"[^a-z0-9_]", "_", character_name.lower().strip())
