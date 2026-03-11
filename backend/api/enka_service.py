import aiohttp
import asyncio
import re
import time
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class EnkaService:
    """Service for fetching player data from Enka.Network API"""
    
    BASE_URL = "https://enka.network/api/uid"
    CACHE_DURATION = 3600  # Cache player data for 1 hour

    # Mapping from Enka fight prop IDs to human-readable stat names.
    # Used for both main-stat and substat labels in artifact parsing.
    PROP_ID_TO_STAT: Dict[str, str] = {
        "FIGHT_PROP_HP":                    "HP",
        "FIGHT_PROP_HP_PERCENT":            "HP%",
        "FIGHT_PROP_ATTACK":                "ATK",
        "FIGHT_PROP_ATTACK_PERCENT":        "ATK%",
        "FIGHT_PROP_DEFENSE":               "DEF",
        "FIGHT_PROP_DEFENSE_PERCENT":       "DEF%",
        "FIGHT_PROP_ELEMENT_MASTERY":       "Elemental Mastery",
        "FIGHT_PROP_CHARGE_EFFICIENCY":     "Energy Recharge",
        "FIGHT_PROP_CRITICAL":              "Crit Rate",
        "FIGHT_PROP_CRITICAL_HURT":         "Crit DMG",
        "FIGHT_PROP_HEAL_ADD":              "Healing Bonus",
        "FIGHT_PROP_FIRE_ADD_HURT":         "Pyro DMG Bonus",
        "FIGHT_PROP_WATER_ADD_HURT":        "Hydro DMG Bonus",
        "FIGHT_PROP_ICE_ADD_HURT":          "Cryo DMG Bonus",
        "FIGHT_PROP_ELEC_ADD_HURT":         "Electro DMG Bonus",
        "FIGHT_PROP_WIND_ADD_HURT":         "Anemo DMG Bonus",
        "FIGHT_PROP_ROCK_ADD_HURT":         "Geo DMG Bonus",
        "FIGHT_PROP_GRASS_ADD_HURT":        "Dendro DMG Bonus",
        "FIGHT_PROP_PHYSICAL_ADD_HURT":     "Physical DMG Bonus",
    }

    # Enka Network character database (community-maintained, updated with each patch)
    ENKA_CHARACTERS_URL = (
        "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/characters.json"
    )
    # Enka Network localisation file – maps NameTextMapHash values to English
    # display names.  Required to resolve character names from characters.json.
    ENKA_LOC_URL = (
        "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/loc.json"
    )
    # genshin.dev API – always up-to-date, provides element/rarity/weapon/region.
    # Response: list of objects with fields: name, vision (element), rarity,
    # weapon, nation (region), title, gender, affiliation, constellation, etc.
    GENSHIN_DEV_CHARACTERS_URL = "https://genshin.jmp.blue/characters/all?lang=en"
    # Third-party Genshin character list API – provides character ID → name mapping
    # including the very newest characters not yet indexed by the other sources.
    JMSSZKZLZ_CHARACTERS_URL = "https://genshin.jmsszkzlz.com/api/character/list"
    # genshin.dev artifacts endpoint – used to build artifact set icon-ID → name map.
    GENSHIN_DEV_ARTIFACTS_URL = "https://genshin.jmp.blue/artifacts/all?lang=en"
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

    # Equip-type slot codes returned by Enka → canonical slot names used in
    # build analysis (sands/goblet/circlet for main-stat matching).
    EQUIP_TYPE_TO_SLOT: Dict[str, str] = {
        "EQUIP_BRACER":   "flower",
        "EQUIP_NECKLACE": "feather",
        "EQUIP_SHOES":    "sands",
        "EQUIP_RING":     "goblet",
        "EQUIP_DRESS":    "circlet",
    }

    # Hardcoded artifact set icon-ID → set name for the most popular endgame sets.
    # Icon format from Enka: UI_RelicIcon_{setId}_{slotId}
    # Used as fallback when the dynamic genshin.dev fetch is unavailable.
    ARTIFACT_SET_IDS: Dict[str, str] = {
        "10001": "Gladiator's Finale",
        "10003": "Berserker",
        "10007": "Instructor",
        "10008": "Lucky Dog",
        "10009": "Exile",
        "10010": "Scholar",
        "14001": "Brave Heart",
        "14004": "Defender's Will",
        "14007": "Adventurer",
        "14010": "Traveling Doctor",
        "14019": "Viridescent Venerer",
        "14023": "Maiden Beloved",
        "14024": "Noblesse Oblige",
        "15001": "Resolution of Sojourner",
        "15009": "Thundering Fury",
        "15010": "Thundersoother",
        "15015": "Bloodstained Chivalry",
        "15020": "Retracing Bolide",
        "15023": "Pale Flame",
        "15025": "Shimenawa's Reminiscence",
        "15026": "Crimson Witch of Flames",
        "15027": "Lavawalker",
        "15028": "Blizzard Strayer",
        "15029": "Heart of Depth",
        "15031": "Emblem of Severed Fate",
        "15033": "Husk of Opulent Dreams",
        "15034": "Ocean-Hued Clam",
        "15035": "Vermillion Hereafter",
        "15036": "Echoes of an Offering",
        "15037": "Tenacity of the Millelith",
        "15038": "Deepwood Memories",
        "15039": "Gilded Dreams",
        "15040": "Desert Pavilion Chronicle",
        "15041": "Flower of Paradise Lost",
        "15042": "Nymph's Dream",
        "15043": "Vourukasha's Glow",
        "15044": "Marechaussee Hunter",
        "15045": "Golden Troupe",
        "15046": "Song of Days Past",
        "15047": "Nighttime Whispers in the Echoing Woods",
        "15048": "Fragment of Harmonic Whimsy",
        "15049": "Unfinished Reverie",
        "15050": "Scroll of the Hero of Cinder City",
        "15051": "Obsidian Codex",
        "15052": "Long Night's Oath",
    }

    # Artifact set bonuses and ideal characters.
    ARTIFACT_SETS: Dict[str, Dict[str, Any]] = {
        "Crimson Witch of Flames": {
            "2piece": "Pyro DMG Bonus +15%",
            "4piece": "Increases Overloaded and Burning DMG by 40%. Increases Vaporize and Melt DMG by 15%. Using Elemental Skill increases 2-piece set effects by 50% for 10s (max 3 stacks).",
            "ideal_for": ["Hu Tao", "Klee", "Yanfei", "Lyney", "Arlecchino", "Mavuika"],
            "element": "Pyro",
        },
        "Blizzard Strayer": {
            "2piece": "Cryo DMG Bonus +15%",
            "4piece": "When a character attacks an enemy affected by Cryo, their Crit Rate is increased by 20%. If the enemy is Frozen, Crit Rate is increased by an additional 20%.",
            "ideal_for": ["Ganyu", "Kamisato Ayaka", "Wriothesley", "Citlali"],
            "element": "Cryo",
        },
        "Thundering Fury": {
            "2piece": "Electro DMG Bonus +15%",
            "4piece": "Increases DMG caused by Overloaded, Electro-Charged, Superconduct, and Hyperbloom by 40%. Triggering such reactions decreases Elemental Skill CD by 1s.",
            "ideal_for": ["Keqing", "Cyno", "Fischl", "Yae Miko"],
            "element": "Electro",
        },
        "Viridescent Venerer": {
            "2piece": "Anemo DMG Bonus +15%",
            "4piece": "Increases Swirl DMG by 60%. Decreases opponent's Elemental RES to the element infused in the Swirl by 40% for 10s.",
            "ideal_for": ["Kaedehara Kazuha", "Sucrose", "Venti", "Wanderer", "Jean", "Faruzan", "Xianyun", "Lan Yan"],
            "element": "Anemo",
        },
        "Emblem of Severed Fate": {
            "2piece": "Energy Recharge +20%",
            "4piece": "Increases Elemental Burst DMG by 25% of Energy Recharge. Max 75% bonus DMG.",
            "ideal_for": ["Raiden Shogun", "Xiangling", "Sara", "Yelan", "Kokomi", "Beidou"],
            "element": "Any",
        },
        "Noblesse Oblige": {
            "2piece": "Elemental Burst DMG +20%",
            "4piece": "Using Elemental Burst increases all party members' ATK by 20% for 12s.",
            "ideal_for": ["Bennett", "Mona", "Qiqi", "Albedo"],
            "element": "Any",
        },
        "Pale Flame": {
            "2piece": "Physical DMG Bonus +25%",
            "4piece": "When Elemental Skill hits an opponent, ATK is increased by 9% for 7s. Max 2 stacks. 2 stacks also increases Physical DMG Bonus by 25%.",
            "ideal_for": ["Eula", "Razor", "Xinyan"],
            "element": "Physical",
        },
        "Deepwood Memories": {
            "2piece": "Dendro DMG Bonus +15%",
            "4piece": "After Elemental Skills or Bursts hit opponents, the targets' Dendro RES is decreased by 30% for 8s.",
            "ideal_for": ["Nahida", "Baizhu", "Collei", "Yaoyao", "Tighnari"],
            "element": "Dendro",
        },
        "Gilded Dreams": {
            "2piece": "Elemental Mastery +80",
            "4piece": "Within 8s of triggering an Elemental Reaction, the character equipping this will obtain buffs based on the Elemental Type of the other party members.",
            "ideal_for": ["Nahida", "Alhaitham", "Tighnari", "Cyno", "Kirara"],
            "element": "Dendro",
        },
        "Marechaussee Hunter": {
            "2piece": "Normal and Charged Attack DMG +15%",
            "4piece": "When current HP increases or decreases, Crit Rate is increased by 12% for 5s. Max 3 stacks.",
            "ideal_for": ["Hu Tao", "Furina", "Neuvillette", "Lyney"],
            "element": "Any",
        },
        "Golden Troupe": {
            "2piece": "Elemental Skill DMG +20%",
            "4piece": "Increases Elemental Skill DMG by 25%. When not on field, Elemental Skill DMG is increased by an additional 25%.",
            "ideal_for": ["Fischl", "Yae Miko", "Citlali", "Ororon"],
            "element": "Any",
        },
        "Husk of Opulent Dreams": {
            "2piece": "DEF +30%",
            "4piece": "A character that gains Curiosity can have its DEF increased by 6% and Geo DMG increased by 6%.",
            "ideal_for": ["Albedo", "Itto", "Noelle", "Gorou"],
            "element": "Geo",
        },
        "Desert Pavilion Chronicle": {
            "2piece": "Anemo DMG Bonus +15%",
            "4piece": "When Charged Attacks hit opponents, the equipping character's Normal Attack SPD increases by 10% while Normal, Charged, and Plunging Attack DMG increases by 40% for 15s.",
            "ideal_for": ["Wanderer", "Xianyun", "Chasca"],
            "element": "Anemo",
        },
        "Fragment of Harmonic Whimsy": {
            "2piece": "ATK +18%",
            "4piece": "When the value of a Bond of Life increases or decreases, this character deals 18% increased DMG for 6s. Max 3 stacks.",
            "ideal_for": ["Arlecchino", "Clorinde"],
            "element": "Any",
        },
        "Obsidian Codex": {
            "2piece": "While off-field, Elemental Skill DMG +15%",
            "4piece": "After the equipping character's Nightsoul is consumed, deal DMG increased by 40% for 15s.",
            "ideal_for": ["Citlali", "Mavuika", "Varesa", "Lan Yan"],
            "element": "Any",
        },
        "Scroll of the Hero of Cinder City": {
            "2piece": "Nightsoul-aligned characters deal 12% more DMG",
            "4piece": "When a character activates or is activated by Nightsoul's Blessing, all party members with the same element gain 40% Elemental DMG Bonus for 15s.",
            "ideal_for": ["Mavuika", "Ororon", "Xilonen", "Chasca"],
            "element": "Any",
        },
        "Shimenawa's Reminiscence": {
            "2piece": "ATK +18%",
            "4piece": "When casting an Elemental Skill, if the character has 15 or more Energy, they lose 15 Energy and Normal/Charged/Plunging Attack DMG is increased by 50% for 10s.",
            "ideal_for": ["Hu Tao", "Yoimiya", "Ganyu", "Noelle"],
            "element": "Any",
        },
        "Unfinished Reverie": {
            "2piece": "ATK +18%",
            "4piece": "After leaving combat for 3s, DMG dealt is increased by 50%. In combat, if no Burning opponents are nearby within 3s, DMG is increased by 20%.",
            "ideal_for": ["Dehya", "Xilonen", "Arlecchino"],
            "element": "Any",
        },
        "Long Night's Oath": {
            "2piece": "HP +20%",
            "4piece": "Increases Charged Attack DMG based on the equipping character's Max HP.",
            "ideal_for": ["Neuvillette", "Sigewinne"],
            "element": "Hydro",
        },
    }

    # Optimal build configurations for popular characters.
    # main_stats lists acceptable main-stat options for sands/goblet/circlet.
    # ideal_substats lists substats in priority order.
    OPTIMAL_BUILDS: Dict[str, Dict[str, Any]] = {
        "Hu Tao": {
            "artifact_sets": ["Crimson Witch of Flames", "Marechaussee Hunter", "Shimenawa's Reminiscence"],
            "main_stats": {
                "sands": ["HP%"],
                "goblet": ["Pyro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "HP%", "Elemental Mastery"],
            "role": "Main DPS",
        },
        "Ganyu": {
            "artifact_sets": ["Blizzard Strayer", "Shimenawa's Reminiscence", "Wanderer's Troupe"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Cryo DMG Bonus"],
                "circlet": ["Crit DMG", "Crit Rate"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Elemental Mastery"],
            "role": "Main DPS",
        },
        "Raiden Shogun": {
            "artifact_sets": ["Emblem of Severed Fate"],
            "main_stats": {
                "sands": ["ATK%", "Energy Recharge"],
                "goblet": ["Electro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit Rate", "Crit DMG", "ATK%", "Energy Recharge"],
            "role": "Main DPS / Sub-DPS",
        },
        "Nahida": {
            "artifact_sets": ["Deepwood Memories", "Gilded Dreams"],
            "main_stats": {
                "sands": ["Elemental Mastery", "ATK%"],
                "goblet": ["Dendro DMG Bonus", "Elemental Mastery"],
                "circlet": ["Crit Rate", "Crit DMG", "Elemental Mastery"],
            },
            "ideal_substats": ["Elemental Mastery", "Crit Rate", "Crit DMG", "ATK%"],
            "role": "Sub-DPS / Support",
        },
        "Kaedehara Kazuha": {
            "artifact_sets": ["Viridescent Venerer"],
            "main_stats": {
                "sands": ["Elemental Mastery"],
                "goblet": ["Elemental Mastery"],
                "circlet": ["Elemental Mastery"],
            },
            "ideal_substats": ["Elemental Mastery", "Energy Recharge", "HP%", "ATK%"],
            "role": "Support",
        },
        "Venti": {
            "artifact_sets": ["Viridescent Venerer", "Emblem of Severed Fate"],
            "main_stats": {
                "sands": ["Elemental Mastery", "Energy Recharge"],
                "goblet": ["Elemental Mastery", "Anemo DMG Bonus"],
                "circlet": ["Elemental Mastery", "Crit Rate"],
            },
            "ideal_substats": ["Elemental Mastery", "Energy Recharge", "Crit Rate", "Crit DMG"],
            "role": "Support",
        },
        "Zhongli": {
            "artifact_sets": ["Tenacity of the Millelith", "Noblesse Oblige"],
            "main_stats": {
                "sands": ["HP%"],
                "goblet": ["HP%", "Geo DMG Bonus"],
                "circlet": ["HP%", "Crit Rate"],
            },
            "ideal_substats": ["HP%", "HP", "Crit Rate", "Crit DMG"],
            "role": "Support",
        },
        "Bennett": {
            "artifact_sets": ["Noblesse Oblige"],
            "main_stats": {
                "sands": ["HP%", "Energy Recharge"],
                "goblet": ["HP%"],
                "circlet": ["HP%", "Healing Bonus"],
            },
            "ideal_substats": ["HP%", "HP", "Energy Recharge", "Crit Rate"],
            "role": "Support",
        },
        "Furina": {
            "artifact_sets": ["Golden Troupe", "Marechaussee Hunter"],
            "main_stats": {
                "sands": ["HP%"],
                "goblet": ["HP%", "Hydro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG", "HP%"],
            },
            "ideal_substats": ["HP%", "Crit Rate", "Crit DMG", "Energy Recharge"],
            "role": "Support",
        },
        "Neuvillette": {
            "artifact_sets": ["Marechaussee Hunter", "Long Night's Oath"],
            "main_stats": {
                "sands": ["HP%"],
                "goblet": ["Hydro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit Rate", "Crit DMG", "HP%", "Elemental Mastery"],
            "role": "Main DPS",
        },
        "Arlecchino": {
            "artifact_sets": ["Fragment of Harmonic Whimsy", "Shimenawa's Reminiscence", "Crimson Witch of Flames"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Pyro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Elemental Mastery"],
            "role": "Main DPS",
        },
        "Mavuika": {
            "artifact_sets": ["Obsidian Codex", "Scroll of the Hero of Cinder City", "Crimson Witch of Flames"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Pyro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Elemental Mastery"],
            "role": "Main DPS",
        },
        "Lyney": {
            "artifact_sets": ["Crimson Witch of Flames", "Marechaussee Hunter"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Pyro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "HP%"],
            "role": "Main DPS",
        },
        "Eula": {
            "artifact_sets": ["Pale Flame"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Physical DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Energy Recharge"],
            "role": "Main DPS",
        },
        "Ayaka": {
            "artifact_sets": ["Blizzard Strayer", "Shimenawa's Reminiscence"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Cryo DMG Bonus"],
                "circlet": ["Crit DMG", "Crit Rate"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Energy Recharge"],
            "role": "Main DPS",
        },
        "Kamisato Ayaka": {
            "artifact_sets": ["Blizzard Strayer", "Shimenawa's Reminiscence"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Cryo DMG Bonus"],
                "circlet": ["Crit DMG", "Crit Rate"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Energy Recharge"],
            "role": "Main DPS",
        },
        "Wriothesley": {
            "artifact_sets": ["Blizzard Strayer", "Marechaussee Hunter"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Cryo DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "HP%"],
            "role": "Main DPS",
        },
        "Fischl": {
            "artifact_sets": ["Golden Troupe", "Thundering Fury"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Electro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Energy Recharge"],
            "role": "Sub-DPS",
        },
        "Yae Miko": {
            "artifact_sets": ["Golden Troupe", "Thundering Fury"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Electro DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Elemental Mastery"],
            "role": "Sub-DPS",
        },
        "Wanderer": {
            "artifact_sets": ["Desert Pavilion Chronicle", "Shimenawa's Reminiscence"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Anemo DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Elemental Mastery"],
            "role": "Main DPS",
        },
        "Citlali": {
            "artifact_sets": ["Obsidian Codex", "Golden Troupe"],
            "main_stats": {
                "sands": ["HP%"],
                "goblet": ["Cryo DMG Bonus", "HP%"],
                "circlet": ["Crit Rate", "Crit DMG", "HP%"],
            },
            "ideal_substats": ["HP%", "Crit Rate", "Crit DMG", "Energy Recharge"],
            "role": "Support",
        },
        "Chasca": {
            "artifact_sets": ["Desert Pavilion Chronicle", "Scroll of the Hero of Cinder City"],
            "main_stats": {
                "sands": ["ATK%"],
                "goblet": ["Anemo DMG Bonus"],
                "circlet": ["Crit Rate", "Crit DMG"],
            },
            "ideal_substats": ["Crit DMG", "Crit Rate", "ATK%", "Elemental Mastery"],
            "role": "Main DPS",
        },
    }

    # Class-level cache so all instances share a single copy of character data
    _character_db: Dict[int, Dict[str, str]] = {}
    _character_db_loaded_at: float = 0.0
    # Class-level cache for artifact set names resolved from API icons
    _artifact_set_name_db: Dict[str, str] = {}
    _artifact_set_name_db_loaded_at: float = 0.0

    def __init__(self):
        self.cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Dynamic character database
    # ------------------------------------------------------------------

    async def _ensure_character_data(self) -> None:
        """
        Build the class-level character database by combining:
          1. Built-in fallback – always used as the base so common characters
             always resolve to real names even when external APIs are unavailable.
          2. Enka Network characters.json – supplements the fallback with newer
             characters not yet in the built-in list (IDs added each patch).
          3. genshin.dev API – enriches entries with rarity, weapon type and
             nation metadata.
          4. jmsszkzlz API – additional community source with the very newest
             character IDs not yet indexed by the other sources.
        The fallback is the authoritative source for character names; dynamic
        data is only added for character IDs that are absent from the fallback,
        and only when the returned name looks like a real display name (not a
        numeric TextMap hash).
        """
        age = time.time() - EnkaService._character_db_loaded_at
        if EnkaService._character_db and age < self.CHARACTER_CACHE_DURATION:
            return

        # Always start from the built-in fallback so known characters resolve
        # correctly regardless of external API availability.
        merged_db: Dict[int, Dict[str, Any]] = {
            k: v.copy() for k, v in self._builtin_character_fallback().items()
        }

        # Fetch all three external sources concurrently; return_exceptions=True
        # lets one failure not block the others from succeeding.
        results = await asyncio.gather(
            self._fetch_enka_characters(),
            self._load_character_database_from_api(),
            self._fetch_jmsszkzlz_characters(),
            return_exceptions=True,
        )
        enka_db = results[0] if not isinstance(results[0], BaseException) else {}
        genshin_dev_db = results[1] if not isinstance(results[1], BaseException) else {}
        jmsszkzlz_db = results[2] if not isinstance(results[2], BaseException) else {}

        def _name_is_valid(name: str) -> bool:
            return (
                len(name) >= 2
                and not name.isdigit()
                and not name.startswith("Character ")
            )

        # Add characters from Enka that are not yet in the fallback.
        # Only accept entries whose name looks like a real display name (not a
        # numeric TextMap hash or a bare "Character <id>" placeholder).
        if enka_db:
            for char_id, char_info in enka_db.items():
                name = char_info.get("name", "").strip()
                if char_id not in merged_db and _name_is_valid(name):
                    merged_db[char_id] = char_info.copy()

        # Add characters from the jmsszkzlz API that are still missing.
        # This source is especially useful for the very newest character IDs.
        if jmsszkzlz_db:
            for char_id, char_info in jmsszkzlz_db.items():
                name = char_info.get("name", "").strip()
                if _name_is_valid(name):
                    if char_id not in merged_db:
                        merged_db[char_id] = char_info.copy()
                    else:
                        # Enrich existing entry with any extra metadata the API provides
                        existing = merged_db[char_id]
                        existing.setdefault("rarity", char_info.get("rarity"))
                        existing.setdefault("weapon", char_info.get("weapon"))
                        existing.setdefault("region", char_info.get("region"))

        # Enrich every entry with genshin.dev metadata (element, rarity, weapon,
        # region) by matching on the normalised character name.
        if genshin_dev_db:
            for char_info in merged_db.values():
                name = char_info.get("name", "")
                if not name:
                    continue
                key = self._normalize_name(name)
                dev = genshin_dev_db.get(key)
                if dev:
                    # genshin.dev element names ("Hydro", "Cryo", …) are already
                    # in the friendly format we use, so prefer them.
                    char_info["element"] = dev.get("element") or char_info.get("element", "Unknown")
                    char_info.setdefault("rarity", dev.get("rarity"))
                    char_info.setdefault("weapon", dev.get("weapon"))
                    char_info.setdefault("region", dev.get("region"))

        EnkaService._character_db = merged_db
        EnkaService._character_db_loaded_at = time.time()
        logger.info(f"✅ Loaded {len(merged_db)} characters into character database")

    async def _fetch_enka_characters(self) -> Dict[int, Dict[str, str]]:
        """
        Fetch avatar ID → name/element mapping from Enka Network.

        Enka's characters.json stores character names as numeric TextMap hashes
        (NameTextMapHash), not plain strings.  The English display names are
        resolved by looking up those hashes in the loc.json localisation file.
        Both files are fetched concurrently to keep startup latency low.
        """
        headers = {"User-Agent": "GenshinAICoach/1.0"}
        timeout = aiohttp.ClientTimeout(total=15)
        try:
            async with aiohttp.ClientSession() as session:
                # Fetch characters.json and loc.json concurrently
                results = await asyncio.gather(
                    self._get_json_url(session, self.ENKA_CHARACTERS_URL, timeout, headers),
                    self._get_json_url(session, self.ENKA_LOC_URL, timeout, headers),
                    return_exceptions=True,
                )
            chars_raw = results[0] if isinstance(results[0], dict) else None
            loc_raw = results[1] if isinstance(results[1], dict) else None

            if not chars_raw and not loc_raw:
                logger.warning("Both Enka characters.json and loc.json fetches failed; "
                               "character names will rely on built-in fallback only.")
                return {}
            if not chars_raw:
                logger.warning("Enka characters.json fetch failed or returned empty data")
                return {}
            if not loc_raw:
                logger.warning("Enka loc.json fetch failed or returned empty data; "
                               "character names will rely on built-in fallback only.")
                return {}

            # Build NameTextMapHash → English name lookup from loc.json
            en_map: Dict[str, str] = loc_raw.get("en", {})

            new_db: Dict[int, Dict[str, str]] = {}
            for key, info in chars_raw.items():
                # Key format: "10000002" or "10000002-02" (avatar_id[-costume_id])
                try:
                    char_id = int(key.split("-")[0])
                except (ValueError, IndexError):
                    continue
                if char_id in new_db:
                    continue
                element_code = info.get("Element", "")
                # Resolve the display name via the English TextMap
                name_hash = str(info.get("NameTextMapHash", ""))
                name = en_map.get(name_hash, "")
                if not name:
                    continue
                new_db[char_id] = {
                    "name": name,
                    "element": self.ELEMENT_MAP.get(element_code, "Unknown"),
                }
            logger.info(
                f"Loaded {len(new_db)} characters from Enka character database"
            )
            return new_db
        except Exception as exc:
            logger.warning(f"Could not fetch Enka character database: {exc}")
        return {}

    @staticmethod
    async def _get_json_url(
        session: aiohttp.ClientSession,
        url: str,
        timeout: aiohttp.ClientTimeout,
        headers: dict,
    ):
        """Fetch a URL and return its JSON body, or raise on error."""
        async with session.get(url, timeout=timeout, headers=headers) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status} from {url}")
            return await response.json(content_type=None)

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

    async def _fetch_jmsszkzlz_characters(self) -> Dict[int, Dict[str, Any]]:
        """
        Fetch character ID → data mapping from the jmsszkzlz community API.

        This source is especially useful for the very newest character IDs that
        are not yet indexed by Enka Network or genshin.dev.  The API returns a
        list (or dict) of character objects.  We accept several common response
        shapes flexibly.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.JMSSZKZLZ_CHARACTERS_URL,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "GenshinAICoach/1.0"},
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"jmsszkzlz API returned HTTP {response.status}"
                        )
                        return {}
                    data = await response.json(content_type=None)
                    result: Dict[int, Dict[str, Any]] = {}

                    # Normalise different response shapes into a flat iterable of
                    # character dicts, each of which should have an ID and a name.
                    items: List[Dict] = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        # Could be {"data": [...]} or {"characters": [...]} or a
                        # direct id→entry mapping.
                        for key in ("data", "characters", "list", "items"):
                            if key in data and isinstance(data[key], list):
                                items = data[key]
                                break
                        if not items:
                            # Treat top-level as id→entry dict
                            for k, v in data.items():
                                if isinstance(v, dict):
                                    try:
                                        char_id = int(k)
                                        v["id"] = char_id
                                        items.append(v)
                                    except (ValueError, TypeError):
                                        pass

                    for entry in items:
                        if not isinstance(entry, dict):
                            continue
                        # Try several common key names for the character ID
                        char_id = None
                        for id_key in ("id", "avatarId", "avatar_id", "characterId", "character_id"):
                            raw = entry.get(id_key)
                            if raw is not None:
                                try:
                                    char_id = int(raw)
                                    break
                                except (ValueError, TypeError):
                                    pass
                        if char_id is None:
                            continue

                        # Try several common key names for the character name
                        name = ""
                        for name_key in ("name", "nameText", "character_name", "charName"):
                            raw_name = entry.get(name_key, "")
                            if raw_name and isinstance(raw_name, str) and len(raw_name) >= 2:
                                name = raw_name.strip()
                                break
                        if not name or name.isdigit():
                            continue

                        # Element – try both Enka codes and friendly names
                        element = entry.get("element", entry.get("vision", "Unknown"))
                        if isinstance(element, str):
                            element = self.ELEMENT_MAP.get(element, element)

                        result[char_id] = {
                            "name": name,
                            "element": element or "Unknown",
                            "rarity": entry.get("rarity") or entry.get("quality"),
                            "weapon": entry.get("weapon") or entry.get("weaponType") or entry.get("weapon_type"),
                            "region": entry.get("region") or entry.get("nation") or entry.get("affiliation"),
                        }

                    logger.info(
                        f"Loaded {len(result)} characters from jmsszkzlz API"
                    )
                    return result
        except Exception as exc:
            logger.warning(f"Could not fetch jmsszkzlz character database: {exc}")
        return {}

    async def _fetch_artifact_set_names(self) -> Dict[str, str]:
        """
        Fetch artifact set data from genshin.dev and build a mapping from the
        numeric set ID (extracted from the Enka icon URL) to the set's display
        name.  Falls back to the hardcoded ARTIFACT_SET_IDS table on failure.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.GENSHIN_DEV_ARTIFACTS_URL,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "GenshinAICoach/1.0"},
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"genshin.dev artifacts API returned HTTP {response.status}"
                        )
                        return {}
                    data = await response.json(content_type=None)
                    result: Dict[str, str] = {}
                    items = data if isinstance(data, list) else data.get("data", [])
                    for artifact in items:
                        if not isinstance(artifact, dict):
                            continue
                        set_name = artifact.get("name", "")
                        if not set_name:
                            continue
                        # Look for an image URL that contains the set icon ID,
                        # e.g. https://enka.network/ui/UI_RelicIcon_15026_4.png
                        images = artifact.get("images", artifact.get("icons", {}))
                        icon_url = ""
                        if isinstance(images, dict):
                            icon_url = next(iter(images.values()), "")
                        elif isinstance(images, list) and images:
                            icon_url = images[0]
                        # Extract the numeric set ID from the icon URL
                        match = re.search(r"UI_RelicIcon_(\d+)_\d+", icon_url)
                        if match:
                            set_id = match.group(1)
                            result[set_id] = set_name
                    logger.info(
                        f"Loaded {len(result)} artifact set names from genshin.dev"
                    )
                    return result
        except Exception as exc:
            logger.warning(f"Could not fetch artifact set names from genshin.dev: {exc}")
        return {}

    async def _ensure_artifact_data(self) -> None:
        """Populate the class-level artifact set name cache if needed."""
        age = time.time() - EnkaService._artifact_set_name_db_loaded_at
        if EnkaService._artifact_set_name_db and age < self.CHARACTER_CACHE_DURATION:
            return
        # Start from the hardcoded fallback
        merged: Dict[str, str] = dict(self.ARTIFACT_SET_IDS)
        dynamic = await self._fetch_artifact_set_names()
        merged.update(dynamic)
        EnkaService._artifact_set_name_db = merged
        EnkaService._artifact_set_name_db_loaded_at = time.time()
        logger.info(f"✅ Loaded {len(merged)} artifact set name mappings")

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalise a character name for cross-source matching (lowercase, no separators)."""
        return name.lower().replace(" ", "").replace("'", "").replace("-", "").replace(".", "")

    @staticmethod
    def _prop_id_to_stat_name(prop_id: str) -> str:
        """Convert an Enka fight-prop ID to a human-readable stat name."""
        if prop_id in EnkaService.PROP_ID_TO_STAT:
            return EnkaService.PROP_ID_TO_STAT[prop_id]
        # Graceful fallback: strip prefix and title-case
        return prop_id.replace("FIGHT_PROP_", "").replace("_", " ").title()

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

    def _get_artifact_set_name(self, icon: str) -> str:
        """
        Extract the artifact set name from an Enka icon string such as
        'UI_RelicIcon_15026_4'.  Returns the human-readable set name when known,
        or a placeholder that includes the numeric ID for debugging.
        """
        match = re.search(r"UI_RelicIcon_(\d+)_\d+", icon)
        if not match:
            return "Unknown Set"
        set_id = match.group(1)
        db = EnkaService._artifact_set_name_db or self.ARTIFACT_SET_IDS
        return db.get(set_id, f"Unknown Set ({set_id})")

    @staticmethod
    def _count_set_pieces(artifacts: List[Dict]) -> Dict[str, int]:
        """Count how many pieces of each artifact set are equipped."""
        counts: Dict[str, int] = {}
        for a in artifacts:
            set_name = a.get("set_name", "Unknown Set")
            if set_name and not set_name.startswith("Unknown Set"):
                counts[set_name] = counts.get(set_name, 0) + 1
        return counts

    def analyze_character_build(self, character: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate the build quality for a parsed character dict.

        Returns a dict with:
          - set_summary   : str  – active set bonuses
          - main_stats    : dict – sands/goblet/circlet main stats with ✅/❌
          - set_score     : float (0-3) – artifact set bonus score
          - main_stat_score: float (0-3) – main stat correctness score
          - substat_score : float (0-4) – substat quality score
          - total_score   : float (0-10) – overall build quality
          - grade         : str  – "Excellent" / "Good" / "Average" / "Needs Work"
          - recommendations: list[str] – actionable tips
        """
        char_name = character.get("name", "")
        artifacts = character.get("artifacts", [])
        optimal = self.OPTIMAL_BUILDS.get(char_name)

        # --- Artifact set analysis ---
        set_counts = self._count_set_pieces(artifacts)
        set_summary_parts: List[str] = []
        set_score = 0.0
        for set_name, count in sorted(set_counts.items(), key=lambda x: -x[1]):
            if count >= 4:
                set_summary_parts.append(f"{set_name} (4-piece)")
                if optimal and set_name in optimal.get("artifact_sets", []):
                    set_score = 3.0
                else:
                    set_score = max(set_score, 1.5)
            elif count >= 2:
                set_summary_parts.append(f"{set_name} (2-piece)")
                if optimal and set_name in optimal.get("artifact_sets", []):
                    set_score = max(set_score, 1.5)
                else:
                    set_score = max(set_score, 0.5)
        set_summary = ", ".join(set_summary_parts) if set_summary_parts else "Mixed sets"

        # --- Main stat analysis ---
        # Map Enka equip type codes to canonical slot names
        slot_main_stats: Dict[str, str] = {}
        for a in artifacts:
            equip_type = a.get("equip_type", "")
            slot = self.EQUIP_TYPE_TO_SLOT.get(equip_type, "")
            if slot in ("sands", "goblet", "circlet"):
                slot_main_stats[slot] = a.get("main_stat", "")

        main_stat_details: Dict[str, str] = {}
        main_stat_score = 0.0
        if optimal:
            for slot in ("sands", "goblet", "circlet"):
                actual = slot_main_stats.get(slot, "")
                ideal_options = optimal.get("main_stats", {}).get(slot, [])
                if actual and ideal_options:
                    if actual in ideal_options:
                        main_stat_details[slot] = f"{actual} ✅"
                        main_stat_score += 1.0
                    else:
                        main_stat_details[slot] = f"{actual} ❌ (want: {'/'.join(ideal_options)})"
                elif actual:
                    main_stat_details[slot] = actual
        else:
            for slot in ("sands", "goblet", "circlet"):
                actual = slot_main_stats.get(slot, "")
                if actual:
                    main_stat_details[slot] = actual

        # --- Substat analysis ---
        all_substats: List[str] = []
        for a in artifacts:
            for sub in a.get("substats", []):
                name = sub.get("name", "")
                if name:
                    all_substats.append(name)

        substat_score = 0.0
        if optimal:
            ideal = optimal.get("ideal_substats", [])
            # Count how many of the top 4 unique substat types are ideal
            seen: set = set()
            for sub in all_substats:
                if sub not in seen:
                    seen.add(sub)
                    if sub in ideal:
                        substat_score += 1.0
                        if substat_score >= 4.0:
                            break

        # --- Total score ---
        total_score = round(set_score + main_stat_score + substat_score, 1)
        total_score = min(total_score, 10.0)

        if total_score >= 8.0:
            grade = "Excellent"
        elif total_score >= 6.0:
            grade = "Good"
        elif total_score >= 4.0:
            grade = "Average"
        else:
            grade = "Needs Work"

        # --- Recommendations ---
        recommendations: List[str] = []
        if optimal:
            ideal_sets = optimal.get("artifact_sets", [])
            if ideal_sets and not any(s in set_counts for s in ideal_sets):
                recommendations.append(
                    f"Farm {' or '.join(ideal_sets[:2])} for a better set bonus."
                )
            for slot in ("sands", "goblet", "circlet"):
                actual = slot_main_stats.get(slot, "")
                ideal_options = optimal.get("main_stats", {}).get(slot, [])
                if actual and ideal_options and actual not in ideal_options:
                    recommendations.append(
                        f"Replace {slot.title()} main stat ({actual}) with {' or '.join(ideal_options)}."
                    )
            ideal_subs = optimal.get("ideal_substats", [])
            if ideal_subs and substat_score < 2.0:
                recommendations.append(
                    f"Prioritize substats: {', '.join(ideal_subs[:3])}."
                )
        if not recommendations:
            recommendations.append(
                "Build looks solid! Continue farming to upgrade artifact levels and substats."
            )

        return {
            "set_summary": set_summary,
            "main_stats": main_stat_details,
            "set_score": set_score,
            "main_stat_score": main_stat_score,
            "substat_score": substat_score,
            "total_score": total_score,
            "grade": grade,
            "recommendations": recommendations,
            "role": optimal.get("role", "Unknown") if optimal else "Unknown",
        }

    @staticmethod
    def _builtin_character_fallback() -> Dict[int, Dict[str, str]]:
        """
        Hard-coded fallback mapping of Enka avatar IDs to character names.
        Used as the authoritative base so common characters always resolve to
        their real names even when external APIs are unreachable.

        Character IDs and names verified against the Enka Network characters.json
        and loc.json (English TextMap) files.  The previous version of this list
        had a large off-by-one shift starting at ID 10000061 (e.g. Kirara was
        mapped to Aloy's ID, Furina to Chevreuse's ID, etc.).  This version
        contains the correct mappings sourced directly from Enka's API data.

        Note on full vs. short names: Enka returns the game's official English
        names (e.g. "Kaedehara Kazuha", "Sangonomiya Kokomi").  These match the
        keys used in OPTIMAL_BUILDS so build analysis resolves correctly.
        """
        return {
            10000002: {"name": "Kamisato Ayaka",      "element": "Cryo"},
            10000003: {"name": "Jean",                "element": "Anemo"},
            10000005: {"name": "Traveler",            "element": "Anemo"},
            10000006: {"name": "Lisa",                "element": "Electro"},
            10000007: {"name": "Traveler",            "element": "Anemo"},
            10000014: {"name": "Barbara",             "element": "Hydro"},
            10000015: {"name": "Kaeya",               "element": "Cryo"},
            10000016: {"name": "Diluc",               "element": "Pyro"},
            10000020: {"name": "Razor",               "element": "Electro"},
            10000021: {"name": "Amber",               "element": "Pyro"},
            10000022: {"name": "Venti",               "element": "Anemo"},
            10000023: {"name": "Xiangling",           "element": "Pyro"},
            10000024: {"name": "Beidou",              "element": "Electro"},
            10000025: {"name": "Xingqiu",             "element": "Hydro"},
            10000026: {"name": "Xiao",                "element": "Anemo"},
            10000027: {"name": "Ningguang",           "element": "Geo"},
            10000029: {"name": "Klee",                "element": "Pyro"},
            10000030: {"name": "Zhongli",             "element": "Geo"},
            10000031: {"name": "Fischl",              "element": "Electro"},
            10000032: {"name": "Bennett",             "element": "Pyro"},
            10000033: {"name": "Tartaglia",           "element": "Hydro"},
            10000034: {"name": "Noelle",              "element": "Geo"},
            10000035: {"name": "Qiqi",                "element": "Cryo"},
            10000036: {"name": "Chongyun",            "element": "Cryo"},
            10000037: {"name": "Ganyu",               "element": "Cryo"},
            10000038: {"name": "Albedo",              "element": "Geo"},
            10000039: {"name": "Diona",               "element": "Cryo"},
            10000041: {"name": "Mona",                "element": "Hydro"},
            10000042: {"name": "Keqing",              "element": "Electro"},
            10000043: {"name": "Sucrose",             "element": "Anemo"},
            10000044: {"name": "Xinyan",              "element": "Pyro"},
            10000045: {"name": "Rosaria",             "element": "Cryo"},
            10000046: {"name": "Hu Tao",              "element": "Pyro"},
            10000047: {"name": "Kaedehara Kazuha",    "element": "Anemo"},
            10000048: {"name": "Yanfei",              "element": "Pyro"},
            10000049: {"name": "Yoimiya",             "element": "Pyro"},
            10000050: {"name": "Thoma",               "element": "Pyro"},
            10000051: {"name": "Eula",                "element": "Cryo"},
            10000052: {"name": "Raiden Shogun",       "element": "Electro"},
            10000053: {"name": "Sayu",                "element": "Anemo"},
            10000054: {"name": "Sangonomiya Kokomi",  "element": "Hydro"},
            10000055: {"name": "Gorou",               "element": "Geo"},
            10000056: {"name": "Kujou Sara",          "element": "Electro"},
            10000057: {"name": "Arataki Itto",        "element": "Geo"},
            10000058: {"name": "Yae Miko",            "element": "Electro"},
            10000059: {"name": "Shikanoin Heizou",    "element": "Anemo"},
            10000060: {"name": "Yelan",               "element": "Hydro"},
            10000061: {"name": "Kirara",              "element": "Dendro"},
            10000062: {"name": "Aloy",                "element": "Cryo"},
            10000063: {"name": "Shenhe",              "element": "Cryo"},
            10000064: {"name": "Yun Jin",             "element": "Geo"},
            10000065: {"name": "Kuki Shinobu",        "element": "Electro"},
            10000066: {"name": "Kamisato Ayato",      "element": "Hydro"},
            10000067: {"name": "Collei",              "element": "Dendro"},
            10000068: {"name": "Dori",                "element": "Electro"},
            10000069: {"name": "Tighnari",            "element": "Dendro"},
            10000070: {"name": "Nilou",               "element": "Hydro"},
            10000071: {"name": "Cyno",                "element": "Electro"},
            10000072: {"name": "Candace",             "element": "Hydro"},
            10000073: {"name": "Nahida",              "element": "Dendro"},
            10000074: {"name": "Layla",               "element": "Cryo"},
            10000075: {"name": "Wanderer",            "element": "Anemo"},
            10000076: {"name": "Faruzan",             "element": "Anemo"},
            10000077: {"name": "Yaoyao",              "element": "Dendro"},
            10000078: {"name": "Alhaitham",           "element": "Dendro"},
            10000079: {"name": "Dehya",               "element": "Pyro"},
            10000080: {"name": "Mika",                "element": "Cryo"},
            10000081: {"name": "Kaveh",               "element": "Dendro"},
            10000082: {"name": "Baizhu",              "element": "Dendro"},
            10000083: {"name": "Lynette",             "element": "Anemo"},
            10000084: {"name": "Lyney",               "element": "Pyro"},
            10000085: {"name": "Freminet",            "element": "Cryo"},
            10000086: {"name": "Wriothesley",         "element": "Cryo"},
            10000087: {"name": "Neuvillette",         "element": "Hydro"},
            10000088: {"name": "Charlotte",           "element": "Cryo"},
            10000089: {"name": "Furina",              "element": "Hydro"},
            10000090: {"name": "Chevreuse",           "element": "Pyro"},
            10000091: {"name": "Navia",               "element": "Geo"},
            10000092: {"name": "Gaming",              "element": "Pyro"},
            10000093: {"name": "Xianyun",             "element": "Anemo"},
            10000094: {"name": "Chiori",              "element": "Geo"},
            10000095: {"name": "Sigewinne",           "element": "Hydro"},
            10000096: {"name": "Arlecchino",          "element": "Pyro"},
            10000097: {"name": "Sethos",              "element": "Electro"},
            10000098: {"name": "Clorinde",            "element": "Electro"},
            10000099: {"name": "Emilie",              "element": "Dendro"},
            10000100: {"name": "Kachina",             "element": "Geo"},
            10000101: {"name": "Kinich",              "element": "Dendro"},
            10000102: {"name": "Mualani",             "element": "Hydro"},
            10000103: {"name": "Xilonen",             "element": "Geo"},
            10000104: {"name": "Chasca",              "element": "Anemo"},
            10000105: {"name": "Ororon",              "element": "Electro"},
            10000106: {"name": "Mavuika",             "element": "Pyro"},
            10000107: {"name": "Citlali",             "element": "Cryo"},
            10000108: {"name": "Lan Yan",             "element": "Anemo"},
            10000109: {"name": "Yumemizuki Mizuki",   "element": "Anemo"},
            10000110: {"name": "Iansan",              "element": "Electro"},
            10000111: {"name": "Varesa",              "element": "Electro"},
            10000112: {"name": "Escoffier",           "element": "Cryo"},
            10000113: {"name": "Ifa",                 "element": "Anemo"},
            10000114: {"name": "Skirk",               "element": "Cryo"},
            10000115: {"name": "Dahlia",              "element": "Hydro"},
            10000116: {"name": "Ineffa",              "element": "Electro"},
            10000119: {"name": "Lauma",               "element": "Dendro"},
            10000120: {"name": "Flins",               "element": "Electro"},
            10000121: {"name": "Aino",                "element": "Hydro"},
            10000122: {"name": "Nefer",               "element": "Dendro"},
            10000123: {"name": "Durin",               "element": "Pyro"},
            10000124: {"name": "Jahoda",              "element": "Anemo"},
            # IDs beyond 10000124 are populated at runtime from Enka Network
            # (characters.json + loc.json) and the jmsszkzlz API, both of
            # which are auto-fetched on startup.
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
        # Ensure artifact set names are populated
        await self._ensure_artifact_data()

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
                main_stat_name = self._prop_id_to_stat_name(main_stat.get("mainPropId", ""))
                equip_type = flat.get("equipType", "")
                icon = flat.get("icon", "")
                # Parse each substat into a structured dict with human-readable name
                parsed_substats = [
                    {
                        "name": self._prop_id_to_stat_name(s.get("appendPropId", "")),
                        "value": s.get("statValue", 0.0),
                    }
                    for s in sub_stats
                ]
                # Resolve the human-readable artifact set name from the icon ID
                resolved_set_name = self._get_artifact_set_name(icon)
                artifacts.append({
                    "slot": equip_type.replace("EQUIP_", "").title(),
                    "equip_type": equip_type,
                    "set_name": resolved_set_name,
                    "icon": icon,
                    "rarity": flat.get("rankLevel"),
                    "level": equip.get("reliquary", {}).get("level", 1) - 1,
                    # Backward-compatible main_stat label (kept for existing callers)
                    "main_stat": main_stat_name,
                    # New extended fields for optimizer
                    "main_stat_value": main_stat.get("statValue", 0.0),
                    "substats": parsed_substats,
                    # Legacy field for backward compatibility
                    "sub_stat_count": len(sub_stats),
                    # Additional fields
                    "set_name_hash": flat.get("setNameTextMapHash", ""),
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

        character: Dict[str, Any] = {
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
        # Add build analysis when artifact data is available
        if artifacts:
            try:
                character["build_analysis"] = self.analyze_character_build(character)
            except Exception as exc:
                logger.warning(f"Build analysis failed for {char_name}: {exc}")
                character["build_analysis"] = None
        else:
            character["build_analysis"] = None
        return character