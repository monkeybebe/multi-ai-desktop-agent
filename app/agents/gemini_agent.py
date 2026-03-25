"""Google Gemini agent implementation."""

from __future__ import annotations

import httpx

from app.agents.base import AgentResponse, BaseAgent


class GeminiAgent(BaseAgent):
    """Agent powered by Google's Gemini models."""

    def __init__(self, api_key: str = "", model: str = "gemini-1.5-pro"):
        super().__init__(name="Google Gemini", api_key=api_key, model=model)

    async def _call_api(
        self,
        instruction: str,
        screen_text: str = "",
        screen_image_b64: str = "",
        context: str = "",
    ) -> AgentResponse:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            f":generateContent?key={self.api_key}"
        )

        parts: list[dict] = []

        # Add system instruction as text
        parts.append({"text": self._build_system_prompt()})

        # Add image if available
        if screen_image_b64:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": screen_image_b64,
                    }
                }
            )

        # Add user prompt
        parts.append(
            {"text": self._build_user_prompt(instruction, screen_text, context)}
        )

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        raw_text = ""
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            for part in content.get("parts", []):
                if "text" in part:
                    raw_text += part["text"]

        return self._parse_response(self.name, raw_text)
