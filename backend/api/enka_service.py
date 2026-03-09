import aiohttp
import asyncio
import time
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class EnkaService:
    """Service for fetching player data from Enka.Network API"""
    
    BASE_URL = "https://enka.network/api/uid"
    CACHE_DURATION = 3600  # Cache player data for 1 hour

    # Enka Network character database (community-maintained, updated with each patch)
    ENKA_CHARACTERS_URL = (
        "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/characters.json"
    )
    # genshin.dev API – always up-to-date, provides element/rarity/weapon/region.
    # Response: list of objects with fields: name, vision (element), rarity,
    # weapon, nation (region), title, gender, affiliation, constellation, etc.
    GENSHIN_DEV_CHARACTERS_URL = "https://genshin.jmp.blue/characters/all?lang=en"
    CHARACTER_CACHE_DURATION = 86400  # Refresh character list once per day

    # Enka element code → friendly name
    ELEMENT_MAP: Dict[str, str] = {
        "Ice": "Cryo",
        "Water": "Hydro",
        "Wind": "Anemo",
        "Rock": "Geo",
        "Electric": "Electro",
        "Grass": "Dendro",
        "Fire": "Pyro",
    }

    # Class-level cache so all instances share a single copy of character data
    _character_db: Dict[int, Dict[str, str]] = {}
    _character_db_loaded_at: float = 0.0

    def __init__(self):
        self.cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Dynamic character database
    # ------------------------------------------------------------------

    async def _ensure_character_data(self) -> None:
        """
        Build the class-level character database by combining two sources:
          1. Enka Network characters.json – provides the numeric avatar IDs we
             need to resolve Enka API payloads.
          2. genshin.dev API – always up-to-date; provides element, rarity,
             weapon type and nation for every current character.
        Both fetches are attempted in parallel; if either fails the other's
        data is still used.  The built-in fallback dict is the last resort.
        """
        age = time.time() - EnkaService._character_db_loaded_at
        if EnkaService._character_db and age < self.CHARACTER_CACHE_DURATION:
            return

        # Fetch both sources concurrently; return_exceptions=True lets one failure
        # not block the other from succeeding.
        results = await asyncio.gather(
            self._fetch_enka_characters(),
            self._load_character_database_from_api(),
            return_exceptions=True,
        )
        enka_db = results[0] if not isinstance(results[0], BaseException) else {}
        genshin_dev_db = results[1] if not isinstance(results[1], BaseException) else {}

        # Merge genshin.dev data into the Enka DB by matching on normalised name.
        # genshin.dev supplies element/rarity/weapon/region; Enka supplies the ID.
        if enka_db and genshin_dev_db:
            for char_info in enka_db.values():
                key = self._normalize_name(char_info["name"])
                dev = genshin_dev_db.get(key)
                if dev:
                    # genshin.dev's element names ("Hydro", "Cryo", …) are already
                    # in the friendly format we use, so prefer them over Enka's.
                    char_info["element"] = dev.get("element") or char_info.get("element", "Unknown")
                    char_info.setdefault("rarity", dev.get("rarity"))
                    char_info.setdefault("weapon", dev.get("weapon"))
                    char_info.setdefault("region", dev.get("region"))

        new_db = enka_db or {}

        if new_db:
            EnkaService._character_db = new_db
            EnkaService._character_db_loaded_at = time.time()
            logger.info(f"Loaded {len(new_db)} characters into character database")
        elif not EnkaService._character_db:
            EnkaService._character_db = self._builtin_character_fallback()
            EnkaService._character_db_loaded_at = time.time()
            logger.info("Using built-in character fallback database")

    async def _fetch_enka_characters(self) -> Dict[int, Dict[str, str]]:
        """Fetch avatar ID → name/element mapping from Enka Network characters.json."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.ENKA_CHARACTERS_URL,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={"User-Agent": "GenshinAICoach/1.0"},
                ) as response:
                    if response.status == 200:
                        raw = await response.json(content_type=None)
                        new_db: Dict[int, Dict[str, str]] = {}
                        for key, info in raw.items():
                            # Key format: "10000002-02" (avatar_id-costume_id)
                            char_id = int(key.split("-")[0])
                            if char_id not in new_db:
                                element_code = info.get("Element", "")
                                new_db[char_id] = {
                                    "name": info.get("NameText", f"Character {char_id}"),
                                    "element": self.ELEMENT_MAP.get(element_code, "Unknown"),
                                }
                        logger.info(
                            f"Loaded {len(new_db)} characters from Enka character database"
                        )
                        return new_db
                    else:
                        logger.warning(
                            f"Enka characters.json returned HTTP {response.status}"
                        )
        except Exception as exc:
            logger.warning(f"Could not fetch Enka character database: {exc}")
        return {}

    async def _load_character_database_from_api(self) -> Dict[str, Dict]:
        """
        Fetch all character data from the genshin.dev API.

        Returns a dict keyed by *normalised* character name so it can be
        joined against the Enka ID database by name matching.  Each entry
        contains: name, element (vision), rarity, weapon, region (nation).
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.GENSHIN_DEV_CHARACTERS_URL,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "GenshinAICoach/1.0"},
                ) as response:
                    if response.status == 200:
                        # content_type=None skips Content-Type validation; genshin.dev
                        # sometimes returns "text/plain" instead of "application/json".
                        data = await response.json(content_type=None)
                        result: Dict[str, Dict] = {}
                        for char in data:
                            name = char.get("name", "")
                            if not name:
                                continue
                            result[self._normalize_name(name)] = {
                                "name": name,
                                "element": char.get("vision", "Unknown"),
                                "rarity": char.get("rarity"),
                                "weapon": char.get("weapon"),
                                "region": char.get("nation"),
                            }
                        logger.info(
                            f"Loaded {len(result)} characters from genshin.dev API"
                        )
                        return result
                    else:
                        logger.warning(
                            f"genshin.dev API returned HTTP {response.status}"
                        )
        except Exception as exc:
            logger.warning(f"Could not fetch genshin.dev character database: {exc}")
        return {}

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalise a character name for cross-source matching (lowercase, no separators)."""
        return name.lower().replace(" ", "").replace("'", "").replace("-", "").replace(".", "")

    def _get_char_name(self, character_id: Optional[int]) -> str:
        info = EnkaService._character_db.get(character_id) if character_id else None
        if info:
            return info["name"]
        return f"Character {character_id}" if character_id else "Unknown"

    def _get_char_element(self, character_id: Optional[int]) -> str:
        info = EnkaService._character_db.get(character_id) if character_id else None
        if info:
            return info["element"]
        return "Unknown"

    def _get_char_info(self, character_id: Optional[int]) -> Dict[str, Any]:
        """Return the full cached info dict for a character, or sensible defaults."""
        info = EnkaService._character_db.get(character_id) if character_id else None
        if info:
            return info.copy()
        return {
            "name": f"Character {character_id}" if character_id else "Unknown",
            "element": "Unknown",
        }

    @staticmethod
    def _builtin_character_fallback() -> Dict[int, Dict[str, str]]:
        """
        Minimal hard-coded fallback using correct Enka avatar IDs.
        Only used when the live characters.json cannot be reached.
        Character IDs sourced from Enka Network API documentation.
        """
        return {
            10000002: {"name": "Kamisato Ayaka",   "element": "Cryo"},
            10000003: {"name": "Qiqi",              "element": "Cryo"},
            10000005: {"name": "Traveler",          "element": "Anemo"},
            10000006: {"name": "Lisa",              "element": "Electro"},
            10000007: {"name": "Traveler",          "element": "Anemo"},
            10000014: {"name": "Barbara",           "element": "Hydro"},
            10000015: {"name": "Kaeya",             "element": "Cryo"},
            10000016: {"name": "Diluc",             "element": "Pyro"},
            10000020: {"name": "Razor",             "element": "Electro"},
            10000021: {"name": "Amber",             "element": "Pyro"},
            10000022: {"name": "Venti",             "element": "Anemo"},
            10000023: {"name": "Xiangling",        "element": "Pyro"},
            10000024: {"name": "Beidou",            "element": "Electro"},
            10000025: {"name": "Xingqiu",          "element": "Hydro"},
            10000026: {"name": "Xiao",              "element": "Anemo"},
            10000027: {"name": "Ningguang",        "element": "Geo"},
            10000029: {"name": "Klee",              "element": "Pyro"},
            10000030: {"name": "Zhongli",          "element": "Geo"},
            10000031: {"name": "Fischl",           "element": "Electro"},
            10000032: {"name": "Bennett",          "element": "Pyro"},
            10000033: {"name": "Tartaglia",        "element": "Hydro"},
            10000034: {"name": "Noelle",           "element": "Geo"},
            10000035: {"name": "Qiqi",             "element": "Cryo"},
            10000036: {"name": "Chongyun",         "element": "Cryo"},
            10000037: {"name": "Ganyu",            "element": "Cryo"},
            10000038: {"name": "Albedo",           "element": "Geo"},
            10000039: {"name": "Diona",            "element": "Cryo"},
            10000041: {"name": "Mona",             "element": "Hydro"},
            10000042: {"name": "Keqing",           "element": "Electro"},
            10000043: {"name": "Sucrose",          "element": "Anemo"},
            10000044: {"name": "Xinyan",           "element": "Pyro"},
            10000045: {"name": "Rosaria",          "element": "Cryo"},
            10000046: {"name": "Hu Tao",           "element": "Pyro"},
            10000047: {"name": "Kazuha",           "element": "Anemo"},
            10000048: {"name": "Yanfei",           "element": "Pyro"},
            10000049: {"name": "Yoimiya",          "element": "Pyro"},
            10000050: {"name": "Thoma",            "element": "Pyro"},
            10000051: {"name": "Eula",             "element": "Cryo"},
            10000052: {"name": "Raiden Shogun",    "element": "Electro"},
            10000053: {"name": "Sayu",             "element": "Anemo"},
            10000054: {"name": "Kokomi",           "element": "Hydro"},
            10000055: {"name": "Gorou",            "element": "Geo"},
            10000056: {"name": "Sara",             "element": "Electro"},
            10000057: {"name": "Itto",             "element": "Geo"},
            10000058: {"name": "Yae Miko",         "element": "Electro"},
            10000059: {"name": "Heizou",           "element": "Anemo"},
            10000060: {"name": "Yelan",            "element": "Hydro"},
            10000061: {"name": "Aloy",             "element": "Cryo"},
            10000062: {"name": "Shenhe",           "element": "Cryo"},
            10000063: {"name": "Yun Jin",          "element": "Geo"},
            10000064: {"name": "Kuki Shinobu",     "element": "Electro"},
            10000065: {"name": "Kamisato Ayato",   "element": "Hydro"},
            10000066: {"name": "Collei",           "element": "Dendro"},
            10000067: {"name": "Dori",             "element": "Electro"},
            10000068: {"name": "Tighnari",         "element": "Dendro"},
            10000069: {"name": "Nilou",            "element": "Hydro"},
            10000070: {"name": "Cyno",             "element": "Electro"},
            10000071: {"name": "Candace",          "element": "Hydro"},
            10000072: {"name": "Nahida",           "element": "Dendro"},
            10000073: {"name": "Layla",            "element": "Cryo"},
            10000074: {"name": "Wanderer",         "element": "Anemo"},
            10000075: {"name": "Faruzan",          "element": "Anemo"},
            10000076: {"name": "Yaoyao",           "element": "Dendro"},
            10000077: {"name": "Alhaitham",        "element": "Dendro"},
            10000078: {"name": "Dehya",            "element": "Pyro"},
            10000079: {"name": "Mika",             "element": "Cryo"},
            10000080: {"name": "Kaveh",            "element": "Dendro"},
            10000081: {"name": "Baizhu",           "element": "Dendro"},
            10000082: {"name": "Lynette",          "element": "Anemo"},
            10000083: {"name": "Lyney",            "element": "Pyro"},
            10000084: {"name": "Freminet",         "element": "Cryo"},
            10000085: {"name": "Wriothesley",      "element": "Cryo"},
            10000086: {"name": "Neuvilette",       "element": "Hydro"},
            10000087: {"name": "Charlotte",        "element": "Cryo"},
            10000088: {"name": "Furina",           "element": "Hydro"},
            10000089: {"name": "Chevreuse",        "element": "Pyro"},
            10000090: {"name": "Navia",            "element": "Geo"},
            10000091: {"name": "Gaming",           "element": "Pyro"},
            10000092: {"name": "Xianyun",          "element": "Anemo"},
            10000093: {"name": "Chiori",           "element": "Geo"},
            10000094: {"name": "Sigewinne",        "element": "Hydro"},
            10000095: {"name": "Arlecchino",       "element": "Pyro"},
            10000096: {"name": "Sethos",           "element": "Electro"},
            10000097: {"name": "Clorinde",         "element": "Electro"},
            10000098: {"name": "Emilie",           "element": "Dendro"},
            10000099: {"name": "Kachina",          "element": "Geo"},
            10000100: {"name": "Kinich",           "element": "Dendro"},
            10000101: {"name": "Mualani",          "element": "Hydro"},
            10000102: {"name": "Xilonen",          "element": "Geo"},
            10000103: {"name": "Chasca",           "element": "Anemo"},
            10000104: {"name": "Ororon",           "element": "Electro"},
            10000105: {"name": "Citlali",          "element": "Cryo"},
            10000106: {"name": "Mizuki",           "element": "Anemo"},
            10000107: {"name": "Varesa",           "element": "Electro"},
            10000108: {"name": "Mavuika",          "element": "Pyro"},
            10000110: {"name": "Lan Yan",          "element": "Anemo"},
        }
    
    async def fetch_account(self, uid: str) -> Dict[str, Any]:
        """
        Fetch player account data from Enka.Network
        
        Args:
            uid: Player UID (as string)
            
        Returns:
            Dictionary with player data
        """
        # Ensure character database is populated before parsing any character data
        await self._ensure_character_data()

        # Check cache first
        if uid in self.cache:
            cached_data, timestamp = self.cache[uid]
            if time.time() - timestamp < self.CACHE_DURATION:
                logger.info(f"Returning cached data for UID {uid}")
                return cached_data
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/{uid}"
                headers = {"User-Agent": "GenshinAICoach/1.0"}
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), headers=headers) as response:
                    if response.status == 200:
                        raw_data = await response.json()
                        
                        # Parse the data
                        parsed_data = self._parse_account_data(raw_data)
                        
                        # Cache it
                        self.cache[uid] = (parsed_data, time.time())
                        
                        logger.info(f"Successfully fetched data for UID {uid}")
                        return parsed_data
                        
                    elif response.status == 404:
                        raise ValueError(f"UID {uid} not found or account is private. Make sure your showcase is public in-game.")
                    elif response.status == 429:
                        raise Exception("Rate limit reached. Please wait a moment and try again.")
                    else:
                        raise Exception(f"API returned status {response.status}")
                        
        except asyncio.TimeoutError:
            raise Exception("API request timed out. Enka.Network might be slow.")
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {str(e)}")
            raise Exception(f"Network error: {str(e)}")
    
    def _parse_account_data(self, raw_data: Dict) -> Dict[str, Any]:
        """Parse raw Enka API response into usable format"""
        
        player_info = raw_data.get("playerInfo", {})
        
        parsed_data = {
            "player_id": raw_data.get("uid"),
            "nickname": player_info.get("nickname"),
            "level": player_info.get("level"),
            "world_level": player_info.get("worldLevel"),
            "signature": player_info.get("signature", ""),
            "achievement_count": player_info.get("finishAchievementNum", 0),
            "abyss_floor": player_info.get("towerFloorIndex", 0),
            "abyss_chamber": player_info.get("towerLevelIndex", 0),
            "characters": [],
        }
        
        # avatarInfoList is at the TOP LEVEL of the response, not inside playerInfo
        avatar_info_list = raw_data.get("avatarInfoList", [])
        for char_data in avatar_info_list:
            character = self._parse_character(char_data)
            parsed_data["characters"].append(character)
        
        # If no detailed avatar data, fall back to showcase list for basic info
        if not parsed_data["characters"]:
            show_list = player_info.get("showAvatarInfoList", [])
            for show_char in show_list:
                char_id = show_char.get("avatarId")
                char_info = self._get_char_info(char_id)
                parsed_data["characters"].append({
                    "id": char_id,
                    "name": char_info["name"],
                    "element": char_info["element"],
                    "rarity": char_info.get("rarity"),
                    "weapon_type": char_info.get("weapon"),
                    "region": char_info.get("region"),
                    "level": show_char.get("level", 1),
                    "ascension": 0,
                    "constellations": 0,
                    "friendship": 0,
                    "stats": {},
                    "weapon": {},
                    "talents": {},
                    "artifacts": [],
                })
        
        return parsed_data
    
    def _parse_character(self, char_data: Dict) -> Dict[str, Any]:
        """Parse individual character data from Enka avatarInfoList entry"""
        
        character_id = char_data.get("avatarId")
        char_info = self._get_char_info(character_id)
        char_name = char_info["name"]
        char_element = char_info["element"]

        # Character level is in propMap["4001"]
        prop_map = char_data.get("propMap", {})
        level_entry = prop_map.get("4001", {})
        level = int(level_entry.get("val", level_entry.get("ival", 1)))

        # Ascension is in propMap["1002"]
        ascension_entry = prop_map.get("1002", {})
        ascension = int(ascension_entry.get("val", ascension_entry.get("ival", 0)))

        # Constellations: number of talent IDs unlocked
        constellations = len(char_data.get("talentIdList", []))

        # Friendship level
        fetter_info = char_data.get("fetterInfo", {})
        friendship = fetter_info.get("expLevel", 0)

        # Parse stats from fightPropMap (keys are strings of integers)
        # Correct keys per Enka API spec:
        #   "1000" = Max HP, "2000" = Max ATK, "2001" = Max DEF
        #   "20"   = Energy Recharge (decimal), "22" = Elemental Mastery
        #   "23"   = Crit Rate (decimal), "24"  = Crit DMG (decimal)
        fight_props = char_data.get("fightPropMap", {})
        stats = {}
        if "1000" in fight_props:
            stats["HP"] = round(float(fight_props["1000"]))
        if "2000" in fight_props:
            stats["ATK"] = round(float(fight_props["2000"]))
        if "2001" in fight_props:
            stats["DEF"] = round(float(fight_props["2001"]))
        if "20" in fight_props:
            stats["Energy Recharge"] = f"{round(float(fight_props['20']) * 100, 1)}%"
        if "22" in fight_props:
            stats["Elemental Mastery"] = round(float(fight_props["22"]))
        if "23" in fight_props:
            stats["Crit Rate"] = f"{round(float(fight_props['23']) * 100, 1)}%"
        if "24" in fight_props:
            stats["Crit DMG"] = f"{round(float(fight_props['24']) * 100, 1)}%"
        
        # Parse weapon and artifacts from equipList
        weapon_info = {}
        artifacts: List[Dict] = []
        equip_list = char_data.get("equipList", [])
        for equip in equip_list:
            flat = equip.get("flat", {})
            item_type = flat.get("itemType", "")
            if item_type == "ITEM_WEAPON":
                weapon_info = {
                    "level": equip.get("weapon", {}).get("level"),
                    "refinement": max(equip.get("weapon", {}).get("affixMap", {0: 0}).values(), default=0) + 1,
                    "rarity": flat.get("rankLevel"),
                    "type": flat.get("equipType", ""),
                }
            elif item_type == "ITEM_RELIQUARY":
                main_stat = flat.get("reliquaryMainstat", {})
                sub_stats = flat.get("reliquarySubstats", [])
                artifacts.append({
                    "slot": flat.get("equipType", "").replace("EQUIP_", "").title(),
                    "set_name": flat.get("setNameTextMapHash", ""),
                    "icon": flat.get("icon", ""),
                    "rarity": flat.get("rankLevel"),
                    "level": equip.get("reliquary", {}).get("level", 1) - 1,
                    "main_stat": main_stat.get("mainPropId", "").replace("FIGHT_PROP_", "").replace("_", " ").title(),
                    "main_stat_value": main_stat.get("statValue", 0.0),
                    "substats": [
                        {
                            "name": s.get("appendPropId", "").replace("FIGHT_PROP_", "").replace("_", " ").title(),
                            "value": s.get("statValue", 0.0),
                        }
                        for s in sub_stats
                    ],
                    "sub_stat_count": len(sub_stats),
                })

        # Parse talent/skill levels from skillLevelMap
        # Keys vary by character; we grab up to 3 values (normal, skill, burst)
        skill_map = char_data.get("skillLevelMap", {})
        skill_levels = list(skill_map.values())
        talents = {}
        if len(skill_levels) >= 1:
            talents["normal_attack"] = skill_levels[0]
        if len(skill_levels) >= 2:
            talents["elemental_skill"] = skill_levels[1]
        if len(skill_levels) >= 3:
            talents["elemental_burst"] = skill_levels[2]
        
        return {
            "id": character_id,
            "name": char_name,
            "element": char_element,
            "rarity": char_info.get("rarity"),
            "weapon_type": char_info.get("weapon"),
            "region": char_info.get("region"),
            "level": level,
            "ascension": ascension,
            "constellations": constellations,
            "friendship": friendship,
            "stats": stats,
            "weapon": weapon_info,
            "talents": talents,
            "artifacts": artifacts,
        }