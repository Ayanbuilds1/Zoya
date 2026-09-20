from __future__ import annotations

from abc import ABC, abstractmethod

from app.research.models import SearchResult


class ResearchProviderError(RuntimeError):
    """Base exception for research provider failures."""


class ResearchProviderUnavailable(ResearchProviderError):
    """Raised when a provider is not configured or cannot be used."""


class ResearchProvider(ABC):
    """Provider-independent interface for web research."""

    name: str

    @abstractmethod
    async def is_available(self) -> bool:
        """Return whether the provider is configured and usable."""
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[SearchResult]:
        """Search the web and return normalized results."""
        raise NotImplementedError