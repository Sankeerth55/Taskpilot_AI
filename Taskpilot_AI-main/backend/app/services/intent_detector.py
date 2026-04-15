"""Intent Detection - Understands what the user wants TaskPilot AI to DO."""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any


class TaskIntent(str, Enum):
    """Types of tasks TaskPilot AI can execute."""
    # Research and Information
    RESEARCH = "research"  # Deep investigation of a topic
    COMPARE = "compare"  # Compare options/products/services
    RECOMMEND = "recommend"  # Provide recommendations
    EXPLAIN = "explain"  # Explain complex topics
    SUMMARIZE = "summarize"  # Summarize information
    
    # Analysis Tasks
    ANALYZE_FILE = "analyze_file"  # Analyze uploaded files
    EXTRACT_DATA = "extract_data"  # Extract specific data
    CALCULATE = "calculate"  # Perform calculations
    EVALUATE = "evaluate"  # Evaluate options/decisions
    
    # Planning Tasks
    PLAN = "plan"  # Create plans or strategies
    GUIDE = "guide"  # Provide step-by-step guidance
    SUGGEST = "suggest"  # Suggest solutions
    
    # Creation Tasks
    DRAFT = "draft"  # Draft content
    ORGANIZE = "organize"  # Organize information
    
    # Information Retrieval
    FIND = "find"  # Find specific information
    CHECK = "check"  # Check facts or status
    LOOKUP = "lookup"  # Quick lookup
    
    # Simple Interactions
    GREETING = "greeting"  # Simple greetings
    CLARIFICATION = "clarification"  # Asking for clarification


class IntentDetector:
    """
    Detects user intent to determine what TaskPilot AI should DO.
    
    This is NOT about keywords - it's about understanding the USER'S GOAL.
    """
    
    @staticmethod
    def detect_intent(
        user_input: str, 
        has_files: bool = False,
        screen_context: str | None = None
    ) -> dict[str, Any]:
        """
        Detect what the user wants TaskPilot AI to accomplish.
        
        Returns:
            {
                "intent": TaskIntent,
                "confidence": float (0-1),
                "requires_web": bool,
                "requires_analysis": bool,
                "is_time_sensitive": bool,
                "complexity": str,
                "keywords": list[str],
                "entities": list[str]
            }
        """
        text = user_input.lower().strip()
        
        # Quick greeting check
        if IntentDetector._is_greeting(text):
            return {
                "intent": TaskIntent.GREETING,
                "confidence": 1.0,
                "requires_web": False,
                "requires_analysis": False,
                "is_time_sensitive": False,
                "complexity": "simple",
                "keywords": [],
                "entities": []
            }
        
        # File-based intents
        if has_files:
            return IntentDetector._detect_file_intent(text)
        
        # Detect primary intent
        intent, confidence = IntentDetector._classify_intent(text)
        
        # Determine if web search is needed
        requires_web = IntentDetector._needs_web_data(text, intent)
        
        # Check if time-sensitive (needs current data)
        is_time_sensitive = IntentDetector._is_time_sensitive(text)
        
        # Extract keywords and entities
        keywords = IntentDetector._extract_keywords(user_input)
        entities = IntentDetector._extract_entities(user_input)
        
        # Assess complexity
        complexity = IntentDetector._assess_complexity(text, intent, len(keywords))
        
        return {
            "intent": intent,
            "confidence": confidence,
            "requires_web": requires_web,
            "requires_analysis": True,  # Always analyze for quality
            "is_time_sensitive": is_time_sensitive,
            "complexity": complexity,
            "keywords": keywords,
            "entities": entities,
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "current_year": datetime.now().year
        }
    
    @staticmethod
    def _is_greeting(text: str) -> bool:
        """Check if message is a simple greeting."""
        greetings = {
            "hi", "hello", "hey", "good morning", "good afternoon",
            "good evening", "greetings", "howdy", "hi there", "hello there",
            "sup", "what's up", "wassup"
        }
        
        # Exact match or starts with greeting and is short
        if text in greetings:
            return True
        
        for greeting in ["hi ", "hey ", "hello ", "howdy "]:
            if text.startswith(greeting) and len(text) < 20:
                return True
        
        return False
    
    @staticmethod
    def _detect_file_intent(text: str) -> dict[str, Any]:
        """Detect intent when files are uploaded."""
        # Analyze file content
        if any(word in text for word in ["analyze", "analysis", "examine", "inspect"]):
            intent = TaskIntent.ANALYZE_FILE
        # Summarize file
        elif any(word in text for word in ["summarize", "summary", "overview", "tldr"]):
            intent = TaskIntent.SUMMARIZE
        # Extract data
        elif any(word in text for word in ["extract", "pull", "get data", "find in"]):
            intent = TaskIntent.EXTRACT_DATA
        # Compare files
        elif any(word in text for word in ["compare", "difference", "vs", "versus"]):
            intent = TaskIntent.COMPARE
        # Default to analysis for files
        else:
            intent = TaskIntent.ANALYZE_FILE
        
        return {
            "intent": intent,
            "confidence": 0.9,
            "requires_web": False,
            "requires_analysis": True,
            "is_time_sensitive": False,
            "complexity": "medium",
            "keywords": IntentDetector._extract_keywords(text),
            "entities": []
        }
    
    @staticmethod
    def _classify_intent(text: str) -> tuple[TaskIntent, float]:
        """Classify the primary intent with confidence score."""
        
        # Research intent - wants deep information
        research_patterns = [
            r"\b(research|investigate|explore|study|learn about|tell me about|what is|explain)\b",
            r"\b(how does|why does|when did|where is|who is)\b",
            r"\b(history of|overview of|background on)\b"
        ]
        for pattern in research_patterns:
            if re.search(pattern, text):
                return TaskIntent.RESEARCH, 0.85
        
        # Comparison intent
        compare_patterns = [
            r"\b(compare|comparison|vs|versus|difference|better|best|which)\b",
            r"\b(pros and cons|advantages|disadvantages)\b"
        ]
        for pattern in compare_patterns:
            if re.search(pattern, text):
                return TaskIntent.COMPARE, 0.9
        
        # Recommendation intent
        recommend_patterns = [
            r"\b(recommend|recommendation|suggest|should i|which should)\b",
            r"\b(best|top|good|better option)\b.*\b(for|to|under)\b"
        ]
        for pattern in recommend_patterns:
            if re.search(pattern, text):
                return TaskIntent.RECOMMEND, 0.85
        
        # Calculation intent
        calculate_patterns = [
            r"\b(calculate|compute|solve|math|how much|how many)\b",
            r"\d+\s*[\+\-\*\/\^]\s*\d+",  # Mathematical expressions
        ]
        for pattern in calculate_patterns:
            if re.search(pattern, text):
                return TaskIntent.CALCULATE, 0.95
        
        # Planning intent
        plan_patterns = [
            r"\b(plan|planning|schedule|organize|strategy|steps to)\b",
            r"\b(how to|how can i|guide me|help me)\b"
        ]
        for pattern in plan_patterns:
            if re.search(pattern, text):
                return TaskIntent.PLAN, 0.8
        
        # Find/Search intent
        find_patterns = [
            r"\b(find|search|look for|locate|where can i)\b",
            r"\b(list of|examples of|sources for)\b"
        ]
        for pattern in find_patterns:
            if re.search(pattern, text):
                return TaskIntent.FIND, 0.85
        
        # Evaluation intent
        evaluate_patterns = [
            r"\b(evaluate|assessment|analyze|review|critique)\b",
            r"\b(worth it|is it good|any good)\b"
        ]
        for pattern in evaluate_patterns:
            if re.search(pattern, text):
                return TaskIntent.EVALUATE, 0.8
        
        # Summarize intent
        if any(word in text for word in ["summarize", "summary", "brief", "tldr", "key points"]):
            return TaskIntent.SUMMARIZE, 0.9
        
        # Default to research for questions
        if "?" in text:
            return TaskIntent.RESEARCH, 0.6
        
        # Default: explanation
        return TaskIntent.EXPLAIN, 0.5
    
    @staticmethod
    def _needs_web_data(text: str, intent: TaskIntent) -> bool:
        """Determine if the query needs web data."""
        # Always need web for these intents
        web_required_intents = {
            TaskIntent.RESEARCH,
            TaskIntent.COMPARE,
            TaskIntent.RECOMMEND,
            TaskIntent.FIND,
            TaskIntent.CHECK
        }
        
        if intent in web_required_intents:
            return True
        
        # Check for current/recent/latest indicators
        current_indicators = [
            "current", "latest", "recent", "today", "now", "2025", "2026",
            "this year", "this month", "price", "cost", "available", "weather",
            "temperature", "time in", "current time", "local time", "clock"
        ]
        
        return any(word in text for word in current_indicators)
    
    @staticmethod
    def _is_time_sensitive(text: str) -> bool:
        """Check if query needs current/updated information."""
        time_sensitive_keywords = [
            "today", "now", "current", "latest", "recent", "this week",
            "this month", "this year", "2025", "2026", "updated",
            "new", "trending", "happening", "status", "price", "cost",
            "weather", "temperature", "time in", "current time", "local time", "clock"
        ]
        
        return any(keyword in text for keyword in time_sensitive_keywords)
    
    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract meaningful keywords for search."""
        # Remove common stop words
        stop_words = {
            "i", "me", "my", "myself", "we", "our", "you", "your", "he", "him",
            "his", "she", "her", "it", "its", "they", "them", "what", "which",
            "who", "when", "where", "why", "how", "a", "an", "the", "and", "but",
            "or", "because", "as", "until", "while", "of", "at", "by", "for",
            "with", "about", "against", "between", "into", "through", "during",
            "before", "after", "above", "below", "to", "from", "up", "down",
            "in", "out", "on", "off", "over", "under", "again", "further",
            "then", "once", "is", "am", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "can", "could",
            "should", "would", "may", "might", "tell", "me", "please"
        }
        
        # Extract words
        words = re.findall(r'\b[a-z]+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Keep unique keywords in order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords[:10]  # Top 10 keywords
    
    @staticmethod
    def _extract_entities(text: str) -> list[str]:
        """Extract named entities (capitalized words/phrases)."""
        # Find capitalized words (potential entities)
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        # Filter out common capitalizations
        common_caps = {"I", "The", "A", "An", "This", "That", "These", "Those"}
        entities = [e for e in entities if e not in common_caps]
        
        return list(dict.fromkeys(entities))[:5]  # Top 5 unique entities
    
    @staticmethod
    def _assess_complexity(text: str, intent: TaskIntent, keyword_count: int) -> str:
        """Assess task complexity."""
        complexity_score = 0
        
        # Length
        if len(text) > 100:
            complexity_score += 1
        if len(text) > 200:
            complexity_score += 1
        
        # Multiple questions or requirements
        if text.count('?') > 1 or text.count('and') > 3:
            complexity_score += 1
        
        # Intent-based complexity
        complex_intents = {
            TaskIntent.RESEARCH, TaskIntent.COMPARE, 
            TaskIntent.ANALYZE_FILE, TaskIntent.EVALUATE
        }
        if intent in complex_intents:
            complexity_score += 2
        
        # Many keywords = complex topic
        if keyword_count > 5:
            complexity_score += 1
        
        if complexity_score >= 4:
            return "high"
        elif complexity_score >= 2:
            return "medium"
        else:
            return "simple"
