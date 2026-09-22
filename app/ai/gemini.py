from collections.abc import Iterator

from google import genai

from app.ai.provider import AIProvider, ZOYA_SYSTEM_INSTRUCTION
from app.config import GEMINI_API_KEY


class GeminiService(AIProvider):
    def __init__(self) -> None:
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def _build_request(self, message: str) -> dict:
        return {
            "model": "gemini-3.6-flash",
            "input": message,
            "system_instruction": ZOYA_SYSTEM_INSTRUCTION,
        }

    def send_message(self, message: str) -> str:
        interaction = self.client.interactions.create(
            **self._build_request(message)
        )

        if not interaction.output_text:
            raise RuntimeError("Gemini returned an empty response.")

        return interaction.output_text

    def stream_message(self, message: str) -> Iterator[str]:
        request = self._build_request(message)
        request["stream"] = True

        stream = self.client.interactions.create(**request)

        emitted_text = False

        for event in stream:
            event_type = getattr(event, "event_type", None)

            if event_type != "step.delta":
                continue

            delta = getattr(event, "delta", None)

            if delta is None:
                continue

            if getattr(delta, "type", None) != "text":
                continue

            text = getattr(delta, "text", None)

            if not text:
                continue

            emitted_text = True
            yield text

        if not emitted_text:
            raise RuntimeError("Gemini returned an empty streamed response.")
