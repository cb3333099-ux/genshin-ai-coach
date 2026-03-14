import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants and helpers
# ---------------------------------------------------------------------------

INTELLIGENT_SYSTEM_PROMPT = """
You are a professional Genshin Impact coach with expertise in character builds, artifact optimization, and resin management.

YOUR COACHING ROLE:
- Analyze the player's actual characters, artifacts, and equipment
- Identify build strengths and weaknesses with specific numbers
- Recommend optimal farming priorities based on THEIR roster
- Calculate personalized resin usage strategy
- Suggest team compositions from their existing characters
- Give character-specific, actionable advice (NEVER generic)

CRITICAL RULES FOR RESPONSES:
1. ALWAYS base recommendations on player data provided
2. ONLY recommend Original Resin farming (artifacts, talents, materials)
3. NEVER mention Spiral Abyss resin usage - it doesn't exist!
4. Be SPECIFIC: use character names, domain names, artifact set names
5. Include quality scores and specific stat recommendations
6. Estimate farming timelines based on domain drops
7. Prioritize fixing weakest builds first

RESPONSE FORMAT:
- Current Status (what's good, what needs work)
- Top 3 Farming Priorities (specific domains with reasons)
- Daily Resin Allocation (% split)
- Weekly Schedule (when to farm what)
- Time to Completion (estimated days/weeks)
- Alternative options (if applicable)

If no player data provided, ask for UID to give personalized advice.
"""

_DEFAULT_FARMING_TIME = "2-3 weeks"

_DOMAIN_MAPPING = {
    "Crimson Witch of Flames": {"location": "Mondstadt"},
    "Viridescent Venerer": {"location": "Mondstadt"},
    "Heart of Depth": {"location": "Mondstadt (Dragonspine)"},
    "Blizzard Strayer": {"location": "Mondstadt"},
    "Emblem of Severed Fate": {"location": "Inazuma"},
    "Deepwood Memories": {"location": "Sumeru"},
    "Husk of Opulent Dreams": {"location": "Inazuma"},
    "Gilded Dreams": {"location": "Sumeru"},
    "Ocean-Hued Clam": {"location": "Inazuma"},
    "Echoes of an Offering": {"location": "Inazuma"},
    "Vermillion Hereafter": {"location": "Inazuma"},
    "Flower of Paradise Lost": {"location": "Sumeru"},
    "Desert Pavilion Chronicle": {"location": "Sumeru"},
    "Noblesse Oblige": {"location": "Mondstadt"},
    "Thundering Fury": {"location": "Mondstadt"},
    "Lavawalker": {"location": "Mondstadt"},
    "Maiden Beloved": {"location": "Mondstadt"},
    "Pale Flame": {"location": "Mondstadt (Dragonspine)"},
    "Bloodstained Chivalry": {"location": "Mondstadt"},
    "Archaic Petra": {"location": "Liyue"},
    "Retracing Bolide": {"location": "Liyue"},
    "Tenacity of the Millelith": {"location": "Liyue"},
    "Shimenawa's Reminiscence": {"location": "Inazuma"},
}

_ELEMENT_DOMAINS = {
    "Pyro": "Crimson Witch of Flames",
    "Hydro": "Heart of Depth",
    "Cryo": "Blizzard Strayer",
    "Anemo": "Viridescent Venerer",
    "Electro": "Emblem of Severed Fate",
    "Dendro": "Deepwood Memories",
    "Geo": "Husk of Opulent Dreams",
}


def calculate_farming_priorities(weak_builds: list, char_db: dict = None) -> list:
    """Calculate top farming domains based on weak builds, sorted by priority."""
    priorities = []
    for build in weak_builds:
        set_name = build.get("set", "Unknown")
        # If set is unknown/empty, fall back to element-based recommendation
        if not set_name or set_name == "Unknown":
            element = build.get("element", "")
            set_name = _ELEMENT_DOMAINS.get(element, "Unknown")
        domain_info = _DOMAIN_MAPPING.get(set_name, {})
        priorities.append({
            "character": build["character"],
            "set": set_name,
            "quality": build["quality"],
            "location": domain_info.get("location", "Unknown"),
            "farming_time": _DEFAULT_FARMING_TIME,
            "priority_score": 10 - build["quality"],
        })
    return sorted(priorities, key=lambda x: x["priority_score"], reverse=True)


def get_resin_allocation(weak_builds: list, total_resin: int = 180) -> str:
    """Calculate and format optimal daily resin allocation."""
    if not weak_builds:
        return "All your builds are optimal! Consider farming for backup artifacts."

    primary_pct = 60
    secondary_pct = 20
    weekly_pct = 20

    primary_resin = int(total_resin * primary_pct / 100)
    secondary_resin = int(total_resin * secondary_pct / 100)
    weekly_resin = int(total_resin * weekly_pct / 100)

    return (
        f"Daily Resin Allocation ({total_resin} resin/day):\n"
        f"- {primary_pct}% ({primary_resin} resin) → Priority domain\n"
        f"- {secondary_pct}% ({secondary_resin} resin) → Secondary domain\n"
        f"- {weekly_pct}% ({weekly_resin} resin) → Weekly bosses (3x/week)\n\n"
        "Recommended: Use Condensed Resin (4 runs = 160 resin total)"
    )


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

        achievements = account_data.get("achievement_count", 0)
        if achievements:
            lines.append(f"Achievements: {achievements}")

        sig = account_data.get("signature", "")
        if sig:
            lines.append(f"Signature: {sig}")

        characters = account_data.get("characters", [])
        weak_builds = []

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

                build_analysis = char.get("build_analysis")
                if build_analysis:
                    score = build_analysis.get("total_score", 0)
                    grade = build_analysis.get("grade", "")
                    set_summary = build_analysis.get("set_summary", "")
                    role = build_analysis.get("role", "")
                    if score >= 8.5:
                        status = "✅ Optimal"
                    elif score >= 7:
                        status = "⚠️ Needs upgrade"
                    else:
                        status = "🔴 Poor"
                    lines.append(f"    Build Quality: {score}/10 ({grade}) {status} | Role: {role}")
                    if set_summary:
                        lines.append(f"    Artifact Set: {set_summary}")
                    main_stats = build_analysis.get("main_stats", {})
                    if main_stats:
                        ms_parts = [f"{k.title()}: {v}" for k, v in main_stats.items()]
                        lines.append(f"    Main Stats: {' | '.join(ms_parts)}")
                    recs = build_analysis.get("recommendations", [])
                    if recs:
                        lines.append(f"    Build Tips: {recs[0]}")

                    # Track weak builds for priority calculation
                    if score < 8:
                        weak_builds.append({
                            "character": name,
                            "element": element,
                            "quality": score,
                            "set": set_summary or "",
                        })

        # Farming priorities using module-level helper
        priorities = calculate_farming_priorities(weak_builds)
        lines.append("\nFARMING PRIORITIES:")
        if priorities:
            for i, p in enumerate(priorities[:3], 1):
                lines.append(
                    f"{i}. {p['character']} needs {p['set']}"
                    f" (Current: {p['quality']}/10 | {p['location']} | Est. {p['farming_time']})"
                )
        else:
            lines.append("No urgent farming priorities identified.")

        # Resin allocation using module-level helper
        lines.append("\nRESIN ALLOCATION:")
        lines.append(get_resin_allocation(weak_builds))

        lines.append("\nUSE THIS DATA to give personalized advice about this player's specific characters, builds, and progression.")
        lines.append("Remember: Base your recommendations on their actual character data, not generic advice.")
        lines.append("=== END PLAYER DATA ===")
        return "\n".join(lines)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI coach"""
        return INTELLIGENT_SYSTEM_PROMPT

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