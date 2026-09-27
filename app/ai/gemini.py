from collections.abc import Iterator

from google import genai
from google.genai import types

from app.ai.provider import AIProvider, ZOYA_SYSTEM_INSTRUCTION
from app.config import GEMINI_API_KEY


GEMINI_REQUEST_TIMEOUT_MS = 20_000


class GeminiService(AIProvider):
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is missing.")

        self.client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=GEMINI_REQUEST_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    @staticmethod
    def _build_contextual_input(
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Gemini's current Interactions adapter receives the system instruction
        separately, so conversation history is serialized into the user input.
        This keeps Gemini conversation-aware without sharing cross-conversation
        interaction IDs/state.
        """
        if not conversation_history:
            return message

        lines = ["CONVERSATION HISTORY:"]

        for item in conversation_history:
            role = item.get("role")
            content = item.get("content")

            if role not in {"user", "assistant"}:
                continue

            if not isinstance(content, str):
                continue

            content = content.strip()
            if not content:
                continue

            label = "USER" if role == "user" else "ZOYA"
            lines.append(f"{label}: {content}")

        lines.extend(
            [
                "",
                "CURRENT USER REQUEST:",
                message,
            ]
        )

        return "\n".join(lines)

    def _build_request(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict:
        return {
            "model": "gemini-3.6-flash",
            "input": self._build_contextual_input(
                message,
                conversation_history=conversation_history,
            ),
            "system_instruction": ZOYA_SYSTEM_INSTRUCTION,
        }

    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        interaction = self.client.interactions.create(
            **self._build_request(
                message,
                conversation_history=conversation_history,
            )
        )

        if not interaction.output_text:
            raise RuntimeError("Gemini returned an empty response.")

        return interaction.output_text

    def stream_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        request = self._build_request(
            message,
            conversation_history=conversation_history,
        )
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
