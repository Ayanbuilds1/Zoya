from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .image_provider import ImageGenerationRequest, ImageGenerationResult, ImageProvider


LOGGER = logging.getLogger(__name__)


@dataclass
class _ProviderHealth:
    cooldown_until: datetime | None = None
    permanent_failure: bool = False
    last_error_code: str | None = None

    def available(self, now: datetime) -> bool:
        if self.permanent_failure:
            return False
        if self.cooldown_until is None:
            return True
        return now >= self.cooldown_until


class ImageProviderRouter:
    """Capability-aware image provider router with fallback and cooldown."""

    def __init__(
        self,
        providers: Iterable[ImageProvider],
        *,
        provider_order: list[str] | None = None,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self._providers = {provider.name: provider for provider in providers}
        self._order = provider_order or [provider.name for provider in providers]
        self._cooldown_seconds = max(1.0, cooldown_seconds)
        self._health: dict[str, _ProviderHealth] = {
            name: _ProviderHealth() for name in self._providers
        }

    def _ordered_providers(self) -> list[ImageProvider]:
        seen: set[str] = set()
        ordered: list[ImageProvider] = []

        for name in self._order:
            provider = self._providers.get(name)
            if provider is not None and name not in seen:
                ordered.append(provider)
                seen.add(name)

        # Keep newly added providers reachable even if config omitted them.
        for name, provider in self._providers.items():
            if name not in seen:
                ordered.append(provider)

        return ordered

    def _cooldown(self, name: str, *, permanent: bool, code: str) -> None:
        health = self._health.setdefault(name, _ProviderHealth())
        health.last_error_code = code
        health.permanent_failure = permanent

        if not permanent:
            health.cooldown_until = (
                datetime.now(timezone.utc)
                + timedelta(seconds=self._cooldown_seconds)
            )

    def health_snapshot(self) -> dict[str, dict[str, object]]:
        now = datetime.now(timezone.utc)
        snapshot: dict[str, dict[str, object]] = {}
        for name, health in self._health.items():
            snapshot[name] = {
                "available": health.available(now),
                "cooldown_until": (
                    health.cooldown_until.isoformat()
                    if health.cooldown_until
                    else None
                ),
                "permanent_failure": health.permanent_failure,
                "last_error_code": health.last_error_code,
            }
        return snapshot

    def generate(
        self,
        request: ImageGenerationRequest,
    ) -> ImageGenerationResult:
        attempted: list[str] = []
        failures: list[dict[str, object]] = []

        now = datetime.now(timezone.utc)

        for provider in self._ordered_providers():
            health = self._health.setdefault(provider.name, _ProviderHealth())

            if not health.available(now):
                LOGGER.info(
                    "[IMAGE_ROUTER] provider=%s status=skipped reason=health",
                    provider.name,
                )
                continue

            try:
                if not provider.supports(request):
                    LOGGER.info(
                        "[IMAGE_ROUTER] provider=%s status=skipped reason=capability_mismatch",
                        provider.name,
                    )
                    failures.append(
                        {
                            "provider": provider.name,
                            "code": "capability_mismatch",
                        }
                    )
                    continue
            except Exception as exc:
                LOGGER.warning(
                    "[IMAGE_ROUTER] provider=%s status=capability_check_failed error=%s",
                    provider.name,
                    type(exc).__name__,
                )
                failures.append(
                    {
                        "provider": provider.name,
                        "code": "capability_check_failed",
                    }
                )
                continue

            attempted.append(provider.name)
            started = time.monotonic()

            try:
                result = provider.generate(request)
            except Exception as exc:
                elapsed = time.monotonic() - started
                self._cooldown(
                    provider.name,
                    permanent=False,
                    code="provider_exception",
                )
                LOGGER.warning(
                    "[IMAGE_ROUTER] provider=%s status=failed reason=provider_exception latency=%.2fs",
                    provider.name,
                    elapsed,
                )
                failures.append(
                    {
                        "provider": provider.name,
                        "code": "provider_exception",
                    }
                )
                continue

            elapsed = time.monotonic() - started

            if result.success and result.image_path:
                # A previous transient failure should not keep the provider
                # degraded once it proves it can generate again.
                self._health[provider.name] = _ProviderHealth()
                result.metadata = {
                    **result.metadata,
                    "attempted_providers": attempted,
                    "latency_seconds": round(elapsed, 3),
                    "fallback_failures": failures,
                }
                LOGGER.info(
                    "[IMAGE_ROUTER] provider=%s model=%s status=success latency=%.2fs",
                    provider.name,
                    result.model or "default",
                    elapsed,
                )
                return result

            code = result.error_code or "provider_failed"
            permanent = code in {
                "missing_api_key",
                "invalid_api_key",
                "invalid_configuration",
                "unsupported_model",
            }
            self._cooldown(
                provider.name,
                permanent=permanent,
                code=code,
            )

            LOGGER.warning(
                "[IMAGE_ROUTER] provider=%s model=%s status=failed reason=%s fallback=next",
                provider.name,
                result.model or "default",
                code,
            )
            failures.append(
                {
                    "provider": provider.name,
                    "code": code,
                    "message": result.error_message or "Provider failed.",
                }
            )

        return ImageGenerationResult(
            success=False,
            provider="router",
            error_code="all_providers_failed",
            error_message="All configured image providers failed or were unavailable.",
            retryable=any(
                failure.get("code")
                in {"timeout", "rate_limited", "server_error", "network_error"}
                for failure in failures
            ),
            metadata={
                "attempted_providers": attempted,
                "failures": failures,
            },
        )
