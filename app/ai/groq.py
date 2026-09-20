from collections.abc import Iterator

from groq import Groq

from app.ai.provider import AIProvider, build_chat_messages
from app.config import GROQ_API_KEY, GROQ_MODEL


class GroqService(AIProvider):
    def __init__(self) -> None:
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is missing."
            )

        self.client = Groq(
            api_key=GROQ_API_KEY
        )

    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
                response = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=build_chat_messages(message),
            max_tokens=2048,
        )
                content = response.choices[0].message.content
                if not content:
                     raise RuntimeError(
                "Groq returned an empty response."
            )
                return content

    def stream_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=build_chat_messages(message),
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
                "Groq returned an empty streamed response."
            )