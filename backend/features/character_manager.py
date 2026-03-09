# Character Manager

This module manages character data, builds recommendations, and team compositions based on player characters.

class Character:
    def __init__(self, name, role, element, weapon):
        self.name = name
        self.role = role  # e.g., DPS, Support
        self.element = element  # e.g., Anemo, Geo
        self.weapon = weapon  # e.g., Sword, Bow

class CharacterManager:
    def __init__(self):
        self.characters = []

    def add_character(self, character):
        self.characters.append(character)

    def get_recommendations(self, player_characters):
        # Logic to build recommendations based on player characters
        recommendations = []
        # Example logic (to be replaced with actual logic):
        for character in self.characters:
            if character not in player_characters:
                recommendations.append(character)
        return recommendations

    def build_team_composition(self, player_characters):
        # Logic to build team compositions
        # Example placeholder logic
        return player_characters[:4]  # Return first four characters as a team composition

