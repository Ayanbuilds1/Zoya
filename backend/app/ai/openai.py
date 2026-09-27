from openai import OpenAI

from app.ai.provider import AIProvider
from app.config import OPENAI_API_KEY, OPENAI_MODEL


class OpenAIService(AIProvider):
    def __init__(self) -> None:
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is missing."
            )

        self.client = OpenAI(
            api_key=OPENAI_API_KEY
        )

    def send_message(self, message: str) -> str:
        response = self.client.responses.create(
            model=OPENAI_MODEL,
            input=message,
        )

        if not response.output_text:
            raise RuntimeError(
                "OpenAI returned an empty response."
            )

        return response.output_text