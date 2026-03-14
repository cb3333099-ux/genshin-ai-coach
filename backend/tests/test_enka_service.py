"""
Unit tests for EnkaService – specifically the character database loading,
ID resolution, and build analysis features introduced by the live-character-
API integration.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.enka_service import EnkaService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_service() -> EnkaService:
    """Return an EnkaService with an empty class-level cache."""
    EnkaService._character_db = {}
    EnkaService._character_db_loaded_at = 0.0
    return EnkaService()


# ---------------------------------------------------------------------------
# Builtin fallback tests
# ---------------------------------------------------------------------------


class TestBuiltinCharacterFallback:
    def test_returns_dict(self):
        fb = EnkaService._builtin_character_fallback()
        assert isinstance(fb, dict)

    def test_all_values_have_name_and_element(self):
        fb = EnkaService._builtin_character_fallback()
        for char_id, info in fb.items():
            assert "name" in info, f"ID {char_id} missing 'name'"
            assert "element" in info, f"ID {char_id} missing 'element'"
            assert info["name"], f"ID {char_id} has empty name"
            assert info["element"], f"ID {char_id} has empty element"

    def test_known_characters_present(self):
        fb = EnkaService._builtin_character_fallback()
        expected = {
            10000022: "Venti",
            10000046: "Hu Tao",
            10000052: "Raiden Shogun",
            10000073: "Nahida",
            10000087: "Neuvillette",
            10000096: "Arlecchino",
            10000106: "Mavuika",
            10000121: "Aino",    # most recently confirmed new character
        }
        for char_id, name in expected.items():
            assert char_id in fb, f"Character ID {char_id} ({name}) missing from fallback"
            assert fb[char_id]["name"] == name, (
                f"ID {char_id}: expected '{name}', got '{fb[char_id]['name']}'"
            )

    def test_no_placeholder_names(self):
        """None of the builtin entries should use a 'Character <id>' placeholder."""
        fb = EnkaService._builtin_character_fallback()
        for char_id, info in fb.items():
            name = info.get("name", "")
            assert not name.startswith("Character "), (
                f"ID {char_id} has placeholder name '{name}'"
            )

    def test_elements_are_valid(self):
        valid_elements = {"Pyro", "Hydro", "Anemo", "Electro", "Dendro", "Cryo", "Geo"}
        fb = EnkaService._builtin_character_fallback()
        for char_id, info in fb.items():
            el = info.get("element", "")
            assert el in valid_elements, (
                f"ID {char_id} ({info.get('name')}) has unrecognised element '{el}'"
            )


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------


class TestNormalizeName:
    def test_lowercase(self):
        assert EnkaService._normalize_name("Venti") == "venti"

    def test_removes_spaces(self):
        assert EnkaService._normalize_name("Hu Tao") == "hutao"

    def test_removes_spaces_and_apostrophes(self):
        assert EnkaService._normalize_name("Yun Jin") == "yunjin"
        assert EnkaService._normalize_name("Kuki Shinobu") == "kukishinobu"
        # Verify apostrophe removal (e.g. player nicknames like "O'Brien")
        assert EnkaService._normalize_name("O'Brien") == "obrien"

    def test_removes_hyphens(self):
        assert EnkaService._normalize_name("Kujou Sara") == "kujousara"

    def test_removes_dots(self):
        assert EnkaService._normalize_name("A.E.R.") == "aer"

    def test_complex_name(self):
        assert EnkaService._normalize_name("Sangonomiya Kokomi") == "sangonomiyakokomi"
        assert EnkaService._normalize_name("Kaedehara Kazuha") == "kaedeharakazuha"


# ---------------------------------------------------------------------------
# Character name/element resolution
# ---------------------------------------------------------------------------


class TestGetCharInfo:
    def setup_method(self):
        self.service = _fresh_service()
        # Populate the class-level DB with the builtin fallback
        EnkaService._character_db = dict(EnkaService._builtin_character_fallback())

    def test_known_id_returns_name(self):
        assert self.service._get_char_name(10000022) == "Venti"
        assert self.service._get_char_name(10000046) == "Hu Tao"

    def test_known_id_returns_element(self):
        assert self.service._get_char_element(10000022) == "Anemo"
        assert self.service._get_char_element(10000046) == "Pyro"

    def test_unknown_id_returns_placeholder(self):
        name = self.service._get_char_name(10000999)
        assert "10000999" in name

    def test_none_id_returns_unknown(self):
        assert self.service._get_char_name(None) == "Unknown"
        assert self.service._get_char_element(None) == "Unknown"

    def test_get_char_info_returns_copy(self):
        """Mutating the returned dict must not affect the cached entry."""
        info = self.service._get_char_info(10000022)
        info["name"] = "MUTATED"
        assert EnkaService._character_db[10000022]["name"] == "Venti"

    def test_get_char_info_unknown_id(self):
        info = self.service._get_char_info(10000999)
        assert "10000999" in info["name"]
        assert info["element"] == "Unknown"

    def test_aino_resolves_from_fallback(self):
        """Character 10000121 (Aino) must be in the builtin fallback."""
        assert self.service._get_char_name(10000121) == "Aino"
        assert self.service._get_char_element(10000121) == "Hydro"


# ---------------------------------------------------------------------------
# Ensure character data – merging logic (async tests with mocked APIs)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEnsureCharacterData:
    def setup_method(self):
        _fresh_service()  # Reset class-level caches

    async def test_fallback_used_when_apis_fail(self):
        """All external APIs fail → only builtin fallback entries in DB."""
        service = EnkaService()
        with patch.object(service, "_fetch_enka_characters", new_callable=AsyncMock, return_value={}), \
             patch.object(service, "_load_character_database_from_api", new_callable=AsyncMock, return_value={}), \
             patch.object(service, "_fetch_jmsszkzlz_characters", new_callable=AsyncMock, return_value={}):
            await service._ensure_character_data()

        # Builtin fallback entries must still be present
        assert EnkaService._character_db.get(10000022, {}).get("name") == "Venti"
        assert EnkaService._character_db.get(10000121, {}).get("name") == "Aino"

    async def test_enka_adds_new_ids(self):
        """New character IDs from Enka should be merged into the DB."""
        service = EnkaService()
        enka_stub = {
            10000200: {"name": "FutureChar", "element": "Pyro"},
        }
        with patch.object(service, "_fetch_enka_characters", new_callable=AsyncMock, return_value=enka_stub), \
             patch.object(service, "_load_character_database_from_api", new_callable=AsyncMock, return_value={}), \
             patch.object(service, "_fetch_jmsszkzlz_characters", new_callable=AsyncMock, return_value={}):
            await service._ensure_character_data()

        assert EnkaService._character_db.get(10000200, {}).get("name") == "FutureChar"
        # Existing fallback entries must still be present
        assert EnkaService._character_db.get(10000022, {}).get("name") == "Venti"

    async def test_enka_does_not_override_fallback(self):
        """Enka data should NOT override builtin fallback for known IDs."""
        service = EnkaService()
        enka_stub = {
            10000022: {"name": "WRONG_NAME", "element": "Anemo"},  # Should be ignored
        }
        with patch.object(service, "_fetch_enka_characters", new_callable=AsyncMock, return_value=enka_stub), \
             patch.object(service, "_load_character_database_from_api", new_callable=AsyncMock, return_value={}), \
             patch.object(service, "_fetch_jmsszkzlz_characters", new_callable=AsyncMock, return_value={}):
            await service._ensure_character_data()

        # Builtin fallback wins for ID 10000022
        assert EnkaService._character_db[10000022]["name"] == "Venti"

    async def test_jmsszkzlz_adds_newest_ids(self):
        """jmsszkzlz API entries should fill IDs still missing after Enka pass."""
        service = EnkaService()
        jmsszkzlz_stub = {
            10000126: {"name": "NewCharA", "element": "Pyro"},
            10000127: {"name": "NewCharB", "element": "Cryo"},
        }
        with patch.object(service, "_fetch_enka_characters", new_callable=AsyncMock, return_value={}), \
             patch.object(service, "_load_character_database_from_api", new_callable=AsyncMock, return_value={}), \
             patch.object(service, "_fetch_jmsszkzlz_characters", new_callable=AsyncMock, return_value=jmsszkzlz_stub):
            await service._ensure_character_data()

        assert EnkaService._character_db.get(10000126, {}).get("name") == "NewCharA"
        assert EnkaService._character_db.get(10000127, {}).get("name") == "NewCharB"

    async def test_cache_prevents_refetch(self):
        """Once populated, _ensure_character_data should not re-fetch within cache duration."""
        import time
        service = EnkaService()
        EnkaService._character_db = {10000022: {"name": "Venti", "element": "Anemo"}}
        EnkaService._character_db_loaded_at = time.time()  # Fresh cache

        mock_enka = AsyncMock(return_value={})
        with patch.object(service, "_fetch_enka_characters", mock_enka):
            await service._ensure_character_data()

        mock_enka.assert_not_called()

    async def test_placeholder_names_rejected(self):
        """Entries with invalid/placeholder names from external APIs must be ignored."""
        service = EnkaService()
        bad_enka = {
            10000200: {"name": "", "element": "Pyro"},        # empty name
            10000201: {"name": "12", "element": "Hydro"},     # digit-only
            10000202: {"name": "X", "element": "Anemo"},      # too short
        }
        with patch.object(service, "_fetch_enka_characters", new_callable=AsyncMock, return_value=bad_enka), \
             patch.object(service, "_load_character_database_from_api", new_callable=AsyncMock, return_value={}), \
             patch.object(service, "_fetch_jmsszkzlz_characters", new_callable=AsyncMock, return_value={}):
            await service._ensure_character_data()

        # None of the bad entries should have been added
        for bad_id in (10000200, 10000201, 10000202):
            assert bad_id not in EnkaService._character_db, (
                f"ID {bad_id} with invalid name should not be in character DB"
            )


# ---------------------------------------------------------------------------
# Build analysis
# ---------------------------------------------------------------------------


class TestAnalyzeCharacterBuild:
    def setup_method(self):
        self.service = EnkaService()

    def _make_artifact(self, slot, equip_type, set_name, main_stat, substats=None):
        return {
            "slot": slot,
            "equip_type": equip_type,
            "set_name": set_name,
            "icon": "",
            "rarity": 5,
            "level": 20,
            "main_stat": main_stat,
            "main_stat_value": 0,
            "substats": substats or [],
            "sub_stat_count": len(substats or []),
        }

    def test_good_hu_tao_build(self):
        char = {
            "name": "Hu Tao",
            "artifacts": [
                self._make_artifact("Flower", "EQUIP_BRACER", "Crimson Witch of Flames", "HP",
                                    [{"name": "Crit DMG", "value": 20}, {"name": "Crit Rate", "value": 10},
                                     {"name": "HP%", "value": 5}, {"name": "Elemental Mastery", "value": 40}]),
                self._make_artifact("Feather", "EQUIP_NECKLACE", "Crimson Witch of Flames", "ATK",
                                    [{"name": "Crit DMG", "value": 15}, {"name": "Crit Rate", "value": 7}]),
                self._make_artifact("Sands", "EQUIP_SHOES", "Crimson Witch of Flames", "HP%",
                                    [{"name": "Crit DMG", "value": 12}]),
                self._make_artifact("Goblet", "EQUIP_RING", "Crimson Witch of Flames", "Pyro DMG Bonus",
                                    [{"name": "Crit Rate", "value": 9}]),
                self._make_artifact("Circlet", "EQUIP_DRESS", "Crimson Witch of Flames", "Crit DMG",
                                    [{"name": "HP%", "value": 5}]),
            ],
        }
        result = self.service.analyze_character_build(char)
        assert result["grade"] in ("Excellent", "Good")
        assert result["set_score"] > 0
        assert result["main_stat_score"] > 0
        assert result["total_score"] > 0
        assert isinstance(result["recommendations"], list)

    def test_mixed_sets_score_lower(self):
        char = {
            "name": "Hu Tao",
            "artifacts": [
                self._make_artifact("Flower", "EQUIP_BRACER", "Gladiator's Finale", "HP", []),
                self._make_artifact("Feather", "EQUIP_NECKLACE", "Gladiator's Finale", "ATK", []),
                self._make_artifact("Sands", "EQUIP_SHOES", "Noblesse Oblige", "ATK%", []),
                self._make_artifact("Goblet", "EQUIP_RING", "Noblesse Oblige", "Physical DMG Bonus", []),
                self._make_artifact("Circlet", "EQUIP_DRESS", "Wanderer's Troupe", "Crit Rate", []),
            ],
        }
        result = self.service.analyze_character_build(char)
        assert result["total_score"] < 7.0  # Not an ideal build

    def test_unknown_character_still_returns_analysis(self):
        char = {
            "name": "Character 10000999",
            "artifacts": [
                self._make_artifact("Flower", "EQUIP_BRACER", "Gladiator's Finale", "HP", []),
            ],
        }
        result = self.service.analyze_character_build(char)
        assert "grade" in result
        assert "total_score" in result
        assert isinstance(result["recommendations"], list)

    def test_no_artifacts_returns_defaults(self):
        char = {"name": "Venti", "artifacts": []}
        result = self.service.analyze_character_build(char)
        assert result["total_score"] == 0.0
        assert result["grade"] == "Needs Work"

    def test_grade_thresholds(self):
        assert self.service.analyze_character_build({"name": "X", "artifacts": []})["grade"] == "Needs Work"
