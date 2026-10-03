from unittest.mock import MagicMock

from openai import APITimeoutError

from app.ai.freellmapi import FreeLLMAPIService


def test_sse_timeout_after_gateway_acceptance_is_not_gateway_outage():
    error = APITimeoutError(request=MagicMock())

    kind, status, headers = FreeLLMAPIService._classify_error(
        error,
        response_headers={
            "X-Routed-Via": "cloudflare/@cf/openai/gpt-oss-20b",
            "X-Fallback-Attempts": "1",
        },
        response_status_code=200,
    )

    assert kind == "upstream_failed"
    assert status == 200
    assert headers["x-routed-via"] == "cloudflare/@cf/openai/gpt-oss-20b"
    assert headers["x-fallback-attempts"] == "1"


def test_connection_timeout_before_gateway_response_allows_fallback():
    error = APITimeoutError(request=MagicMock())

    kind, status, _ = FreeLLMAPIService._classify_error(error)

    assert kind == "gateway_unavailable"
    assert status is None
