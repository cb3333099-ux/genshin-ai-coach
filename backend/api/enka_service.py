import aiohttp
import asyncio
import time
import json
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class EnkaService:
    """Service for fetching player data from Enka.Network API"""
    
    BASE_URL = "https://enka.network/api/uid"
    CACHE_DURATION = 3600  # Cache for 1 hour
    
    def __init__(self):
        self.cache = {}
        self.character_names = self._load_character_names()
        self.character_elements = self._load_character_elements()
        
    def _load_character_names(self) -> Dict[int, str]:
        """Load character ID to name mapping"""
        return {
            10000002: "Ayaka",
            10000003: "Qiqi",
            10000005: "Traveler",
            10000006: "Barbara",
            10000007: "Bennett",
            10000014: "Noelle",
            10000015: "Chongyun",
            10000016: "Fischl",
            10000020: "Razor",
            10000021: "Amber",
            10000022: "Venti",
            10000023: "Xiangling",
            10000024: "Ningguang",
            10000025: "Hu Tao",
            10000026: "Sucrose",
            10000027: "Mika",
            10000029: "Xingqiu",
            10000030: "Xinyan",
            10000031: "Kokomi",
            10000032: "Ganyu",
            10000033: "Zhongli",
            10000034: "Shenhe",
            10000035: "Yae Miko",
            10000036: "Nahida",
            10000037: "Yelan",
            10000038: "Alhaitham",
            10000039: "Dehya",
            10000040: "Mika",
            10000041: "Kazuha",
            10000042: "Fischl",
            10000043: "Collei",
            10000044: "Tighnari",
            10000045: "Cyno",
            10000046: "Nilou",
            10000047: "Nahida",
            10000048: "Layla",
            10000049: "Wanderer",
            10000050: "Faruzan",
            10000051: "Yaoyao",
            10000052: "Alhaitham",
            10000053: "Baizhu",
            10000054: "Kaveh",
            10000055: "Hu Tao",
            10000056: "Neuvilette",
            10000057: "Wriothesley",
            10000058: "Furina",
            10000059: "Charlotte",
            10000060: "Navia",
            10000061: "Chevreuse",
            10000062: "Xianyun",
            10000063: "Gaming",
            10000064: "Chiori",
            10000065: "Sigewinne",
            10000066: "Arlecchino",
            10000067: "Sethos",
            10000068: "Clorinde",
            10000069: "Emilie",
            10000070: "Kachina",
            10000071: "Kinich",
            10000072: "Mualani",
            10000073: "Xilonen",
            10000074: "Chasca",
            10000075: "Ororon",
            10000076: "Citlali",
            10000077: "Mizuki",
            10000078: "Varesa",
        }

    def _load_character_elements(self) -> Dict[int, str]:
        """Load character ID to element mapping"""
        return {
            10000002: "Cryo",
            10000003: "Cryo",
            10000005: "Anemo",
            10000006: "Hydro",
            10000007: "Pyro",
            10000014: "Geo",
            10000015: "Cryo",
            10000016: "Electro",
            10000020: "Electro",
            10000021: "Pyro",
            10000022: "Anemo",
            10000023: "Pyro",
            10000024: "Geo",
            10000025: "Pyro",
            10000026: "Anemo",
            10000027: "Cryo",
            10000029: "Hydro",
            10000030: "Pyro",
            10000031: "Hydro",
            10000032: "Cryo",
            10000033: "Geo",
            10000034: "Cryo",
            10000035: "Electro",
            10000036: "Dendro",
            10000037: "Hydro",
            10000038: "Dendro",
            10000039: "Pyro",
            10000040: "Cryo",
            10000041: "Anemo",
            10000042: "Electro",
            10000043: "Dendro",
            10000044: "Dendro",
            10000045: "Electro",
            10000046: "Hydro",
            10000047: "Dendro",
            10000048: "Cryo",
            10000049: "Anemo",
            10000050: "Anemo",
            10000051: "Dendro",
            10000052: "Dendro",
            10000053: "Dendro",
            10000054: "Dendro",
            10000055: "Pyro",
            10000056: "Hydro",
            10000057: "Cryo",
            10000058: "Hydro",
            10000059: "Cryo",
            10000060: "Geo",
            10000061: "Pyro",
            10000062: "Anemo",
            10000063: "Pyro",
            10000064: "Geo",
            10000065: "Hydro",
            10000066: "Pyro",
            10000067: "Electro",
            10000068: "Electro",
            10000069: "Dendro",
            10000070: "Geo",
            10000071: "Dendro",
            10000072: "Hydro",
            10000073: "Geo",
            10000074: "Anemo",
            10000075: "Electro",
            10000076: "Cryo",
            10000077: "Anemo",
            10000078: "Electro",
        }
    
    async def fetch_account(self, uid: str) -> Dict[str, Any]:
        """
        Fetch player account data from Enka.Network
        
        Args:
            uid: Player UID (as string)
            
        Returns:
            Dictionary with player data
        """
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
                parsed_data["characters"].append({
                    "id": char_id,
                    "name": self.character_names.get(char_id, f"Character {char_id}"),
                    "element": self.character_elements.get(char_id, "Unknown"),
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
        char_name = self.character_names.get(character_id, f"Character {character_id}")
        char_element = self.character_elements.get(character_id, "Unknown")

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
                    "rarity": flat.get("rankLevel"),
                    "level": equip.get("reliquary", {}).get("level", 1) - 1,
                    "main_stat": main_stat.get("mainPropId", "").replace("FIGHT_PROP_", "").replace("_", " ").title(),
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
            "level": level,
            "ascension": ascension,
            "constellations": constellations,
            "friendship": friendship,
            "stats": stats,
            "weapon": weapon_info,
            "talents": talents,
            "artifacts": artifacts,
        }