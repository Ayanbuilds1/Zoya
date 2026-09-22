from collections.abc import Iterator

from openai import OpenAI

from app.ai.provider import AIProvider, build_chat_messages
from app.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
)


class OpenRouterService(AIProvider):
    def __init__(self) -> None:
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is missing."
            )

        self.client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )

    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        response = self.client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=build_chat_messages(
                message,
                conversation_history=conversation_history,
            ),
            max_tokens=2048,
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "OpenRouter returned an empty response."
            )

        return content

    def stream_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=build_chat_messages(
                message,
                conversation_history=conversation_history,
            ),
            max_tokens=2048,
            stream=True,
        )

        emitted_text = False

        for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            content = getattr(
                delta,
                "content",
                None,
            )

            if not content:
                continue

            emitted_text = True
            yield content

        if not emitted_text:
            raise RuntimeError(
                "OpenRouter returned an empty streamed response."
            )