"""Agent Manager - orchestrates all AI agents."""

from __future__ import annotations

import asyncio
from typing import Optional

from app.agents.anthropic_agent import AnthropicAgent
from app.agents.base import AgentResponse, BaseAgent
from app.agents.copilot_agent import CopilotAgent
from app.agents.gemini_agent import GeminiAgent
from app.agents.openai_agent import OpenAIAgent
from app.config import settings


class AgentManager:
    """Manages all AI agents and coordinates queries."""

    def __init__(self) -> None:
        self.agents: dict[str, BaseAgent] = {}
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Initialize all configured agents."""
        self.agents["openai"] = OpenAIAgent(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        self.agents["anthropic"] = AnthropicAgent(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
        self.agents["gemini"] = GeminiAgent(
            api_key=settings.google_api_key,
            model=settings.gemini_model,
        )
        self.agents["copilot"] = CopilotAgent(
            api_key=settings.microsoft_api_key,
        )

    def get_enabled_agents(self) -> list[BaseAgent]:
        """Return list of enabled agents."""
        return [a for a in self.agents.values() if a.is_enabled]

    def get_agent_statuses(self) -> dict[str, dict]:
        """Return status of all agents."""
        return {
            key: {
                "name": agent.name,
                "enabled": agent.is_enabled,
                "status": agent.status.value,
                "model": agent.model,
            }
            for key, agent in self.agents.items()
        }

    def update_api_key(self, agent_key: str, api_key: str) -> bool:
        """Update an agent's API key at runtime."""
        agent = self.agents.get(agent_key)
        if agent is None:
            return False
        agent.api_key = api_key
        if api_key:
            agent.enable()
        else:
            agent.disable()
        # Reset client so it's recreated with the new key
        agent.reset_client()
        return True

    async def query_all(
        self,
        instruction: str,
        screen_text: str = "",
        screen_image_b64: str = "",
        context: str = "",
        agent_keys: Optional[list[str]] = None,
    ) -> list[AgentResponse]:
        """Query all enabled agents concurrently.

        Args:
            instruction: The user's instruction/question
            screen_text: OCR-extracted text from screen
            screen_image_b64: Base64-encoded screenshot
            context: Additional context from memory/history
            agent_keys: Optional list of specific agents to query

        Returns:
            List of AgentResponse objects from all queried agents
        """
        if agent_keys:
            agents_to_query = [
                self.agents[k] for k in agent_keys
                if k in self.agents and self.agents[k].is_enabled
            ]
        else:
            agents_to_query = self.get_enabled_agents()

        if not agents_to_query:
            return [
                AgentResponse(
                    agent_name="System",
                    answer="",
                    reasoning="",
                    confidence=0.0,
                    error="No AI agents are configured. Please add API keys in Settings.",
                )
            ]

        tasks = [
            agent.query(
                instruction=instruction,
                screen_text=screen_text,
                screen_image_b64=screen_image_b64,
                context=context,
            )
            for agent in agents_to_query
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[AgentResponse] = []
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                results.append(
                    AgentResponse(
                        agent_name=agents_to_query[i].name,
                        answer="",
                        reasoning="",
                        confidence=0.0,
                        error=str(resp),
                    )
                )
            else:
                results.append(resp)

        return results

    async def query_single(
        self,
        agent_key: str,
        instruction: str,
        screen_text: str = "",
        screen_image_b64: str = "",
        context: str = "",
    ) -> AgentResponse:
        """Query a single specific agent."""
        agent = self.agents.get(agent_key)
        if agent is None:
            return AgentResponse(
                agent_name=agent_key,
                answer="",
                reasoning="",
                confidence=0.0,
                error=f"Agent '{agent_key}' not found",
            )

        return await agent.query(
            instruction=instruction,
            screen_text=screen_text,
            screen_image_b64=screen_image_b64,
            context=context,
        )
