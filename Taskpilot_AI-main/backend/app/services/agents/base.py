from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import time


@dataclass
class AgentContext:
    user_input: str
    screen_context: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)  # Processed attachments
    fetched_context: str | None = None
    analysis: str | None = None
    plan: list[str] = field(default_factory=list)
    report: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Performance tracking
    start_time: float = field(default_factory=time.time)
    agent_timings: dict[str, float] = field(default_factory=dict)
    
    def record_agent_time(self, agent_name: str, duration: float):
        """Record execution time for an agent."""
        self.agent_timings[agent_name] = duration
    
    def get_total_time(self) -> float:
        """Get total execution time."""
        return time.time() - self.start_time


@dataclass
class AgentResultData:
    name: str
    status: str
    output: str
    details: dict[str, Any] = field(default_factory=dict)
    
    # Quality metrics
    quality_score: Optional[float] = None
    confidence: Optional[float] = None
    execution_time: Optional[float] = None
    cached: bool = False


class BaseAgent(ABC):
    name: str

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResultData:
        raise NotImplementedError
    
    def _create_result(
        self,
        status: str,
        output: str,
        **details
    ) -> AgentResultData:
        """Helper to create AgentResultData with consistent structure."""
        return AgentResultData(
            name=self.name,
            status=status,
            output=output,
            details=details
        )
