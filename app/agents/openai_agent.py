"""OpenAI (GPT) agent implementation."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.agents.base import AgentResponse, BaseAgent


class OpenAIAgent(BaseAgent):
    """Agent powered by OpenAI's GPT models."""

    def __init__(self, api_key: str = "", model: str = "gpt-4o"):
        super().__init__(name="OpenAI GPT", api_key=api_key, model=model)
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def _call_api(
        self,
        instruction: str,
        screen_text: str = "",
        screen_image_b64: str = "",
        context: str = "",
    ) -> AgentResponse:
        client = self._get_client()

        messages: list[dict] = [
            {"role": "system", "content": self._build_system_prompt()},
        ]

        # Build user message with optional image
        user_content: list[dict] = []

        if screen_image_b64:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{screen_image_b64}",
                        "detail": "high",
                    },
                }
            )

        user_content.append(
            {
                "type": "text",
                "text": self._build_user_prompt(instruction, screen_text, context),
            }
        )

        messages.append({"role": "user", "content": user_content})

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
            temperature=0.3,
        )

        raw_text = response.choices[0].message.content or ""
        return self._parse_response(self.name, raw_text)
