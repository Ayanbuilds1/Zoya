from __future__ import annotations

from collections.abc import Iterator
import time
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
)

from app.ai.provider import AIProvider, build_chat_messages
from app.config import (
    FREELLMAPI_API_KEY,
    FREELLMAPI_BASE_URL,
    FREELLMAPI_CHAT_MODEL,
    FREELLMAPI_MAX_TOKENS,
    FREELLMAPI_NATIVE_STREAM,
    FREELLMAPI_REQUEST_TIMEOUT_SECONDS,
    FREELLMAPI_STREAM_REQUEST_TIMEOUT_SECONDS,
    FREELLMAPI_STREAM_CHUNK_CHARS,
    FREELLMAPI_STREAM_CHUNK_DELAY_MS,
)


class FreeLLMAPIError(RuntimeError):
    """Normalized FreeLLMAPI failure with gateway/upstream classification."""

    def __init__(
        self,
        message: str,
        *,
        kind: str,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.headers = headers or {}


class FreeLLMAPIService(AIProvider):
    """
    Normal-chat adapter for the self-hosted FreeLLMAPI OpenAI-compatible gateway.

    The gateway remains the primary router. A gateway-level outage is classified
    separately from an upstream provider failure so Zoya can decide whether
    direct-provider fallback is allowed.
    """

    name = "freellmapi"

    _UPSTREAM_MARKERS = (
        "upstream_failed",
        "upstream provider errors",
        "all routed attempt",
        "routing_exhausted",
        "attempt trail",
        "fallback trail",
        "fallback-trail",
    )

    def __init__(self) -> None:
        if not FREELLMAPI_API_KEY:
            raise RuntimeError("FREELLMAPI_API_KEY is missing.")

        base_url = FREELLMAPI_BASE_URL.rstrip("/")

        self.client = OpenAI(
            api_key=FREELLMAPI_API_KEY,
            base_url=base_url,
            timeout=FREELLMAPI_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
        self.stream_client = OpenAI(
            api_key=FREELLMAPI_API_KEY,
            base_url=base_url,
            timeout=FREELLMAPI_STREAM_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
        self.last_route_metadata: dict[str, str] = {}

    @staticmethod
    def _headers_from_error(error: Exception) -> dict[str, str]:
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
        if headers is None:
            return {}

        try:
            return {
                str(key).lower(): str(value)
                for key, value in headers.items()
            }
        except Exception:
            return {}

    @staticmethod
    def _body_from_error(error: Exception) -> str:
        response = getattr(error, "response", None)
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text[:4000]

        body = getattr(error, "body", None)
        if body is not None:
            return str(body)[:4000]

        return str(error)[:4000]

    @classmethod
    def _classify_error(
        cls,
        error: Exception,
    ) -> tuple[str, int | None, dict[str, str]]:
        headers = cls._headers_from_error(error)
        body = cls._body_from_error(error).lower()
        status_code = getattr(error, "status_code", None)

        if isinstance(
            error,
            (APIConnectionError, APITimeoutError, TimeoutError),
        ):
            return "gateway_unavailable", status_code, headers

        combined = " ".join(
            [
                body,
                headers.get("x-fallback-trail", ""),
                headers.get("x-fallback-detail", ""),
                headers.get("x-fallback-attempts", ""),
            ]
        ).lower()

        if any(
            marker in combined
            for marker in cls._UPSTREAM_MARKERS
        ):
            return "upstream_failed", status_code, headers

        if status_code in {
            400,
            401,
            403,
            404,
            409,
            422,
            429,
        }:
            return "request_error", status_code, headers

        if status_code is not None and status_code >= 500:
            return "gateway_unavailable", status_code, headers

        if isinstance(error, (APIStatusError, APIError)):
            return "gateway_unavailable", status_code, headers

        text = str(error).lower()
        if any(
            marker in text
            for marker in (
                "connection refused",
                "connect error",
                "dns",
                "network",
            )
        ):
            return "gateway_unavailable", status_code, headers

        return "gateway_unavailable", status_code, headers

    @staticmethod
    def _route_metadata(
        headers: dict[str, str],
    ) -> dict[str, str]:
        keys = (
            "x-routed-via",
            "x-fallback-attempts",
            "x-fallback-trail",
            "x-fallback-detail",
        )
        return {
            key: headers[key]
            for key in keys
            if key in headers
        }

    @staticmethod
    def _extract_content(response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise RuntimeError(
                "FreeLLMAPI returned no choices."
            )

        message = getattr(
            choices[0],
            "message",
            None,
        )
        content = getattr(
            message,
            "content",
            None,
        )

        if not isinstance(
            content,
            str,
        ) or not content.strip():
            raise RuntimeError(
                "FreeLLMAPI returned an empty response."
            )

        return content

    def _raise_classified(
        self,
        error: Exception,
    ) -> None:
        kind, status_code, headers = (
            self._classify_error(error)
        )
        detail = self._body_from_error(error)

        if kind == "upstream_failed":
            message = (
                "FreeLLMAPI gateway is reachable, but its configured "
                "upstream model pool could not complete the request."
            )
        elif kind == "request_error":
            message = (
                "FreeLLMAPI rejected the request. Check the gateway "
                "model, API key, or request configuration."
            )
        else:
            message = (
                "FreeLLMAPI gateway could not be reached or returned "
                "a gateway error."
            )

        if detail:
            print(
                "[FREELLMAPI] "
                f"kind={kind} status={status_code} "
                f"detail={detail[:800]}"
            )

        raise FreeLLMAPIError(
            message,
            kind=kind,
            status_code=status_code,
            headers=headers,
        ) from error

    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
        *,
        client: OpenAI | None = None,
    ) -> str:
        try:
            active_client = client or self.client
            response = (
                active_client.chat.completions.create(
                    model=FREELLMAPI_CHAT_MODEL,
                    messages=build_chat_messages(
                        message,
                        conversation_history=conversation_history,
                    ),
                    max_tokens=FREELLMAPI_MAX_TOKENS,
                )
            )

            headers = getattr(
                response,
                "headers",
                {},
            ) or {}

            normalized_headers = {
                str(key).lower(): str(value)
                for key, value in headers.items()
            }

            self.last_route_metadata = (
                self._route_metadata(
                    normalized_headers
                )
            )

            return self._extract_content(response)

        except Exception as error:
            self._raise_classified(error)
            raise AssertionError("unreachable")

    def stream_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        """
        Use reliable buffered streaming by default.

        The FreeLLMAPI Desktop gateway has been observed to return a normal
        completion successfully while its native streaming endpoint can stall
        before the first chunk. Buffered mode calls the normal completion path
        once, then emits the completed text in local chunks so Zoya's SSE UI
        remains responsive without a long first-token timeout.

        Native gateway streaming remains available through
        FREELLMAPI_NATIVE_STREAM=true.
        """

        if not FREELLMAPI_NATIVE_STREAM:
            response = self.send_message(
                message,
                conversation_history=conversation_history,
                client=self.stream_client,
            )

            chunk_size = max(
                8,
                int(FREELLMAPI_STREAM_CHUNK_CHARS),
            )
            delay = max(
                0.0,
                float(
                    FREELLMAPI_STREAM_CHUNK_DELAY_MS
                ) / 1000.0,
            )

            for index in range(
                0,
                len(response),
                chunk_size,
            ):
                chunk = response[
                    index:index + chunk_size
                ]

                if chunk:
                    yield chunk

                if (
                    delay
                    and index + chunk_size < len(response)
                ):
                    time.sleep(delay)

            return

        try:
            stream = (
                self.client.chat.completions.create(
                    model=FREELLMAPI_CHAT_MODEL,
                    messages=build_chat_messages(
                        message,
                        conversation_history=conversation_history,
                    ),
                    max_tokens=FREELLMAPI_MAX_TOKENS,
                    stream=True,
                )
            )

            emitted_text = False

            for chunk in stream:
                if not getattr(
                    chunk,
                    "choices",
                    None,
                ):
                    continue

                delta = getattr(
                    chunk.choices[0],
                    "delta",
                    None,
                )
                content = getattr(
                    delta,
                    "content",
                    None,
                )

                if (
                    not isinstance(
                        content,
                        str,
                    )
                    or not content
                ):
                    continue

                emitted_text = True
                yield content

            if not emitted_text:
                raise RuntimeError(
                    "FreeLLMAPI returned an empty streamed response."
                )

        except Exception as error:
            self._raise_classified(error)
            raise AssertionError("unreachable")
