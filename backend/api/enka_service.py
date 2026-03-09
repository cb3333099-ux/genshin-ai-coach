import aiohttp
import asyncio
import time
import json
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class EnkaService:
    """Service for fetching player data from Enka.Network API"""
    
    BASE_URL = "https://enka.network/api/uid"
    CACHE_DURATION = 3600  # Cache for 1 hour
    
    def __init__(self):
        self.cache = {}
        self.character_names = self._load_character_names()
        
    def _load_character_names(self) -> Dict[int, str]:
        """Load character ID to name mapping"""
        return {
            10000002: "Ayaka",
            10000003: "Qiqi",
            10000005: "Amber",
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
            10000055: "Hutao",
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
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        raw_data = await response.json()
                        
                        # Parse the data
                        parsed_data = self._parse_account_data(raw_data)
                        
                        # Cache it
                        self.cache[uid] = (parsed_data, time.time())
                        
                        logger.info(f"Successfully fetched data for UID {uid}")
                        return parsed_data
                        
                    elif response.status == 404:
                        raise ValueError(f"UID {uid} not found or account is private")
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
            "player_id": player_info.get("playerID"),
            "nickname": player_info.get("nickname"),
            "level": player_info.get("level"),
            "world_level": player_info.get("worldLevel"),
            "signature": player_info.get("signature", ""),
            "characters": [],
        }
        
        # Parse characters
        if "avatarInfoList" in player_info:
            for char_data in player_info["avatarInfoList"]:
                character = self._parse_character(char_data)
                parsed_data["characters"].append(character)
        
        return parsed_data
    
    def _parse_character(self, char_data: Dict) -> Dict[str, Any]:
        """Parse individual character data"""
        
        character_id = char_data.get("avatarId")
        char_name = self.character_names.get(character_id, f"Unknown")
        
        # Get character details
        detail_info = char_data.get("avatarInfo", {})
        
        # Parse stats
        stats = {}
        fight_props = detail_info.get("fightPropMap", {})
        
        if "10" in fight_props:
            stats["HP"] = round(float(fight_props["10"]), 2)
        if "11" in fight_props:
            stats["Attack"] = round(float(fight_props["11"]), 2)
        if "12" in fight_props:
            stats["Defense"] = round(float(fight_props["12"]), 2)
        if "20" in fight_props:
            stats["Energy Recharge"] = round(float(fight_props["20"]), 2)
        if "22" in fight_props:
            stats["Elemental Mastery"] = round(float(fight_props["22"]), 2)
        if "25" in fight_props:
            stats["Crit Rate"] = round(float(fight_props["25"]), 2)
        if "26" in fight_props:
            stats["Crit Damage"] = round(float(fight_props["26"]), 2)
        
        # Parse weapon
        weapon_info = {}
        if "equipList" in detail_info:
            for equip in detail_info["equipList"]:
                if equip.get("flat", {}).get("itemType") == "ITEM_WEAPON":
                    weapon_info = {
                        "name": equip.get("flat", {}).get("name"),
                        "level": equip.get("weapon", {}).get("level"),
                        "rarity": equip.get("flat", {}).get("rankLevel"),
                    }
        
        # Parse talents/skills
        talents = {
            "normal_attack": detail_info.get("skillLevelMap", {}).get("10001", 1),
            "elemental_skill": detail_info.get("skillLevelMap", {}).get("10002", 1),
            "elemental_burst": detail_info.get("skillLevelMap", {}).get("10003", 1),
        }
        
        return {
            "id": character_id,
            "name": char_name,
            "level": detail_info.get("level", 1),
            "ascension": detail_info.get("promotion", 0),
            "stats": stats,
            "weapon": weapon_info,
            "talents": talents,
        }