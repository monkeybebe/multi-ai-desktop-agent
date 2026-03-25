"""Base agent interface for all AI agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentStatus(str, Enum):
    """Status of an AI agent."""

    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class AgentResponse:
    """Response from an AI agent."""

    agent_name: str
    answer: str
    reasoning: str
    confidence: float  # 0.0 to 1.0
    raw_response: str = ""
    processing_time: float = 0.0
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "answer": self.answer,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "processing_time": self.processing_time,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    """Abstract base class for all AI agents."""

    def __init__(self, name: str, api_key: str = "", model: str = ""):
        self.name = name
        self.api_key = api_key
        self.model = model
        self.status = AgentStatus.IDLE
        self._enabled = bool(api_key)

    @property
    def is_enabled(self) -> bool:
        return self._enabled and bool(self.api_key)

    @property
    def is_available(self) -> bool:
        return self.is_enabled and self.status != AgentStatus.PROCESSING

    def enable(self) -> None:
        if self.api_key:
            self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    async def query(
        self,
        instruction: str,
        screen_text: str = "",
        screen_image_b64: str = "",
        context: str = "",
    ) -> AgentResponse:
        """Query the agent with instruction and optional screen data."""
        if not self.is_enabled:
            return AgentResponse(
                agent_name=self.name,
                answer="",
                reasoning="",
                confidence=0.0,
                error="Agent is disabled or API key not configured",
            )

        self.status = AgentStatus.PROCESSING
        start_time = time.time()

        try:
            response = await self._call_api(
                instruction=instruction,
                screen_text=screen_text,
                screen_image_b64=screen_image_b64,
                context=context,
            )
            response.processing_time = time.time() - start_time
            self.status = AgentStatus.COMPLETED
            return response
        except Exception as e:
            self.status = AgentStatus.ERROR
            return AgentResponse(
                agent_name=self.name,
                answer="",
                reasoning="",
                confidence=0.0,
                processing_time=time.time() - start_time,
                error=str(e),
            )

    @abstractmethod
    async def _call_api(
        self,
        instruction: str,
        screen_text: str = "",
        screen_image_b64: str = "",
        context: str = "",
    ) -> AgentResponse:
        """Implement the actual API call. Subclasses must override this."""
        ...

    def _build_system_prompt(self) -> str:
        return (
            "You are a helpful AI assistant that is part of the WA/D (Wisdom Assistor/Distributor) "
            "multi-agent system. You analyze screen content and user instructions to provide "
            "accurate answers and actionable guidance.\n\n"
            "When responding, provide:\n"
            "1. Your answer clearly stated\n"
            "2. Step-by-step reasoning for how you arrived at your answer\n"
            "3. A confidence level from 0.0 to 1.0\n\n"
            "Format your response as:\n"
            "ANSWER: <your answer>\n"
            "REASONING: <step-by-step reasoning>\n"
            "CONFIDENCE: <0.0-1.0>"
        )

    def _build_user_prompt(
        self,
        instruction: str,
        screen_text: str = "",
        context: str = "",
    ) -> str:
        parts = []
        if screen_text:
            parts.append(f"Current screen content:\n```\n{screen_text}\n```\n")
        if context:
            parts.append(f"Additional context:\n{context}\n")
        parts.append(f"User instruction: {instruction}")
        return "\n".join(parts)

    @staticmethod
    def _parse_response(agent_name: str, raw_text: str) -> AgentResponse:
        """Parse a structured agent response from raw text."""
        answer = ""
        reasoning = ""
        confidence = 0.5

        lines = raw_text.strip().split("\n")
        current_section = None

        for line in lines:
            line_upper = line.strip().upper()
            if line_upper.startswith("ANSWER:"):
                current_section = "answer"
                answer = line.split(":", 1)[1].strip()
            elif line_upper.startswith("REASONING:"):
                current_section = "reasoning"
                reasoning = line.split(":", 1)[1].strip()
            elif line_upper.startswith("CONFIDENCE:"):
                current_section = "confidence"
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    confidence = 0.5
            elif current_section == "answer":
                answer += "\n" + line
            elif current_section == "reasoning":
                reasoning += "\n" + line

        # If structured parsing failed, treat entire response as the answer
        if not answer and not reasoning:
            answer = raw_text.strip()
            reasoning = "Direct response without structured format."
            confidence = 0.5

        return AgentResponse(
            agent_name=agent_name,
            answer=answer.strip(),
            reasoning=reasoning.strip(),
            confidence=confidence,
            raw_response=raw_text,
        )
