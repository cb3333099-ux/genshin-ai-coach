import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ChatInterface:
    """AI Chat interface for Genshin Impact recommendations"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize chat interface with OpenAI"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set - chat will use mock responses")
            self.client = None
        else:
            try:
                import httpx
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, http_client=httpx.Client())
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e} - using mock responses")
                self.client = None
        
        self.conversation_history = []
        
    async def chat(self, query: str, account_data: dict = None) -> str:
        """
        Process user query and return AI response
        
        Args:
            query: User's question
            account_data: Optional player account data for context
            
        Returns:
            AI response string
        """
        try:
            if not self.client:
                return self._get_mock_response(query)
            
            # Build system prompt
            system_prompt = self._get_system_prompt()
            
            # Add context if available
            context_msg = ""
            if account_data:
                context_msg = f"\n\nPlayer Context:\n"
                context_msg += f"- Nickname: {account_data.get('nickname', 'Unknown')}\n"
                context_msg += f"- Level: {account_data.get('level', 'Unknown')}\n"
                context_msg += f"- World Level: {account_data.get('world_level', 'Unknown')}\n"
            
            # Create user message
            user_message = query + context_msg
            
            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *self.conversation_history
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            # Extract response
            assistant_message = response.choices[0].message.content
            
            # Add to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            logger.info(f"Chat response generated for query: {query}")
            return assistant_message
            
        except Exception as e:
            logger.error(f"Error in chat interface: {str(e)}")
            return self._get_mock_response(query)
    
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
            "beginner": "For beginners, I recommend focusing on Amber, Barbara, and Xiangling. They're all free characters and form a solid team. Level them up together and farm artifacts from Spiral Abyss rewards.",
            "farm": "Today's best farming priority: Domain of Guyun for Guyun Domain artifacts (great for DPS builds). Also consider farming Talent materials for your main characters.",
            "team": "Here are some great beginner-friendly teams:\n1. Pyro: Amber (DPS) + Xiangling (Sub-DPS) + Barbara (Healer) + Anemo (Support)\n2. Hydro: Barbara (Healer) + Xingqiu (Sub-DPS) + Fischl (Elemental Reaction) + Any DPS",
            "abyss": "For Spiral Abyss: Focus on building two balanced teams. Team 1 should have a strong DPS with support. Team 2 should have another DPS with elemental reactions. Start with floor 1-8 for guaranteed rewards.",
        }
        
        # Find matching response
        query_lower = query.lower()
        for key, response in mock_responses.items():
            if key in query_lower:
                return response
        
        return "I'm Genshin AI Coach! Ask me about team compositions, artifact farming, character builds, or Spiral Abyss strategies. (Note: OpenAI API not configured - showing template responses)"
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []