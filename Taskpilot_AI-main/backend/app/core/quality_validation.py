"""
Quality Validation System for TaskPilot AI

Features:
- Output quality scoring
- Content validation
- Confidence calculation
- Quality metrics tracking
"""

import re
from typing import Any, Optional
from dataclasses import dataclass
from enum import Enum


class QualityLevel(Enum):
    """Quality levels for outputs."""
    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"            # 75-89%
    ACCEPTABLE = "acceptable"  # 60-74%
    POOR = "poor"            # 40-59%
    UNACCEPTABLE = "unacceptable"  # <40%


@dataclass
class QualityScore:
    """Quality score with breakdown."""
    overall_score: float  # 0-100
    completeness: float   # 0-100
    relevance: float      # 0-100
    clarity: float        # 0-100
    accuracy: float       # 0-100
    level: QualityLevel
    issues: list[str]
    confidence: float     # 0-1


class OutputValidator:
    """
    Validates agent outputs for quality.
    
    Checks:
    - Completeness
    - Relevance to query
    - Clarity and structure
    - Potential accuracy issues
    """
    
    def __init__(self):
        self.validation_history = []
    
    def validate(
        self,
        output: str,
        context: dict,
        agent_name: str
    ) -> QualityScore:
        """
        Validate agent output and return quality score.
        
        Args:
            output: The agent's output text
            context: Context including user query and other data
            agent_name: Name of the agent that generated output
        
        Returns:
            QualityScore with detailed breakdown
        """
        issues = []
        
        # Score individual dimensions
        completeness = self._score_completeness(output, context, issues)
        relevance = self._score_relevance(output, context, issues)
        clarity = self._score_clarity(output, issues)
        accuracy = self._score_accuracy(output, issues)
        
        # Calculate overall score (weighted average)
        overall = (
            completeness * 0.30 +
            relevance * 0.30 +
            clarity * 0.20 +
            accuracy * 0.20
        )
        
        # Determine quality level
        if overall >= 90:
            level = QualityLevel.EXCELLENT
        elif overall >= 75:
            level = QualityLevel.GOOD
        elif overall >= 60:
            level = QualityLevel.ACCEPTABLE
        elif overall >= 40:
            level = QualityLevel.POOR
        else:
            level = QualityLevel.UNACCEPTABLE
        
        # Calculate confidence (inverse of issues count, normalized)
        confidence = max(0.0, min(1.0, 1.0 - (len(issues) * 0.1)))
        
        score = QualityScore(
            overall_score=round(overall, 2),
            completeness=round(completeness, 2),
            relevance=round(relevance, 2),
            clarity=round(clarity, 2),
            accuracy=round(accuracy, 2),
            level=level,
            issues=issues,
            confidence=round(confidence, 2)
        )
        
        # Record in history
        self.validation_history.append({
            'agent': agent_name,
            'score': score,
            'output_length': len(output)
        })
        
        return score
    
    def _score_completeness(self, output: str, context: dict, issues: list) -> float:
        """Score output completeness (0-100)."""
        score = 100.0
        
        # Check minimum length
        if len(output) < 50:
            issues.append("Output too short (< 50 characters)")
            score -= 30
        elif len(output) < 100:
            score -= 10
        
        # Check if output is just error message
        error_indicators = ['error', 'failed', 'could not', 'unable to', 'sorry']
        if any(indicator in output.lower()[:100] for indicator in error_indicators):
            issues.append("Output appears to be error message")
            score -= 40
        
        # Check if output provides substantial content
        sentences = self._count_sentences(output)
        if sentences < 2:
            issues.append("Output lacks sufficient detail (< 2 sentences)")
            score -= 20
        
        return max(0, score)
    
    def _score_relevance(self, output: str, context: dict, issues: list) -> float:
        """Score output relevance to user query (0-100)."""
        score = 100.0
        
        user_input = context.get('user_input', '').lower()
        if not user_input:
            return score
        
        output_lower = output.lower()
        
        # Extract key terms from query
        query_terms = self._extract_key_terms(user_input)
        
        if query_terms:
            # Check how many query terms appear in output
            matches = sum(1 for term in query_terms if term in output_lower)
            match_rate = matches / len(query_terms)
            
            if match_rate < 0.3:
                issues.append("Low relevance to user query (< 30% term match)")
                score -= 40
            elif match_rate < 0.5:
                score -= 20
        
        # Check if output just repeats the query
        if user_input in output_lower and len(output) < len(user_input) * 3:
            issues.append("Output mostly repeats user query")
            score -= 30
        
        return max(0, score)
    
    def _score_clarity(self, output: str, issues: list) -> float:
        """Score output clarity and structure (0-100)."""
        score = 100.0
        
        # Check for proper sentence structure
        sentences = self._count_sentences(output)
        if sentences == 0:
            issues.append("No proper sentences detected")
            score -= 40
        
        # Check for excessive repetition
        words = output.lower().split()
        if len(words) > 20:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.5:
                issues.append("High word repetition (low uniqueness)")
                score -= 20
        
        # Check for formatting (bullets, numbers, structure)
        has_structure = any([
            '\n•' in output,
            '\n-' in output,
            '\n→' in output,
            '\n1.' in output,
            '**' in output,
        ])
        
        if len(output) > 300 and not has_structure:
            score -= 10  # Long text without structure
        
        # Check for excessive caps or special characters
        if len(output) > 0:
            caps_ratio = sum(1 for c in output if c.isupper()) / len(output)
            if caps_ratio > 0.3:
                issues.append("Excessive capitalization")
                score -= 10
        
        return max(0, score)
    
    def _score_accuracy(self, output: str, issues: list) -> float:
        """Score potential accuracy issues (0-100)."""
        score = 100.0
        
        output_lower = output.lower()
        
        # Check for confidence disclaimers (might indicate hallucination)
        uncertain_phrases = [
            'might be', 'could be', 'possibly', 'perhaps',
            'i think', 'i believe', 'probably', 'maybe'
        ]
        
        uncertainty_count = sum(1 for phrase in uncertain_phrases if phrase in output_lower)
        if uncertainty_count > 2:
            issues.append(f"Multiple uncertainty indicators ({uncertainty_count})")
            score -= 15
        
        # Check for identity leakage (model mentions)
        forbidden_terms = [
            'gemini', 'language model', 'ai model', 'llm',
            'openai', 'chatgpt', 'gpt-', 'claude'
        ]
        
        if any(term in output_lower for term in forbidden_terms):
            issues.append("Contains model/AI identity references")
            score -= 30
        
        # Check for meta-commentary
        meta_phrases = [
            'as an ai', 'as a language', 'i am programmed',
            'my training', 'i cannot access', 'i don\'t have access to'
        ]
        
        if any(phrase in output_lower for phrase in meta_phrases):
            issues.append("Contains meta-commentary about AI limitations")
            score -= 25
        
        # Check for placeholder text
        placeholders = ['lorem ipsum', '[insert', 'placeholder', 'xxx', 'todo']
        if any(placeholder in output_lower for placeholder in placeholders):
            issues.append("Contains placeholder text")
            score -= 40
        
        return max(0, score)
    
    def _count_sentences(self, text: str) -> int:
        """Count sentences in text."""
        # Simple sentence counting
        sentence_endings = re.findall(r'[.!?]+', text)
        return len(sentence_endings)
    
    def _extract_key_terms(self, query: str) -> list[str]:
        """Extract key terms from query."""
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
            'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was',
            'are', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'should', 'could',
            'can', 'may', 'might', 'must', 'what', 'when', 'where',
            'who', 'how', 'why', 'which', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her'
        }
        
        # Extract words
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter stop words and short words
        key_terms = [
            word for word in words
            if word not in stop_words and len(word) > 2
        ]
        
        return key_terms
    
    def get_validation_stats(self) -> dict:
        """Get validation statistics."""
        if not self.validation_history:
            return {'total_validations': 0}
        
        total = len(self.validation_history)
        
        # Average scores by agent
        by_agent = {}
        for record in self.validation_history:
            agent = record['agent']
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(record['score'].overall_score)
        
        agent_averages = {
            agent: sum(scores) / len(scores)
            for agent, scores in by_agent.items()
        }
        
        # Overall average
        all_scores = [r['score'].overall_score for r in self.validation_history]
        overall_avg = sum(all_scores) / len(all_scores)
        
        # Quality level distribution
        level_counts = {}
        for record in self.validation_history:
            level = record['score'].level.value
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return {
            'total_validations': total,
            'overall_average_score': round(overall_avg, 2),
            'by_agent': {
                agent: round(avg, 2)
                for agent, avg in agent_averages.items()
            },
            'quality_distribution': level_counts
        }


class ConfidenceCalculator:
    """
    Calculate confidence scores for agent outputs.
    
    Factors:
    - Quality score
    - Context completeness
    - Agent performance history
    """
    
    @staticmethod
    def calculate(
        quality_score: QualityScore,
        context_completeness: float,
        agent_reliability: float = 0.8
    ) -> float:
        """
        Calculate overall confidence score (0-1).
        
        Args:
            quality_score: Quality score from validator
            context_completeness: How complete the input context was (0-1)
            agent_reliability: Historical reliability of agent (0-1)
        
        Returns:
            Confidence score (0-1)
        """
        # Normalize quality score to 0-1
        quality_factor = quality_score.overall_score / 100.0
        
        # Combine factors (weighted)
        confidence = (
            quality_factor * 0.50 +
            context_completeness * 0.30 +
            agent_reliability * 0.20
        )
        
        # Apply penalty for issues
        issue_penalty = len(quality_score.issues) * 0.05
        confidence = max(0.0, confidence - issue_penalty)
        
        return round(confidence, 3)


# Global instance
_output_validator = None


def get_output_validator() -> OutputValidator:
    """Get the global output validator."""
    global _output_validator
    if _output_validator is None:
        _output_validator = OutputValidator()
    return _output_validator
