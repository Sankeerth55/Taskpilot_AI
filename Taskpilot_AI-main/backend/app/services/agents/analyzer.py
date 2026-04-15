from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any

from app.core.logging_config import get_logger
from app.services.agents.base import AgentContext, AgentResultData, BaseAgent


class AnalyzerAgent(BaseAgent):
    """
    PRODUCTION-GRADE Analyzer Agent for TaskPilot AI.
    
    Performs INTELLIGENT, TASK-ORIENTED analysis:
    - Uses intent information from context
    - Extracts actionable requirements
    - Identifies what needs to be DONE (not just understood)
    - Calculates task priority and urgency
    - Determines data quality and completeness
    - Provides strategic insights for task execution
    """

    name = "analyzer"

    def __init__(self) -> None:
        self.agent_logger = get_logger("agent.analyzer")

    async def run(self, context: AgentContext) -> AgentResultData:
        start = time.perf_counter()
        base = context.fetched_context or context.user_input
        user_input = context.user_input

        deduped_base, duplicate_count = self._merge_duplicate_information(base)
        filtered_base, filtered_count = self._filter_low_quality_lines(deduped_base)
        effective_base = filtered_base or deduped_base or base

        # Preserve backward compatibility while improving context quality.
        if context.fetched_context:
            context.fetched_context = effective_base

        # Get intent information from context metadata
        intent = context.metadata.get("intent", "unknown")
        complexity = context.metadata.get("complexity", "simple")
        is_time_sensitive = context.metadata.get("is_time_sensitive", False)

        # === CRITICAL: DETECT FACTUAL QUESTIONS FIRST ===
        factual_analysis = self._detect_factual_question(user_input, effective_base)
        
        self.agent_logger.debug(
            "analyzer_factual_detection",
            query=user_input,
            is_factual=factual_analysis["is_factual"],
            answer_type=factual_analysis["answer_type"],
            primary_entity=factual_analysis["primary_entity"],
        )
        
        # Store factual question metadata for Reporter
        context.metadata["is_factual_question"] = factual_analysis["is_factual"]
        context.metadata["answer_type"] = factual_analysis["answer_type"]
        context.metadata["primary_entity"] = factual_analysis["primary_entity"]
        context.metadata["expected_answer_format"] = factual_analysis["expected_format"]
        
        # If this is a factual question, mark for direct answer
        if factual_analysis["is_factual"]:
            context.metadata["response_priority"] = "DIRECT_ANSWER_FIRST"
            context.metadata["direct_answer_hint"] = factual_analysis["answer_hint"]
            self.agent_logger.debug(
                "analyzer_direct_answer_priority",
                hint=factual_analysis["answer_hint"],
            )

        # Perform TASK-ORIENTED analysis
        analysis_parts: list[str] = []

        # 1. Task Intent Summary
        if factual_analysis["is_factual"]:
            analysis_parts.append(f"Task: direct_factual_answer ({factual_analysis['answer_type']})")
        else:
            analysis_parts.append(f"Task: {intent}")

        # 2. Extract ACTIONABLE requirements
        requirements = self._extract_requirements(user_input, intent)
        if requirements:
            analysis_parts.append(f"Requirements: {', '.join(requirements)}")

        # 3. Data Quality Assessment
        data_quality = self._assess_data_quality(effective_base, context.attachments)
        analysis_parts.append(f"Data Quality: {data_quality}")

        relevance_score = self._calculate_relevance(user_input, effective_base)
        source_reliability = self._calculate_source_reliability_score(effective_base)
        analysis_parts.append(f"Relevance Score: {relevance_score:.2f}")
        analysis_parts.append(f"Source Reliability: {source_reliability:.2f}")

        # 4. Extract key entities and topics
        entities = self._extract_entities(effective_base)
        if entities:
            analysis_parts.append(f"Key entities: {', '.join(entities[:5])}")

        # 5. Task Priority (urgency + importance)
        priority = self._calculate_priority(user_input, is_time_sensitive, complexity)
        analysis_parts.append(f"Priority: {priority}")

        # 6. Completeness Check - Do we have enough info?
        completeness = self._check_completeness(user_input, effective_base, context.attachments)
        analysis_parts.append(f"Info Completeness: {completeness}%")

        # 7. Extract numerical/quantitative context
        numbers = self._extract_quantitative_context(user_input)
        if numbers:
            analysis_parts.append(f"Quantitative: {numbers}")

        # 8. Identify potential challenges or considerations
        considerations = self._identify_considerations(user_input, intent)
        if considerations:
            analysis_parts.append(f"Considerations: {considerations}")

        output = " | ".join(analysis_parts)
        context.analysis = output
        
        # Store detailed metadata for downstream agents
        context.metadata["requirements"] = requirements
        context.metadata["entities"] = entities
        context.metadata["priority"] = priority
        context.metadata["completeness_score"] = completeness
        context.metadata["data_quality"] = data_quality
        context.metadata["relevance_score"] = round(relevance_score, 4)
        context.metadata["source_reliability_score"] = round(source_reliability, 4)
        context.metadata["duplicate_lines_removed"] = duplicate_count
        context.metadata["low_quality_lines_filtered"] = filtered_count
        context.metadata["analysis_duration_ms"] = round((time.perf_counter() - start) * 1000, 2)

        self.agent_logger.info(
            "analyzer_completed",
            duration_ms=context.metadata["analysis_duration_ms"],
            relevance=context.metadata["relevance_score"],
            reliability=context.metadata["source_reliability_score"],
            duplicates_removed=duplicate_count,
            filtered_lines=filtered_count,
        )

        return AgentResultData(name=self.name, status="complete", output=output)
    
    def _detect_factual_question(self, query: str, context: str) -> dict:
        """
        CRITICAL: Detect if this is a factual question needing a direct answer.
        
        Returns dict with:
            - is_factual: bool
            - answer_type: str (person, place, position, date, fact, etc.)
            - primary_entity: str (the main subject)
            - expected_format: str (name, location, year, etc.)
            - answer_hint: str (guidance for Reporter on what to extract)
        """
        query_lower = query.lower()
        
        result = {
            "is_factual": False,
            "answer_type": "unknown",
            "primary_entity": "",
            "expected_format": "text",
            "answer_hint": ""
        }

        # Treat broad/comparative prompts as non-factual so they stay in normal analysis/report mode.
        broad_non_factual_terms = (
            "best", "compare", "comparison", "recommend", "top", "pros and cons", "versus", " vs "
        )
        hard_factual_markers = (
            "who is", "who's", "founder", "ceo", "president", "prime minister", "chief minister", " cm ", " pm ",
            "where is", "which country", "which city", "capital of", "population", "when "
        )
        if any(term in query_lower for term in broad_non_factual_terms) and not any(marker in query_lower for marker in hard_factual_markers):
            return result

        # Definitions/meaning/summary should be handled as general Gemini responses.
        definition_terms = ("definition", "meaning", "summary", "summarize", "explain")
        if any(term in query_lower for term in definition_terms):
            return result
        
        # === DETECT FACTUAL QUESTION PATTERNS ===
        
        # 0. HOTEL/PRICE COMPARISON questions - Highest priority check
        if any(keyword in query_lower for keyword in ["hotel", "resort", "accommodation"]):
            if any(price_word in query_lower for price_word in ["price", "cheap", "cheapest", "cost", "compare", "affordable"]):
                result["is_factual"] = True
                result["answer_type"] = "price_comparison"
                result["expected_format"] = "price_list_with_comparison"
                result["primary_entity"] = "hotel_prices"
                result["answer_hint"] = "Extract 3-4 hotels with prices, identify cheapest option, provide booking links"
                return result  # Early return for hotel comparisons
        
        # 1. WHO / entity questions (person/position/role) - Enhanced to detect all variations
        if (
            query_lower.startswith("who is")
            or query_lower.startswith("who's")
            or query_lower.startswith("who founded")
            or query_lower.startswith("who created")
            or query_lower.startswith("who leads")
            or query_lower.startswith("who heads")
            or "who is" in query_lower
            or "who founded" in query_lower
            or "who created" in query_lower
        ):
            result["is_factual"] = True
            result["answer_type"] = "person"
            result["expected_format"] = "person_name"
            
            # Extract entity (President of India, CEO of Google, etc.)
            if "president" in query_lower:
                result["primary_entity"] = "president"
                if "india" in query_lower:
                    result["answer_hint"] = "Extract person's name who is President of India - NAME ONLY in first line"
                else:
                    result["answer_hint"] = "Extract president's name - NAME ONLY in first line"
            elif "prime minister" in query_lower or " pm " in query_lower or query_lower.endswith(" pm") or "pm in" in query_lower or "pm of" in query_lower:
                result["primary_entity"] = "prime_minister"
                result["answer_hint"] = "Extract PM's full name - NAME ONLY in first line, no title"
            elif "ceo" in query_lower:
                result["primary_entity"] = "ceo"
                result["answer_hint"] = "Extract CEO name - NAME ONLY in first line"
            elif "chief minister" in query_lower or re.search(r"\bcm\b", query_lower):
                result["primary_entity"] = "chief_minister"
                result["answer_hint"] = "Extract Chief Minister's full name - NAME ONLY in first line"
            elif "founder" in query_lower or "founded" in query_lower:
                result["primary_entity"] = "founder"
                result["answer_hint"] = "Extract founder's name - NAME ONLY in first line"
            elif "leader" in query_lower:
                result["primary_entity"] = "leader"
                result["answer_hint"] = "Extract leader's name - NAME ONLY in first line"
            else:
                # Generic person question
                words = query_lower.replace("who is ", "").replace("who's ", "").split()
                if words:
                    result["primary_entity"] = words[0]
                    result["answer_hint"] = f"Extract information about {words[0]}"
        
        # 2. WHEN questions (date/year/time)
        elif query_lower.startswith("when "):
            result["is_factual"] = True
            result["answer_type"] = "date"
            result["expected_format"] = "date_or_year"
            
            if "won" in query_lower or "win" in query_lower:
                result["primary_entity"] = "event_date"
                result["answer_hint"] = "Extract year/date of the event"
            elif "start" in query_lower or "begin" in query_lower:
                result["primary_entity"] = "start_date"
                result["answer_hint"] = "Extract start date"
            else:
                result["primary_entity"] = "date"
                result["answer_hint"] = "Extract relevant date/year"
        
        # 3. WHERE questions (location/place)
        elif query_lower.startswith("where is") or query_lower.startswith("where ") or query_lower.startswith("which city") or query_lower.startswith("which country"):
            result["is_factual"] = True
            result["answer_type"] = "place"
            result["expected_format"] = "location"
            result["primary_entity"] = "location"
            result["answer_hint"] = "Extract location/place name"
        
        # 4. WHAT IS questions (definition/fact)
        elif query_lower.startswith("what is") or query_lower.startswith("what's") or query_lower.startswith("what are") or query_lower.startswith("what does"):
            # If asking for capital/population, treat as factual; otherwise keep as general.
            if any(term in query_lower for term in ("capital", "population")):
                result["is_factual"] = True
                result["answer_type"] = "place" if "capital" in query_lower else "number"
                result["expected_format"] = "definition"
                result["primary_entity"] = "capital" if "capital" in query_lower else "population"
                result["answer_hint"] = "Extract capital city name" if "capital" in query_lower else "Extract population figure"
            else:
                return result
        
        # 5. Position/title questions (without "who")
        elif any(term in query_lower for term in ["president of", "pm of", "ceo of", "founder of", "leader of"]):
            result["is_factual"] = True
            result["answer_type"] = "person"
            result["expected_format"] = "person_name"
            
            if "president" in query_lower:
                result["primary_entity"] = "president"
                if "india" in query_lower:
                    result["answer_hint"] = "Extract President of India's name - format: 'President of India: [Name]'"
            elif "prime minister" in query_lower or "pm" in query_lower:
                result["primary_entity"] = "prime_minister"
                result["answer_hint"] = "Extract PM's name"
        
        # 6. Current/Present/Latest status questions - should be caught EARLY
        elif any(term in query_lower for term in ["current", "present", "latest"]):
            result["is_factual"] = True
            if "president" in query_lower:
                result["answer_type"] = "person"
                result["expected_format"] = "person_name"
                result["primary_entity"] = "president"
                result["answer_hint"] = "Extract current President's name - NAME ONLY in first line"
            elif "prime minister" in query_lower or " pm " in query_lower or query_lower.endswith(" pm") or "pm in" in query_lower or "pm of" in query_lower:
                result["answer_type"] = "person"
                result["expected_format"] = "person_name"
                result["primary_entity"] = "prime_minister"
                result["answer_hint"] = "Extract current PM's full name - NAME ONLY in first line, no title"
            else:
                result["answer_type"] = "fact"
                result["expected_format"] = "current_info"
                result["answer_hint"] = "Extract current/latest information"
        
        # 7. "Which year" / "What year" questions
        elif "which year" in query_lower or "what year" in query_lower:
            result["is_factual"] = True
            result["answer_type"] = "year"
            result["expected_format"] = "year"
            result["primary_entity"] = "year"
            result["answer_hint"] = "Extract specific year"
        
        # 8. Price/cost questions (for hotel, travel queries)
        elif any(term in query_lower for term in ["cheapest", "price", "cost", "how much"]):
            result["is_factual"] = True
            result["answer_type"] = "price"
            result["expected_format"] = "price_list"
            result["primary_entity"] = "pricing"
            result["answer_hint"] = "Extract prices - show price range in FIRST LINE"
        
        # === EXTRACT PRIMARY ENTITY FROM CONTEXT ===
        if result["is_factual"] and context:
            # Try to find the most relevant name/entity from context
            if result["answer_type"] == "person":
                # Look for proper names (capitalized words in sequence)
                names = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', context)
                if names:
                    # Filter out common non-name phrases
                    filtered_names = [n for n in names if n not in ["Web Research", "Reference Data", "Recent Info"]]
                    if filtered_names:
                        result["primary_entity"] = filtered_names[0]
        
        return result
    
    def _extract_requirements(self, text: str, intent: str) -> list[str]:
        """Extract what the user NEEDS from this task."""
        requirements = []
        text_lower = text.lower()
        
        # Intent-based requirements
        if intent == "compare":
            if "best" in text_lower or "recommend" in text_lower:
                requirements.append("find best option")
            requirements.append("compare alternatives")
            if any(word in text_lower for word in ["price", "cost", "$"]):
                requirements.append("consider pricing")
        
        elif intent == "research":
            requirements.append("gather comprehensive information")
            if "current" in text_lower or "latest" in text_lower:
                requirements.append("provide current data")
        
        elif intent == "recommend":
            requirements.append("provide specific recommendation")
            if "why" in text_lower:
                requirements.append("explain reasoning")
        
        elif intent == "plan":
            requirements.append("create actionable plan")
            requirements.append("provide step-by-step guidance")
        
        elif intent in ["analyze_file", "extract_data"]:
            requirements.append("process file content")
            requirements.append("extract key information")
        
        # Universal requirements
        if "example" in text_lower:
            requirements.append("provide examples")
        if "how" in text_lower and "work" in text_lower:
            requirements.append("explain mechanism")
        if "?" in text:
            requirements.append("answer question directly")
        
        return requirements[:4]  # Top 4 requirements
    
    def _assess_data_quality(self, context: str, attachments: list) -> str:
        """Assess whether we have good data to work with."""
        score = 0
        
        # Length of context (comprehensive is better)
        if len(context) > 2000:
            score += 3  # Very comprehensive
        elif len(context) > 500:
            score += 2
        elif len(context) > 200:
            score += 1
        
        # Has structured data
        if attachments:
            score += 2
        
        # Has diverse sources (NEW: award more points for comprehensive search)
        if "WEB RESEARCH" in context:
            score += 1
        if "REFERENCE DATA" in context:
            score += 1
        if "RECENT INFO" in context:
            score += 1
        if "RELATED INSIGHTS" in context:
            score += 2  # NEW: Related topics provide comprehensive context
        
        # Check for URLs (indicates real sources)
        url_count = context.count("http://") + context.count("https://")
        if url_count >= 5:
            score += 2
        elif url_count >= 2:
            score += 1
        
        if score >= 7:
            return "world-class"  # NEW: Highest tier for comprehensive multi-source data
        elif score >= 5:
            return "excellent"
        elif score >= 3:
            return "good"
        elif score >= 1:
            return "moderate"
        else:
            return "limited"
    
    def _calculate_priority(self, text: str, is_time_sensitive: bool, complexity: str) -> str:
        """Calculate task priority (how urgent/important this is)."""
        score = 0
        
        # Time sensitivity adds urgency
        if is_time_sensitive:
            score += 2
        
        # Complexity adds importance
        if complexity == "high":
            score += 2
        elif complexity == "medium":
            score += 1
        
        # Urgency indicators
        urgent_words = ["urgent", "asap", "quickly", "now", "immediate", "critical"]
        if any(word in text.lower() for word in urgent_words):
            score += 2
        
        # Important indicators
        important_words = ["important", "need", "must", "required", "essential"]
        if any(word in text.lower() for word in important_words):
            score += 1
        
        if score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        else:
            return "normal"
    
    def _check_completeness(self, query: str, context: str, attachments: list) -> int:
        """Check if we have enough information to complete the task (0-100%)."""
        completeness = 40  # Base completeness
        
        # Query clarity
        if len(query) > 20:
            completeness += 10
        if "?" in query or any(word in query.lower() for word in ["what", "how", "why", "when"]):
            completeness += 5
        
        # Data availability (comprehensive data = higher completeness)
        if len(context) > 2000:
            completeness += 30  # Very comprehensive
        elif len(context) > 500:
            completeness += 20
        elif len(context) > 100:
            completeness += 10
        
        # File attachments provide concrete data
        if attachments:
            completeness += 15
        
        # Multiple data sources (NEW: award more for comprehensive search)
        sources = 0
        if "WEB RESEARCH" in context:
            sources += 1
        if "REFERENCE DATA" in context:
            sources += 1
        if "RECENT INFO" in context:
            sources += 1
        if "RELATED INSIGHTS" in context:
            sources += 1  # NEW: Related topics = more complete
        
        # Award bonus for having 3+ sources (comprehensive analysis)
        if sources >= 3:
            completeness += 10
        completeness += (sources * 3)
        
        return min(completeness, 100)
    
    def _identify_considerations(self, text: str, intent: str) -> str:
        """Identify important considerations for task execution."""
        considerations = []
        text_lower = text.lower()
        
        # Budget considerations
        if any(word in text_lower for word in ["cheap", "budget", "affordable", "under"]):
            considerations.append("budget-conscious")
        elif any(word in text_lower for word in ["premium", "best", "high-end"]):
            considerations.append("quality-focused")
        
        # Time considerations
        if any(word in text_lower for word in ["quick", "fast", "immediate"]):
            considerations.append("time-sensitive")
        
        # Accuracy requirements
        if any(word in text_lower for word in ["accurate", "precise", "exact", "verified"]):
            considerations.append("accuracy-critical")
        
        # Completeness requirements
        if any(word in text_lower for word in ["comprehensive", "detailed", "thorough", "complete"]):
            considerations.append("needs-depth")
        
        return ", ".join(considerations[:3]) if considerations else "standard"
    
    def _extract_quantitative_context(self, text: str) -> str:
        """Extract numbers, ranges, and quantitative requirements."""
        # Find numbers and ranges
        numbers = re.findall(r'\$?\d+(?:,\d{3})*(?:\.\d+)?', text)
        
        # Find ranges (e.g., "under $1000", "between 5-10")
        ranges = re.findall(r'(?:under|below|above|over|between)\s+\$?\d+', text, re.IGNORECASE)
        
        if ranges:
            return f"range: {', '.join(ranges[:2])}"
        elif numbers:
            return f"{len(numbers)} numeric value(s)"
        return ""

    def _extract_entities(self, text: str) -> list[str]:
        """Extract capitalized words and potential named entities."""
        words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        # Filter out common English words that are capitalized
        common_words = {"The", "A", "An", "This", "That", "These", "Those"}
        entities = [w for w in words if w not in common_words]
        # Return unique entities
        return list(dict.fromkeys(entities))[:10]

    def _merge_duplicate_information(self, context: str) -> tuple[str, int]:
        """Remove repeated lines while preserving order and useful links."""
        if not context:
            return context, 0

        seen: set[str] = set()
        unique_lines: list[str] = []
        duplicates_removed = 0

        for line in context.splitlines():
            normalized = re.sub(r"\s+", " ", line.strip().lower())
            if not normalized:
                continue
            if normalized in seen:
                duplicates_removed += 1
                continue
            seen.add(normalized)
            unique_lines.append(line)

        return "\n".join(unique_lines), duplicates_removed

    def _filter_low_quality_lines(self, context: str) -> tuple[str, int]:
        """Filter noisy snippets while retaining source lines and links."""
        if not context:
            return context, 0

        filtered: list[str] = []
        removed = 0
        keep_markers = ("🔍", "📚", "📰", "🧐", "⏰", "📎", "🔗", "http://", "https://")

        for line in context.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(keep_markers):
                filtered.append(line)
                continue

            alpha_chars = sum(1 for ch in stripped if ch.isalpha())
            if alpha_chars < 8 and len(stripped) < 18:
                removed += 1
                continue

            # Drop common low-value boilerplate fragments.
            if stripped.lower() in {"result", "read more", "click here"}:
                removed += 1
                continue

            filtered.append(line)

        return "\n".join(filtered), removed

    def _calculate_source_reliability_score(self, context: str) -> float:
        """Estimate source reliability from available source sections and links."""
        section_scores: list[float] = []

        if "REFERENCE DATA" in context:
            section_scores.append(0.9)
        if "WEB RESEARCH" in context:
            section_scores.append(0.7)
        if "RECENT INFO" in context:
            section_scores.append(0.75)
        if "RELATED INSIGHTS" in context:
            section_scores.append(0.65)

        if not section_scores:
            return 0.55

        reliability = sum(section_scores) / len(section_scores)
        link_count = context.count("http://") + context.count("https://")
        if link_count >= 3:
            reliability += 0.05
        elif link_count == 0:
            reliability -= 0.08

        return max(0.1, min(1.0, reliability))

    def _calculate_relevance(self, query: str, context: str) -> float:
        """Calculate relevance score between query and fetched context."""
        query_words = set(query.lower().split())
        context_words = set(context.lower().split())
        if not query_words:
            return 0.0
        intersection = query_words & context_words
        return len(intersection) / len(query_words)

    def _identify_question_type(self, text: str) -> str:
        """Identify the type of question being asked."""
        text_lower = text.lower()
        if any(word in text_lower for word in ["what", "which", "who"]):
            return "informational"
        if any(word in text_lower for word in ["how", "explain", "describe"]):
            return "instructional"
        if any(word in text_lower for word in ["why", "reason"]):
            return "explanatory"
        if "?" in text:
            return "question"
        return "statement"

    def _extract_actions(self, text: str) -> list[str]:
        """Extract action verbs from text."""
        action_verbs = [
            "create", "make", "build", "write", "send", "find", "search",
            "calculate", "analyze", "compare", "list", "show", "explain",
            "describe", "summarize", "help", "tell", "give", "provide"
        ]
        text_lower = text.lower()
        found_actions = [verb for verb in action_verbs if verb in text_lower]
        return list(dict.fromkeys(found_actions))[:3]  # Return up to 3 unique actions
