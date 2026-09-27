import time
from collections.abc import Iterator

from app.ai.claude import ClaudeService
from app.ai.gemini import GeminiService
from app.ai.groq import GroqService
from app.ai.openai import OpenAIService
from app.ai.openrouter import OpenRouterService
from app.ai.provider import AIProvider

from app.config import (
    AI_FALLBACK_PROVIDERS,
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    PRIMARY_AI_PROVIDER,
)


PROVIDER_COOLDOWN_SECONDS = 60


def _create_provider(name: str) -> AIProvider | None:
    if name == "gemini":
        if not GEMINI_API_KEY:
            return None
        return GeminiService()

    if name == "groq":
        if not GROQ_API_KEY:
            return None
        return GroqService()

    if name == "openrouter":
        if not OPENROUTER_API_KEY:
            return None
        return OpenRouterService()

    if name == "openai":
        if not OPENAI_API_KEY:
            return None
        return OpenAIService()

    if name == "claude":
        if not ANTHROPIC_API_KEY:
            return None
        return ClaudeService()

    return None


class FailoverAIProvider(AIProvider):
    def __init__(self) -> None:
        provider_names = [
            PRIMARY_AI_PROVIDER,
            *AI_FALLBACK_PROVIDERS,
        ]

        self.providers: list[tuple[str, AIProvider]] = []
        self.cooldowns: dict[str, float] = {}
        self.seen: set[str] = set()

        for name in provider_names:
            if name in self.seen:
                continue

            self.seen.add(name)

            provider = _create_provider(name)

            if provider is not None:
                self.providers.append(
                    (name, provider)
                )

        if not self.providers:
            raise RuntimeError(
                "No AI provider with a valid API key is configured."
            )

        self.active_provider = self.providers[0][0]

    def _is_on_cooldown(self, name: str) -> bool:
        cooldown_until = self.cooldowns.get(name)

        if cooldown_until is None:
            return False

        if time.time() >= cooldown_until:
            del self.cooldowns[name]
            return False

        return True

    def _set_cooldown(self, name: str) -> None:
        self.cooldowns[name] = (
            time.time() + PROVIDER_COOLDOWN_SECONDS
        )

    @staticmethod
    def _is_quota_error(error: Exception) -> bool:
        error_text = str(error).lower()

        return (
            "429" in error_text
            or "rate limit" in error_text
            or "quota" in error_text
            or "too many requests" in error_text
        )

    def send_message(self, message: str) -> str:
        last_error: Exception | None = None

        for name, provider in self.providers:
            if self._is_on_cooldown(name):
                print(
                    f"⏳ {name} is temporarily on cooldown. "
                    f"Skipping..."
                )
                continue

            try:
                response = provider.send_message(message)

                self.active_provider = name

                return response

            except Exception as error:
                last_error = error

                if not self._is_quota_error(error):
                    raise

                self._set_cooldown(name)

                print(
                    f"⚠️ {name} quota/rate limit reached. "
                    f"Cooldown: {PROVIDER_COOLDOWN_SECONDS}s. "
                    f"Trying next provider..."
                )

        raise RuntimeError(
            "All configured AI providers are currently unavailable."
        ) from last_error

    def stream_message(self, message: str) -> Iterator[str]:
        last_error: Exception | None = None

        for name, provider in self.providers:
            if self._is_on_cooldown(name):
                print(
                    f"⏳ {name} is temporarily on cooldown. "
                    f"Skipping streaming..."
                )
                continue

            iterator = None

            try:
                iterator = iter(provider.stream_message(message))

                # Read the first non-empty chunk before committing to a
                # provider. If it fails with a quota/rate error here, we can
                # safely fail over without duplicating visible output.
                first_chunk = None

                while first_chunk is None:
                    try:
                        chunk = next(iterator)
                    except StopIteration as error:
                        raise RuntimeError(
                            f"{name} returned an empty streamed response."
                        ) from error

                    if chunk:
                        first_chunk = str(chunk)

                self.active_provider = name

                yield first_chunk

                # Once text has been exposed to the user, do not switch to
                # another provider mid-response. That could duplicate or
                # corrupt the answer.
                for chunk in iterator:
                    if chunk:
                        yield str(chunk)

                return

            except Exception as error:
                last_error = error

                if not self._is_quota_error(error):
                    raise

                self._set_cooldown(name)

                print(
                    f"⚠️ {name} streaming quota/rate limit reached. "
                    f"Cooldown: {PROVIDER_COOLDOWN_SECONDS}s. "
                    f"Trying next provider..."
                )

        raise RuntimeError(
            "All configured AI providers are currently unavailable."
        ) from last_error


def create_ai_provider() -> AIProvider:
    return FailoverAIProvider()
