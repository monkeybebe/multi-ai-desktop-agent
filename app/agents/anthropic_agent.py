"""Anthropic (Claude) agent implementation."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from app.agents.base import AgentResponse, BaseAgent


class AnthropicAgent(BaseAgent):
    """Agent powered by Anthropic's Claude models."""

    def __init__(self, api_key: str = "", model: str = "claude-sonnet-4-20250514"):
        super().__init__(name="Anthropic Claude", api_key=api_key, model=model)
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def _call_api(
        self,
        instruction: str,
        screen_text: str = "",
        screen_image_b64: str = "",
        context: str = "",
    ) -> AgentResponse:
        client = self._get_client()

        content: list[dict] = []

        if screen_image_b64:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screen_image_b64,
                    },
                }
            )

        content.append(
            {
                "type": "text",
                "text": self._build_user_prompt(instruction, screen_text, context),
            }
        )

        response = await client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self._build_system_prompt(),
            messages=[{"role": "user", "content": content}],
        )

        raw_text = ""
        for block in response.content:
            if block.type == "text":
                raw_text += block.text

        return self._parse_response(self.name, raw_text)
