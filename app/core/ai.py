import concurrent.futures
import re
import socket
import time
from collections.abc import Iterator
from typing import Any

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


# How long one provider is allowed to block the current request
# before FailoverAIProvider moves to the next provider.
PROVIDER_REQUEST_TIMEOUT_SECONDS = 20

# Failed providers that hit quota/rate-limit stay skipped for this
# amount of time for future requests.
PROVIDER_COOLDOWN_SECONDS = 60


# Shared cooldown state across all FailoverAIProvider instances.
# This means a provider that recently hit a quota/rate-limit is
# skipped by other instances in the same Python process as well.
_PROVIDER_COOLDOWNS: dict[str, float] = {}


def _sanitize_zoya_response(response: str) -> str:
    """
    Apply provider-independent Zoya persona normalization.
    """

    if not response:
        return response

    cleaned = response

    cleaned = re.sub(
        r"\bAyan\s*[-,]?\s*ji\b",
        "Ayan",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned


def _create_provider(name: str) -> AIProvider | None:
    """
    Create one configured provider.

    Providers without an API key are skipped from the failover chain.
    """

    name = name.strip().lower()

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

    Intended order for the current Zoya setup:

        Groq -> Gemini -> OpenRouter

    Conversation history is accepted here so the manager remains
    compatible with the conversation-aware AIProvider interface.
    """

    def __init__(self) -> None:
        provider_names = [
            PRIMARY_AI_PROVIDER,
            *AI_FALLBACK_PROVIDERS,
        ]

        self.providers: list[tuple[str, AIProvider]] = []
        self.seen: set[str] = set()

        for raw_name in provider_names:
            name = raw_name.strip().lower()

            if not name or name in self.seen:
                continue

            self.seen.add(name)

            provider = _create_provider(name)

            if provider is not None:
                self.providers.append((name, provider))
            else:
                print(
                    f"⚪ {name} is not configured or has no valid API key. "
                    f"Skipping provider..."
                )

        if not self.providers:
            raise RuntimeError(
                "No AI provider with a valid API key is configured."
            )

        self.active_provider = self.providers[0][0]

        print(
            "[AI] Provider chain: "
            + " -> ".join(name for name, _ in self.providers)
        )

    def _is_on_cooldown(self, name: str) -> bool:
        cooldown_until = _PROVIDER_COOLDOWNS.get(name)

        if cooldown_until is None:
            return False

        if time.time() >= cooldown_until:
            _PROVIDER_COOLDOWNS.pop(name, None)
            return False

        return True

    def _set_cooldown(self, name: str) -> None:
        _PROVIDER_COOLDOWNS[name] = (
            time.time() + PROVIDER_COOLDOWN_SECONDS
        )

    @staticmethod
    def _send_to_provider(
        provider: AIProvider,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Support both conversation-aware providers and older providers
        that only accept the message argument.
        """

        if conversation_history is None:
            return provider.send_message(message)

        try:
            return provider.send_message(
                message,
                conversation_history=conversation_history,
            )

        except TypeError as error:
            # Some older adapters may not support conversation_history.
            # Only use the compatibility fallback for an actual
            # unsupported-keyword TypeError.
            error_text = str(error).lower()

            if (
                "conversation_history" not in error_text
                and "unexpected keyword argument" not in error_text
            ):
                raise

            return provider.send_message(message)

    @staticmethod
    def _classify_error(error: Exception) -> str:
        """
        Convert provider exceptions into a practical failover category.
        """

        if isinstance(
            error,
            (
                TimeoutError,
                concurrent.futures.TimeoutError,
                socket.timeout,
            ),
        ):
            return "timeout"

        error_text = str(error).lower()

        rate_limit_markers = (
            "429",
            "rate limit",
            "rate_limit",
            "quota",
            "too many requests",
            "resource exhausted",
        )

        if any(marker in error_text for marker in rate_limit_markers):
            return "rate_limit"

        network_markers = (
            "connection",
            "connect error",
            "connection reset",
            "connection aborted",
            "network",
            "dns",
            "timed out",
            "timeout",
            "502",
            "503",
            "504",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        )

        if any(marker in error_text for marker in network_markers):
            return "network"

        auth_markers = (
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "invalid api key",
            "invalid_api_key",
            "authentication",
            "api key",
        )

        if any(marker in error_text for marker in auth_markers):
            return "auth/config"

        provider_markers = (
            "500",
            "internal server error",
            "server error",
            "provider error",
            "api error",
        )

        if any(marker in error_text for marker in provider_markers):
            return "provider_error"

        return "unknown"

    @staticmethod
    def _run_with_timeout(
        provider: AIProvider,
        message: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> str:
        """
        Run a synchronous provider call with a bounded timeout.

        This is intentionally kept in the failover manager so one
        provider cannot block the entire Zoya request indefinitely.
        """

        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1
        )

        future = executor.submit(
            FailoverAIProvider._send_to_provider,
            provider,
            message,
            conversation_history,
        )

        try:
            return future.result(
                timeout=PROVIDER_REQUEST_TIMEOUT_SECONDS
            )

        except concurrent.futures.TimeoutError as error:
            future.cancel()

            raise TimeoutError(
                "Provider request timed out after "
                f"{PROVIDER_REQUEST_TIMEOUT_SECONDS}s."
            ) from error

        finally:
            # Do not wait for a stuck provider call.
            # The request must be allowed to fail over immediately.
            executor.shutdown(
                wait=False,
                cancel_futures=True,
            )

    @staticmethod
    def _validate_response(response: Any) -> str:
        """
        Reject empty/whitespace provider responses.
        """

        if response is None:
            raise RuntimeError("Provider returned no response.")

        if not isinstance(response, str):
            raise TypeError(
                f"Provider returned unsupported response type: "
                f"{type(response).__name__}"
            )

        if not response.strip():
            raise RuntimeError(
                "Provider returned an empty response."
            )

        return response

    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        last_error: Exception | None = None

        for index, (name, provider) in enumerate(self.providers):
            if self._is_on_cooldown(name):
                print(
                    f"⏳ {name} is on cooldown. Skipping..."
                )
                continue

            print(
                f"🤖 [AI] Trying provider: {name}"
            )

            try:
                response = self._run_with_timeout(
                    provider=provider,
                    message=message,
                    conversation_history=conversation_history,
                )

                response = self._validate_response(response)
                response = _sanitize_zoya_response(response)

                self.active_provider = name

                print(
                    f"✅ [AI] {name} responded successfully."
                )

                return response

            except Exception as error:
                last_error = error

                category = self._classify_error(error)

                print(
                    f"⚠️ [AI] {name} failed "
                    f"({category}): {error}"
                )

                # Rate-limit/quota errors trigger the normal cooldown.
                # The current request immediately continues to the
                # next provider.
                if category == "rate_limit":
                    self._set_cooldown(name)

                    print(
                        f"⏳ [AI] {name} cooldown set for "
                        f"{PROVIDER_COOLDOWN_SECONDS}s."
                    )

                # Any provider failure that is safe to fail over from
                # moves to the next configured provider.
                has_next_provider = (
                    index < len(self.providers) - 1
                )

                if has_next_provider:
                    next_name = self.providers[index + 1][0]

                    print(
                        f"➡️ [AI] Falling back from "
                        f"{name} -> {next_name}"
                    )

                    continue

                print(
                    f"❌ [AI] No remaining providers after {name}."
                )

        raise RuntimeError(
            "All configured AI providers are currently unavailable."
        ) from last_error

    @staticmethod
    def _stream_from_provider(
        provider: AIProvider,
        message: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> Iterator[str]:
        """Call native provider streaming while retaining legacy adapters."""
        if conversation_history is None:
            return iter(provider.stream_message(message))

        try:
            return iter(provider.stream_message(
                message,
                conversation_history=conversation_history,
            ))
        except TypeError as error:
            error_text = str(error).lower()
            if (
                "conversation_history" not in error_text
                and "unexpected keyword argument" not in error_text
            ):
                raise
            return iter(provider.stream_message(message))

    @staticmethod
    def _next_stream_chunk(iterator: Iterator[str]) -> str:
        """Bound waiting for a native stream's next item before exposure."""
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(next, iterator)
        try:
            return future.result(timeout=PROVIDER_REQUEST_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError as error:
            future.cancel()
            raise TimeoutError(
                "Provider stream did not produce a chunk within "
                f"{PROVIDER_REQUEST_TIMEOUT_SECONDS}s."
            ) from error
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def stream_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        """Forward native provider chunks and fail over only before output.

        Once a chunk is visible, restarting on another model could duplicate
        the reply. In that case the caller receives a controlled stream error
        and retains the already displayed partial text.
        """
        last_error: Exception | None = None

        for index, (name, provider) in enumerate(self.providers):
            if self._is_on_cooldown(name):
                print(f"⏳ {name} is on cooldown. Skipping stream...")
                continue

            exposed_output = False
            try:
                print(f"🤖 [AI] Trying provider stream: {name}")
                iterator = self._stream_from_provider(
                    provider,
                    message,
                    conversation_history,
                )

                first_chunk = ""
                while not first_chunk:
                    try:
                        first_chunk = self._next_stream_chunk(iterator)
                    except StopIteration as error:
                        raise RuntimeError(
                            "Provider returned an empty streamed response."
                        ) from error
                    if first_chunk is None:
                        first_chunk = ""
                    elif not isinstance(first_chunk, str):
                        raise TypeError("Provider yielded a non-text stream chunk.")

                self.active_provider = name
                exposed_output = True
                yield _sanitize_zoya_response(first_chunk)

                for chunk in iterator:
                    if chunk is None or chunk == "":
                        continue
                    if not isinstance(chunk, str):
                        raise TypeError("Provider yielded a non-text stream chunk.")
                    yield _sanitize_zoya_response(chunk)

                print(f"✅ [AI] {name} stream completed.")
                return

            except Exception as error:
                last_error = error
                if exposed_output:
                    raise RuntimeError(
                        "The provider stream ended before Zoya could finish."
                    ) from error

                category = self._classify_error(error)
                print(f"⚠️ [AI] {name} stream failed ({category}): {error}")
                if category == "rate_limit":
                    self._set_cooldown(name)

                if index < len(self.providers) - 1:
                    print(
                        f"➡️ [AI] Falling back before first chunk: "
                        f"{name} -> {self.providers[index + 1][0]}"
                    )
                    continue

        raise RuntimeError(
            "All configured AI providers are currently unavailable."
        ) from last_error


def create_ai_provider() -> AIProvider:
    return FailoverAIProvider()
