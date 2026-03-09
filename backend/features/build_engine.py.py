"""
Build recommendation engine
"""

class BuildEngine:
    """Generates character build recommendations"""
    
    ARTIFACT_SETS = {
        "crimson_witch": "4-piece for Pyro DPS",
        "blizzard_strayer": "4-piece for Cryo DPS",
    }
    
    @staticmethod
    def recommend_build(character_name):
        builds = {
            "bennett": {
                "artifacts": "Noblesse Oblige (4-piece)",
                "main_stats": "HP%, Pyro DMG%, Healing Bonus",
                "weapons": "Aquila Favonia, The Catch",
            }
        }
        return builds.get(character_name.lower(), {"artifacts": "Check character guides"})