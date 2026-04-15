from __future__ import annotations

from typing import Any

from app.services.agents.base import AgentContext, AgentResultData, BaseAgent
from app.services.ai.base import LLMProvider


class PlannerAgent(BaseAgent):
    """
    Plans TASK EXECUTION using intelligent strategy.
    
    This agent creates ACTIONABLE EXECUTION PLANS, not just descriptions.
    Plans tell TaskPilot AI exactly HOW to accomplish the user's goal.
    """

    name = "planner"

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def run(self, context: AgentContext) -> AgentResultData:
        # Get task metadata from context
        intent = context.metadata.get("intent", "unknown")
        requirements = context.metadata.get("requirements", [])
        priority = context.metadata.get("priority", "normal")
        history = context.metadata.get("conversation_memory", [])
        interaction_intent = self._detect_interaction_intent(context.user_input, history)
        response_format = self._choose_response_format(intent, context.user_input)
        
        # === OPTIMIZATION: Skip heavy planning for factual questions ===
        is_factual = context.metadata.get("is_factual_question", False)
        response_priority = context.metadata.get("response_priority", "normal")
        
        if is_factual and response_priority == "DIRECT_ANSWER_FIRST":
            # Simple factual questions don't need complex planning
            answer_type = context.metadata.get("answer_type", "fact")
            steps = [
                f"Extract direct answer ({answer_type})",
                "Format with answer first, context second",
                "Deliver immediate response"
            ]
            context.plan = steps
            output = "Fast execution: " + "; ".join(steps)
            return AgentResultData(
                name=self.name,
                status="complete",
                output=output,
                details={
                    "steps": steps, 
                    "method": "fast-path-factual",
                    "priority": priority,
                    "interaction_intent": interaction_intent,
                    "response_format": response_format,
                },
            )
        
        # === STANDARD PATH FOR COMPLEX QUERIES ===
        
        # Use intent-based planning directly to avoid API quota issues
        # This provides immediate, reliable planning without external API calls
        steps = self._intent_based_planning(context, intent, requirements)
        
        # Optional: Try LLM enhancement only if steps seem generic
        if len(steps) <= 3:
            try:
                # Build EXECUTION-FOCUSED prompt for LLM
                prompt = self._build_execution_prompt(context, intent, requirements)
                llm_response = await self.llm.generate(prompt)
                
                if llm_response and len(llm_response.strip()) > 10:
                    # Parse LLM response into actionable steps
                    llm_steps = self._parse_execution_steps(llm_response)
                    if len(llm_steps) > len(steps):
                        steps = llm_steps
            except Exception as e:
                # LLM failed, but we already have intent-based steps
                print(f"LLM planning failed (using fallback): {e}")
        
        context.plan = steps
        output = "Execution Plan: " + "; ".join(steps)
        return AgentResultData(
            name=self.name,
            status="complete",
            output=output,
            details={
                "steps": steps, 
                "method": "intent-based",
                "priority": priority,
                "interaction_intent": interaction_intent,
                "response_format": response_format,
            },
        )

    def _detect_interaction_intent(self, query: str, history: list[dict[str, Any]]) -> str:
        """Detect whether this turn is a task, question, research, or follow-up."""
        q = query.lower().strip()

        if any(phrase in q for phrase in ["explain more", "more details", "compare with previous", "as above", "that one"]):
            return "follow_up"
        if history and len(history) > 0 and any(term in q for term in ["previous", "earlier", "last answer"]):
            return "follow_up"
        if any(term in q for term in ["steps", "build", "create", "implement", "do this", "execute"]):
            return "task"
        if any(term in q for term in ["research", "find", "investigate", "latest", "sources"]):
            return "research"
        if "?" in q or any(q.startswith(prefix) for prefix in ["what", "why", "how", "when", "where", "who"]):
            return "question"
        return "general"

    def _choose_response_format(self, intent: str, query: str) -> str:
        """Choose best response structure for downstream formatter/reporter."""
        q = query.lower()
        if intent in ["compare", "evaluate"] or "compare" in q:
            return "comparison_list"
        if intent in ["plan", "calculate"] or any(term in q for term in ["steps", "step by step"]):
            return "step_by_step"
        if intent in ["research", "explain", "summarize"]:
            return "structured_summary"
        return "concise_answer"

    def _build_execution_prompt(
        self, 
        context: AgentContext, 
        intent: str, 
        requirements: list
    ) -> str:
        """Build an EXECUTION-FOCUSED prompt for LLM."""
        prompt_parts = [
            "You are TaskPilot AI's execution planner.",
            "",
            "CRITICAL RULES:",
            "- Generate INTERNAL execution steps, NOT user responses",
            "- NEVER say 'I am Gemini' or mention being an AI model",
            "- Be specific and actionable",
            "- Focus on DOING the task, not just explaining it",
            "",
            f"TASK TYPE: {intent}",
            f"USER REQUEST: {context.user_input}",
        ]
        
        if requirements:
            prompt_parts.append(f"REQUIREMENTS: {', '.join(requirements)}")
        
        if context.analysis:
            # Include key analysis insights
            analysis_summary = context.analysis[:400]
            prompt_parts.append(f"ANALYSIS: {analysis_summary}")
        
        if context.fetched_context:
            # Show what data we have
            data_preview = context.fetched_context[:500]
            prompt_parts.append(f"AVAILABLE DATA: {data_preview}...")
        
        prompt_parts.extend([
            "",
            "Generate 3-5 EXECUTION STEPS that tell TaskPilot AI exactly what to DO.",
            "Format: One action step per line, starting with -",
            "Examples:",
            "- Analyze laptop options by comparing specifications and prices",
            "- Rank options by value considering user's $1000 budget",
            "- Recommend top choice with clear justification",
            "",
            "EXECUTION STEPS:",
        ])
        return "\n".join(prompt_parts)

    def _parse_execution_steps(self, response: str) -> list[str]:
        """Parse LLM response into actionable execution steps."""
        lines = response.strip().split("\n")
        steps = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and headers
            if not line or line.lower() in ["execution steps:", "steps:", "plan:"]:
                continue
            
            # Remove bullet points, numbers, etc.
            if line.startswith("-") or line.startswith("*"):
                line = line[1:].strip()
            elif line and line[0].isdigit() and "." in line[:3]:
                line = line.split(".", 1)[1].strip() if "." in line else line
            
            # Only include meaningful steps
            if line and len(line) > 10 and not line.startswith("CRITICAL"):
                steps.append(line[:200])  # Limit step length
        
        return steps[:6] if steps else self._default_execution_steps()

    def _parse_llm_response(self, response: str) -> list[str]:
        """Parse LLM response into a list of steps."""
        lines = response.strip().split("\n")
        steps = []
        for line in lines:
            line = line.strip()
            # Remove bullet points, numbers, etc.
            if line.startswith("-"):
                line = line[1:].strip()
            elif line and line[0].isdigit() and "." in line[:3]:
                line = line.split(".", 1)[1].strip() if "." in line else line
            
            if line and len(line) > 5:
                steps.append(line[:200])  # Limit step length
        
        return steps[:6] if steps else self._default_steps()

    def _intent_based_planning(
        self, 
        context: AgentContext, 
        intent: str, 
        requirements: list
    ) -> list[str]:
        """
        Generate SMART execution plans based on detected intent.
        This is the fallback when LLM is unavailable.
        """
        has_attachments = bool(context.attachments)
        has_web_data = "WEB RESEARCH" in (context.fetched_context or "")
        
        # INTENT-SPECIFIC EXECUTION PLANS
        
        if intent == "research":
            return [
                "Analyze gathered research data from multiple sources",
                "Identify key facts, trends, and authoritative information",
                "Synthesize findings into comprehensive overview",
                "Present insights with factual backing",
            ]
        
        elif intent == "compare":
            return [
                "Extract options and their key characteristics",
                "Build comparison matrix of features, benefits, drawbacks",
                "Evaluate each option against user criteria",
                "Recommend best choice with justification",
            ]
        
        elif intent == "recommend":
            return [
                "Analyze available options and user requirements",
                "Evaluate each option against criteria (price, features, quality)",
                "Rank options by best fit for user needs",
                "Provide clear recommendation with reasoning",
            ]
        
        elif intent == "plan":
            return [
                "Break down goal into sequential milestones",
                "Identify resources and requirements for each step",
                "Create timeline and prioritization strategy",
                "Deliver actionable implementation plan",
            ]
        
        elif intent == "analyze_file":
            return [
                "Extract and parse file contents systematically",
                "Identify patterns, insights, and key information",
                "Analyze data quality and relevance",
                "Generate actionable summary with findings",
            ]
        
        elif intent == "calculate":
            return [
                "Parse numerical requirements and constraints",
                "Perform calculations accurately",
                "Verify results and check reasonableness",
                "Present answer with clear explanation",
            ]
        
        elif intent == "explain":
            return [
                "Break complex topic into understandable components",
                "Explain each part clearly with examples",
                "Connect concepts to show relationships",
                "Summarize with practical takeaways",
            ]
        
        elif intent == "find":
            return [
                "Search through available data for requested information",
                "Filter results by relevance and quality",
                "Compile findings in organized format",
                "Present results with source context",
            ]
        
        elif intent == "evaluate":
            return [
                "Establish evaluation criteria",
                "Analyze subject against each criterion",
                "Identify strengths and weaknesses",
                "Provide balanced assessment with conclusion",
            ]
        
        elif intent == "summarize":
            return [
                "Extract main points and key information",
                "Remove redundancy and filler content",
                "Organize information logically",
                "Deliver concise summary of essentials",
            ]
        
        # FALLBACK: Generic but actionable steps
        else:
            if has_attachments:
                return [
                    "Process and analyze uploaded file content",
                    "Execute user's requested task on the data",
                    "Generate results with key insights",
                ]
            elif has_web_data:
                return [
                    "Analyze gathered information and context",
                    "Process data to fulfill user request",
                    "Deliver clear and actionable answer",
                ]
            else:
                return [
                    "Process user request and available context",
                    "Generate comprehensive response with relevant details",
                    "Deliver direct answer with supporting information",
                ]

    def _default_execution_steps(self) -> list[str]:
        """Default execution steps when no specific plan can be determined."""
        return [
            "Analyze user request and available information",
            "Process relevant data and context",
            "Generate comprehensive response addressing the query",
        ]
    
    # Legacy method for backwards compatibility
    def _rule_based_planning(self, context: AgentContext) -> list[str]:
        """DEPRECATED: Use _intent_based_planning instead."""
        return self._intent_based_planning(
            context, 
            "unknown", 
            []
        )
    
    def _default_steps(self) -> list[str]:
        """DEPRECATED: Use _default_execution_steps instead."""
        return self._default_execution_steps()
