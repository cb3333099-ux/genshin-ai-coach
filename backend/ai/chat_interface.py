import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ChatInterface:
    """AI Chat interface for Genshin Impact recommendations"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize chat interface with Groq"""
        
        # Use the api_key passed in from main.py
        self.api_key = api_key

        if not self.api_key:
            logger.warning("❌ GROQ_API_KEY not found - chat will use mock responses")
            self.client = None
        else:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.info("✅ Groq client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Groq: {e}")
                self.client = None

        self.conversation_history = []

    async def chat(self, query: str, account_data: dict = None) -> str:
        """Process user query and return AI response"""
        try:
            logger.info(f"📨 Chat request received: {query[:50]}...")
            logger.info(f"🔍 Client status: {self.client is not None}")
            logger.info(f"🔑 API Key present: {bool(self.api_key)}")
            
            if not self.client:
                logger.warning("⚠️ Using mock response - Groq client not available")
                return self._get_mock_response(query)

            system_prompt = self._get_system_prompt()
            context_msg = ""
            if account_data:
                context_msg = self._build_player_context(account_data)

            user_message = query + context_msg

            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })

            try:
                logger.info("🚀 Calling Groq API with model: llama-3.3-70b-versatile...")
                response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *self.conversation_history
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )

                assistant_message = response.choices[0].message.content

                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })

                logger.info("✅ Groq response generated successfully")
                return assistant_message
                
            except Exception as api_error:
                logger.error(f"❌ Groq API error: {str(api_error)}")
                logger.error(f"   Error type: {type(api_error)}")
                logger.warning("⚠️ Falling back to mock response")
                return self._get_mock_response(query)

        except Exception as e:
            logger.error(f"❌ Error in chat interface: {str(e)}")
            return self._get_mock_response(query)

    def _build_player_context(self, account_data: dict) -> str:
        """Build rich player context string for the AI prompt"""
        lines = ["\n\n=== PLAYER ACCOUNT DATA ==="]
        lines.append(f"Nickname: {account_data.get('nickname', 'Unknown')}")
        lines.append(f"Adventure Rank: {account_data.get('level', 'Unknown')}")
        lines.append(f"World Level: {account_data.get('world_level', 'Unknown')}")

        abyss_floor = account_data.get("abyss_floor", 0)
        abyss_chamber = account_data.get("abyss_chamber", 0)
        if abyss_floor:
            lines.append(f"Spiral Abyss Progress: Floor {abyss_floor}-{abyss_chamber}")

        achievements = account_data.get("achievement_count", 0)
        if achievements:
            lines.append(f"Achievements: {achievements}")

        sig = account_data.get("signature", "")
        if sig:
            lines.append(f"Signature: {sig}")

        characters = account_data.get("characters", [])
        if characters:
            lines.append(f"\nShowcased Characters ({len(characters)} total):")
            for char in characters:
                name = char.get("name", "Unknown")
                element = char.get("element", "")
                level = char.get("level", 1)
                ascension = char.get("ascension", 0)
                constellations = char.get("constellations", 0)
                friendship = char.get("friendship", 0)

                char_line = f"  • {name} (C{constellations}) | Lv.{level}/{'90' if ascension >= 6 else str(20 + ascension * 10)}"
                if element:
                    char_line += f" | {element}"
                if friendship:
                    char_line += f" | Friendship {friendship}"
                lines.append(char_line)

                weapon = char.get("weapon", {})
                if weapon and weapon.get("level"):
                    w_level = weapon.get("level")
                    w_ref = weapon.get("refinement", 1)
                    w_rarity = weapon.get("rarity", "?")
                    lines.append(f"    Weapon: {w_rarity}★ | Lv.{w_level} | R{w_ref}")

                talents = char.get("talents", {})
                if talents:
                    na = talents.get("normal_attack", "?")
                    es = talents.get("elemental_skill", "?")
                    eb = talents.get("elemental_burst", "?")
                    lines.append(f"    Talents: NA:{na} / Skill:{es} / Burst:{eb}")

                stats = char.get("stats", {})
                if stats:
                    stat_parts = []
                    for k, v in stats.items():
                        stat_parts.append(f"{k}:{v}")
                    lines.append(f"    Stats: {' | '.join(stat_parts)}")

                artifacts = char.get("artifacts", [])
                if artifacts:
                    max_level = max((a.get("level", 0) for a in artifacts), default=0)
                    rarity_5 = sum(1 for a in artifacts if a.get("rarity") == 5)
                    lines.append(f"    Artifacts: {len(artifacts)} pieces | {rarity_5}x 5★ | Best: +{max_level}")

        lines.append("\nUSE THIS DATA to give personalized advice about this player's specific characters, builds, and progression.")
        lines.append("=== END PLAYER DATA ===")
        return "\n".join(lines)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI coach"""
        return """You are Genshin AI Coach, an expert Genshin Impact gaming assistant.

You have deep knowledge of:
- Character mechanics and optimal builds
- Artifact farming strategies
- Team compositions and elemental reactions
- Spiral Abyss strategies
- Resource management and progression
- Daily farming priorities
- Banner evaluation and pull recommendations

Guidelines:
1. Provide specific, actionable recommendations
2. Explain your reasoning clearly
3. Be encouraging and helpful
4. Consider the player's current level and progression
5. Suggest efficient farming routes
6. Recommend practical team compositions

Always format responses clearly with:
- Main recommendation at the top
- Supporting details
- Any warnings or considerations"""

    def _get_mock_response(self, query: str) -> str:
        """Get a mock response when API is not available"""
        mock_responses = {
            "beginner": "For beginners, I recommend focusing on Amber, Barbara, and Xiangling. They're all free characters and form a solid team.",
            "farm": "Today's best farming priority: Domain of Guyun for artifacts. Also farm Talent materials for your main characters.",
            "team": "Here are great beginner teams:\n1. Pyro: Amber (DPS) + Xiangling (Sub-DPS) + Barbara (Healer)\n2. Hydro: Barbara (Healer) + Xingqiu (Sub-DPS) + Fischl",
            "abyss": "For Spiral Abyss: Build two balanced teams with strong DPS and elemental reactions. Focus on elemental mastery for reaction damage.",
            "hu tao": "Hu Tao is a top-tier Pyro DPS. Build her with: HP% sands, Pyro DMG goblet, Crit Rate/DMG circlet. Target 60-70% Crit Rate and 120%+ Crit DMG.",
            "spiral": "For Spiral Abyss: Build two balanced teams with strong DPS and elemental reactions.",
            "artifact": "Artifacts are crucial! Farm domains that match your main DPS character. Focus on main stats first, then substats.",
            "build": "For any character, prioritize: Main DPS stat → Crit Rate/DMG → ATK% → Secondary stats based on character.",
        }

        query_lower = query.lower()
        for key, response in mock_responses.items():
            if key in query_lower:
                return response

        return "I'm Genshin AI Coach! Ask about team compositions, artifact farming, character builds, or Spiral Abyss strategies."

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []