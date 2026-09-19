import inspect
import time

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

from app.exceptions import (
    AIProviderError,
    AIServiceError,
)


PROVIDER_COOLDOWN_SECONDS = 60


def _create_provider(
    name: str,
) -> AIProvider | None:
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
    """
    AI provider manager with automatic fallback support.

    Example:

        Groq -> OpenRouter -> Gemini
    """

    def __init__(self) -> None:
        provider_names = [
            PRIMARY_AI_PROVIDER,
            *AI_FALLBACK_PROVIDERS,
        ]

        self.providers: list[
            tuple[str, AIProvider]
        ] = []

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
            raise AIServiceError(
                message=(
                    "No configured AI provider "
                    "is available."
                ),
                user_message=(
                    "Zoya ke liye abhi koi AI provider "
                    "available nahi hai."
                ),
            )

        self.active_provider = self.providers[0][0]

    def _is_on_cooldown(
        self,
        name: str,
    ) -> bool:
        cooldown_until = self.cooldowns.get(name)

        if cooldown_until is None:
            return False

        if time.time() >= cooldown_until:
            del self.cooldowns[name]
            return False

        return True

    def _set_cooldown(
        self,
        name: str,
    ) -> None:
        self.cooldowns[name] = (
            time.time()
            + PROVIDER_COOLDOWN_SECONDS
        )

    @staticmethod
    def _is_retryable_error(
        error: Exception,
    ) -> bool:
        """
        Determine whether the provider error is suitable
        for trying another configured provider.
        """

        error_text = str(error).lower()

        retryable_patterns = (
            "429",
            "rate limit",
            "quota",
            "too many requests",
            "timeout",
            "timed out",
            "temporarily unavailable",
            "service unavailable",
            "connection",
            "connection error",
            "connecterror",
            "read timeout",
            "server error",
            "internal server error",
            "503",
            "502",
            "504",
        )

        return any(
            pattern in error_text
            for pattern in retryable_patterns
        )

    @staticmethod
    def _provider_error_message(
        provider_name: str,
        error: Exception,
    ) -> str:
        """
        Create a readable internal log message without
        exposing unnecessary provider/API details.
        """

        return (
            f"{provider_name} failed: "
            f"{type(error).__name__}: {error}"
        )

    @staticmethod
    def _supports_conversation_history(
        provider: AIProvider,
    ) -> bool:
        """
        Check whether a provider's send_message method
        supports the new conversation_history argument.

        Groq and OpenRouter currently support it.

        Older providers such as Gemini/Claude/OpenAI may
        still use the original send_message(message)
        signature, so they continue working without the
        structured history until their adapters are updated.
        """

        try:
            parameters = inspect.signature(
                provider.send_message
            ).parameters

        except (TypeError, ValueError):
            return False

        if "conversation_history" in parameters:
            return True

        return any(
            parameter.kind
            == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )

    @classmethod
    def _send_to_provider(
        cls,
        provider: AIProvider,
        message: str,
        conversation_history: list[
            dict[str, str]
        ] | None = None,
    ) -> str:
        """
        Send a request while remaining compatible with both:

        1. New providers supporting conversation_history.
        2. Older providers using send_message(message).
        """

        if (
            conversation_history
            and cls._supports_conversation_history(
                provider
            )
        ):
            return provider.send_message(
                message,
                conversation_history=conversation_history,
            )

        return provider.send_message(message)

    def send_message(
        self,
        message: str,
        conversation_history: list[
            dict[str, str]
        ] | None = None,
    ) -> str:
        """
        Send a message using the first available provider.

        Conversation history is forwarded to providers that
        support the structured history interface.
        """

        last_error: Exception | None = None
        failed_providers: list[str] = []

        for name, provider in self.providers:
            if self._is_on_cooldown(name):
                print(
                    f"⏳ {name} is temporarily "
                    f"on cooldown. Skipping..."
                )

                failed_providers.append(
                    f"{name} (cooldown)"
                )

                continue

            try:
                response = self._send_to_provider(
                    provider=provider,
                    message=message,
                    conversation_history=(
                        conversation_history
                    ),
                )

                self.active_provider = name

                if failed_providers:
                    print(
                        f"🔄 AI failover successful. "
                        f"Active provider: {name}"
                    )

                return response

            except Exception as error:
                last_error = error

                failed_providers.append(name)

                print(
                    f"⚠️ "
                    f"{self._provider_error_message(name, error)}"
                )

                if not self._is_retryable_error(
                    error
                ):
                    print(
                        f"❌ {name} error is "
                        f"not retryable."
                    )

                    raise AIProviderError(
                        provider=name,
                        message=str(error),
                        is_retryable=False,
                    ) from error

                self._set_cooldown(name)

                print(
                    f"🔄 {name} unavailable. "
                    f"Cooldown: "
                    f"{PROVIDER_COOLDOWN_SECONDS}s. "
                    f"Trying next provider..."
                )

        provider_list = ", ".join(
            failed_providers
        )

        raise AIServiceError(
            message=(
                "All configured AI providers failed. "
                f"Providers attempted: "
                f"{provider_list}"
            ),
            user_message=(
                "Abhi Zoya ke AI providers "
                "available nahi hain. "
                "Thodi der baad dobara try kijiye."
            ),
            failed_providers=failed_providers,
        ) from last_error


def create_ai_provider() -> AIProvider:
    return FailoverAIProvider()