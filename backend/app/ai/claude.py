from anthropic import Anthropic

from app.ai.provider import AIProvider
from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL


class ClaudeService(AIProvider):
    def __init__(self) -> None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is missing."
            )

        self.client = Anthropic(
            api_key=ANTHROPIC_API_KEY
        )

    def send_message(self, message: str) -> str:
        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": message,
                }
            ],
        )

        if not response.content:
            raise RuntimeError(
                "Claude returned an empty response."
            )

        return response.content[0].text