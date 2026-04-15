
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class FallbackService:
    """
    Handles logic when the primary LLM (Gemini) is unavailable due to limits or errors.
    Uses rule-based heuristics and templates to ensure the user ALWAYS gets a response.
    """
    
    @staticmethod
    def get_fallback_decision(user_input: str) -> Dict[str, Any]:
        """
        Determine intent and data needs using regex/keywords.
        """
        user_input = user_input.lower().strip()
        
        # 1. Simple Greetings
        if user_input in ["hi", "hello", "hey", "hola", "greetings", "good morning", "good afternoon", "good evening"]:
            return {
                "needs_data": False,
                "intent": "greeting",
                "complexity": "simple",
                "reasoning": "Fallback: Simple greeting detected"
            }
            
        # 2. Time/Date queries
        if any(w in user_input for w in ["time", "date", "day is it", "clock"]):
             return {
                "needs_data": False,
                "intent": "time",
                "complexity": "simple",
                "reasoning": "Fallback: Time query detected"
            }

        # 3. Explicit Research/Search signals
        search_keywords = [
            "search", "find", "who is", "what is", "news", "latest", 
            "weather", "price", "stock", "compare", "vs", "difference"
        ]
        if any(w in user_input for w in search_keywords):
             return {
                "needs_data": True,
                "intent": "research",
                "complexity": "medium",
                "reasoning": "Fallback: Research keywords detected"
            }
            
        # Default: Assume simple chat or knowledge query that might need data
        # To be safe in fallback mode, we default to needing data if it looks like a question
        needs_data = "?" in user_input or len(user_input) > 20
        
        return {
            "needs_data": needs_data,
            "intent": "research" if needs_data else "chat",
            "complexity": "simple",
            "reasoning": "Fallback: Default heuristic"
        }

    @staticmethod
    def generate_fallback_response(user_input: str, fetched_data: str, analysis: str) -> str:
        """
        Generate a template-based response using available data.
        """
        # If we have fetched data, summarize it simply
        if fetched_data and len(fetched_data) > 20:
            # Simple extraction of likely relevant text
            # This is naive but better than nothing
            content_preview = fetched_data[:500].replace("\n", " ") + "..."
            
            return f"Here is what I found:\n\n{fetched_data}\n\n(I provided the raw data as I couldn't process it deeply right now.)"
            
        # If no data, checks for simple intents
        user_input_lower = user_input.lower()
        
        if user_input_lower in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]:
            return f"Hello! I'm TaskPilot AI. How can I help you today?"
            
        if "time" in user_input_lower:
            from datetime import datetime
            return f"Current system time is: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
        return f"I received your request: '{user_input}'.\n\nHowever, I'm currently operating on limited capacity and couldn't process this fully. Please try again in a moment or try a simpler request."
