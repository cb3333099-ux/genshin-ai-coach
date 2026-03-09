"""
Stat calculator for the artifact optimizer.

Implements:
- Base character stats (level 90 / ascension 6 defaults)
- Weapon stat contribution
- Artifact main-stat and substat accumulation
- Artifact set bonuses (2-piece and 4-piece)
- Team buff placeholders
- Final build scoring against user-defined targets
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .models import Artifact, Build, Weapon

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Character base stat database (level 90, ascension 6)
# Values represent: base_hp, base_atk, base_def, base element stat, element stat type
# This is a representative subset; extend as needed.
# ---------------------------------------------------------------------------

CHARACTER_BASE_STATS: Dict[str, Dict[str, float]] = {
    # ---- Pyro ----
    "Hu Tao":       {"HP": 15552, "ATK": 106, "DEF": 876, "Crit DMG": 0.884},
    "Yoimiya":      {"HP": 10164, "ATK": 323, "DEF": 615, "Crit Rate": 0.242},
    "Diluc":        {"HP": 12981, "ATK": 335, "DEF": 784, "Crit Rate": 0.192},
    "Klee":         {"HP": 10287, "ATK": 311, "DEF": 615, "Crit DMG": 0.384},
    "Yanfei":       {"HP": 9352,  "ATK": 240, "DEF": 587, "Crit Rate": 0.192},
    "Xiangling":    {"HP": 10875, "ATK": 225, "DEF": 669, "Elemental Mastery": 96},
    "Bennett":      {"HP": 12397, "ATK": 191, "DEF": 771, "Energy Recharge": 0.267},
    # ---- Hydro ----
    "Tartaglia":    {"HP": 13103, "ATK": 301, "DEF": 815, "Hydro DMG Bonus": 0.288},
    "Yelan":        {"HP": 14450, "ATK": 244, "DEF": 548, "Crit Rate": 0.242},
    "Mona":         {"HP": 10409, "ATK": 287, "DEF": 653, "Energy Recharge": 0.32},
    "Kokomi":       {"HP": 13471, "ATK": 234, "DEF": 657, "HP%": 0.25},
    "Xingqiu":      {"HP": 10222, "ATK": 202, "DEF": 758, "ATK%": 0.24},
    "Barbara":      {"HP": 13500, "ATK": 153, "DEF": 572, "Energy Recharge": 0.2},
    "Neuvilette":   {"HP": 14695, "ATK": 302, "DEF": 739, "Crit DMG": 0.884},
    "Furina":       {"HP": 15307, "ATK": 244, "DEF": 696, "Crit Rate": 0.242},
    # ---- Cryo ----
    "Ganyu":        {"HP": 9797,  "ATK": 335, "DEF": 630, "Crit DMG": 0.384},
    "Eula":         {"HP": 13226, "ATK": 342, "DEF": 751, "Crit DMG": 0.884},
    "Ayaka":        {"HP": 12858, "ATK": 342, "DEF": 789, "Crit DMG": 0.884},
    "Rosaria":      {"HP": 12289, "ATK": 234, "DEF": 710, "ATK%": 0.24},
    "Diona":        {"HP": 9570,  "ATK": 167, "DEF": 601, "Energy Recharge": 0.267},
    "Wriothesley":  {"HP": 15307, "ATK": 335, "DEF": 696, "Crit DMG": 0.884},
    # ---- Electro ----
    "Raiden Shogun":{"HP": 12907, "ATK": 337, "DEF": 789, "Energy Recharge": 0.32},
    "Yae Miko":     {"HP": 10372, "ATK": 340, "DEF": 569, "Crit Rate": 0.242},
    "Fischl":       {"HP": 9189,  "ATK": 244, "DEF": 594, "ATK%": 0.24},
    "Beidou":       {"HP": 13050, "ATK": 225, "DEF": 648, "Elemental Mastery": 96},
    "Keqing":       {"HP": 13103, "ATK": 323, "DEF": 799, "Crit DMG": 0.384},
    "Cyno":         {"HP": 14450, "ATK": 310, "DEF": 745, "Elemental Mastery": 115},
    # ---- Anemo ----
    "Venti":        {"HP": 10531, "ATK": 192, "DEF": 658, "Energy Recharge": 0.32},
    "Kazuha":       {"HP": 13348, "ATK": 297, "DEF": 807, "Elemental Mastery": 115},
    "Xiao":         {"HP": 12736, "ATK": 349, "DEF": 799, "Crit Rate": 0.242},
    "Wanderer":     {"HP": 10164, "ATK": 328, "DEF": 587, "Crit Rate": 0.242},
    "Jean":         {"HP": 14695, "ATK": 239, "DEF": 769, "Energy Recharge": 0.267},
    "Sucrose":      {"HP": 9244,  "ATK": 170, "DEF": 703, "Elemental Mastery": 96},
    # ---- Geo ----
    "Zhongli":      {"HP": 14695, "ATK": 251, "DEF": 738, "Geo DMG Bonus": 0.288},
    "Albedo":       {"HP": 13226, "ATK": 251, "DEF": 876, "Geo DMG Bonus": 0.288},
    "Itto":         {"HP": 14617, "ATK": 237, "DEF": 959, "Crit Rate": 0.242},
    "Ningguang":    {"HP": 9787,  "ATK": 212, "DEF": 573, "Geo DMG Bonus": 0.288},
    # ---- Dendro ----
    "Nahida":       {"HP": 10360, "ATK": 298, "DEF": 630, "Elemental Mastery": 115},
    "Alhaitham":    {"HP": 13715, "ATK": 299, "DEF": 789, "Elemental Mastery": 115},
    "Tighnari":     {"HP": 10657, "ATK": 267, "DEF": 630, "Crit Rate": 0.242},
    "Collei":       {"HP": 9787,  "ATK": 189, "DEF": 599, "Energy Recharge": 0.267},
    "Baizhu":       {"HP": 14450, "ATK": 261, "DEF": 657, "HP%": 0.25},
    # ---- Universal fallback ----
    "_default":     {"HP": 12000, "ATK": 250, "DEF": 750},
}

# ---------------------------------------------------------------------------
# Artifact set bonus database
# Two-piece and four-piece bonuses expressed as {stat: value} addends.
# Extend this table to cover more sets.
# ---------------------------------------------------------------------------

SET_BONUSES: Dict[str, Dict[str, Dict[str, float]]] = {
    "GladiatorsFinale": {
        "2pc": {"ATK%": 0.18},
        "4pc": {},  # 4pc bonus is conditional (only Normal attacks) - omit
    },
    "WanderersTroupe": {
        "2pc": {"Elemental Mastery": 80},
        "4pc": {},
    },
    "ThunderingFury": {
        "2pc": {"Electro DMG Bonus": 0.15},
        "4pc": {},
    },
    "Thundersoother": {
        "2pc": {},
        "4pc": {},
    },
    "CrimsonWitchOfFlames": {
        "2pc": {"Pyro DMG Bonus": 0.15},
        "4pc": {},
    },
    "Lavawalker": {
        "2pc": {},
        "4pc": {},
    },
    "BlizzardStrayer": {
        "2pc": {"Cryo DMG Bonus": 0.15},
        "4pc": {"Crit Rate": 0.20},  # assumes enemy frozen
    },
    "HeartOfDepth": {
        "2pc": {"Hydro DMG Bonus": 0.15},
        "4pc": {},
    },
    "ViridescentVenerer": {
        "2pc": {"Anemo DMG Bonus": 0.15},
        "4pc": {},
    },
    "ArchaicPetra": {
        "2pc": {"Geo DMG Bonus": 0.15},
        "4pc": {},
    },
    "RetracingBolide": {
        "2pc": {},
        "4pc": {},
    },
    "NoblesseOblige": {
        "2pc": {"Elemental Burst DMG Bonus": 0.20},
        "4pc": {},
    },
    "BloodstainedChivalry": {
        "2pc": {"Physical DMG Bonus": 0.25},
        "4pc": {},
    },
    "MaidenBeloved": {
        "2pc": {"Healing Bonus": 0.15},
        "4pc": {},
    },
    "PaleFlame": {
        "2pc": {"Physical DMG Bonus": 0.25},
        "4pc": {},
    },
    "ShimenawasReminiscence": {
        "2pc": {"ATK%": 0.18},
        "4pc": {},
    },
    "EmblemOfSeveredFate": {
        "2pc": {"Energy Recharge": 0.20},
        "4pc": {},  # 4pc gives DMG bonus from ER, context-dependent
    },
    "HuskOfOpulentDreams": {
        "2pc": {"DEF%": 0.30},
        "4pc": {},
    },
    "OceanHuedClam": {
        "2pc": {"Healing Bonus": 0.15},
        "4pc": {},
    },
    "VermillionHereafter": {
        "2pc": {"ATK%": 0.18},
        "4pc": {},
    },
    "EchoesOfAnOffering": {
        "2pc": {"ATK%": 0.18},
        "4pc": {},
    },
    "DeepwoodMemories": {
        "2pc": {"Dendro DMG Bonus": 0.15},
        "4pc": {},
    },
    "GildedDreams": {
        "2pc": {"Elemental Mastery": 80},
        "4pc": {},
    },
    "FlowerOfParadiseLost": {
        "2pc": {"Elemental Mastery": 80},
        "4pc": {},
    },
    "DesertPavilionChronicle": {
        "2pc": {"Anemo DMG Bonus": 0.15},
        "4pc": {},
    },
    "NymphsDream": {
        "2pc": {"Hydro DMG Bonus": 0.15},
        "4pc": {},
    },
    "VourukashasGlow": {
        "2pc": {"HP%": 0.20},
        "4pc": {},
    },
    "MarechausseeHunter": {
        "2pc": {"Crit Rate": 0.12},
        "4pc": {},
    },
    "GoldenTroupe": {
        "2pc": {},
        "4pc": {},
    },
    "SongOfDaysPast": {
        "2pc": {"Healing Bonus": 0.15},
        "4pc": {},
    },
    "NighttimeWhispersInTheEchoingWoods": {
        "2pc": {"ATK%": 0.18},
        "4pc": {},
    },
    "FragmentOfHarmonicWhimsy": {
        "2pc": {"ATK%": 0.18},
        "4pc": {},
    },
    "UnfinishedReverie": {
        "2pc": {},
        "4pc": {},
    },
}


def _get_base_stats(character_key: str) -> Dict[str, float]:
    """Return base stats for a character at lv90/A6, with fallback."""
    return dict(CHARACTER_BASE_STATS.get(character_key, CHARACTER_BASE_STATS["_default"]))


def apply_artifact_set_bonus(
    stats: Dict[str, float],
    artifacts: Dict[str, Artifact],
) -> Dict[str, float]:
    """
    Count equipped artifact sets and apply 2-piece / 4-piece bonuses.

    Modifies *stats* in place and also returns it for convenience.
    """
    set_counts: Dict[str, int] = {}
    for art in artifacts.values():
        set_counts[art.set_key] = set_counts.get(art.set_key, 0) + 1

    for set_key, count in set_counts.items():
        bonuses = SET_BONUSES.get(set_key, {})
        if count >= 2:
            for stat, value in bonuses.get("2pc", {}).items():
                stats[stat] = stats.get(stat, 0.0) + value
        if count >= 4:
            for stat, value in bonuses.get("4pc", {}).items():
                stats[stat] = stats.get(stat, 0.0) + value

    return stats


def _apply_weapon(stats: Dict[str, float], weapon: Optional[Weapon]) -> None:
    """Add weapon base ATK and sub-stat to the stat dict."""
    if weapon is None:
        return
    stats["ATK"] = stats.get("ATK", 0.0) + weapon.base_atk
    if weapon.sub_stat and weapon.sub_stat_value:
        stats[weapon.sub_stat] = stats.get(weapon.sub_stat, 0.0) + weapon.sub_stat_value


def _apply_artifact_stats(
    stats: Dict[str, float],
    artifacts: Dict[str, Artifact],
) -> None:
    """Accumulate main-stat and substat values from all artifacts."""
    for art in artifacts.values():
        # Main stat
        stats[art.main_stat] = stats.get(art.main_stat, 0.0) + art.main_stat_value
        # Substats
        for sub in art.substats:
            stats[sub.stat] = stats.get(sub.stat, 0.0) + sub.value


def calculate_character_stats(
    character_key: str,
    artifacts: Dict[str, Artifact],
    weapon: Optional[Weapon] = None,
    buffs: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Compute the final stat dictionary for a character equipped with the
    given artifacts, weapon, and team buffs.

    Steps (matches genshin-optimizer calculation order):
      1. Base stats (character lv90 / ascension 6)
      2. Weapon base ATK + sub-stat
      3. Artifact main-stats and sub-stats
      4. Artifact set bonuses (2pc / 4pc)
      5. External buffs (resonance, team skills, food, etc.)

    Returns a flat {stat_name: value} dict.  Percentage stats are stored
    as decimals (e.g. Crit Rate 0.65 = 65%).
    """
    stats: Dict[str, float] = _get_base_stats(character_key)

    _apply_weapon(stats, weapon)
    _apply_artifact_stats(stats, artifacts)
    apply_artifact_set_bonus(stats, artifacts)

    # External buffs (additive)
    if buffs:
        for stat, value in buffs.items():
            stats[stat] = stats.get(stat, 0.0) + value

    return stats


def calculate_build_score(
    stats: Dict[str, float],
    target_stats: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Score a build against the user's target stats.

    Each target stat contributes:
        weight * min(actual / target, 1.0)

    so reaching the target gives full weight; exceeding it gives no extra
    reward (to avoid over-capping e.g. Crit Rate at 100%).

    If no weights are provided, all target stats are weighted equally.

    Returns a value in [0, total_weight].
    """
    if not target_stats:
        return 0.0

    if weights is None:
        weights = {stat: 1.0 for stat in target_stats}

    score = 0.0
    for stat, target_value in target_stats.items():
        if target_value <= 0:
            continue
        actual = stats.get(stat, 0.0)
        w = weights.get(stat, 1.0)
        score += w * min(actual / target_value, 1.0)

    return score
