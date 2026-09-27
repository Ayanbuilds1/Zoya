from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.research.models import SearchResult
from app.research.provider import (
    ResearchProvider,
    ResearchProviderError,
    ResearchProviderUnavailable,
)


DEFAULT_EXCLUDED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
)


CURRENT_QUERY_HINTS = (
    "latest",
    "current",
    "recent",
    "today",
    "this week",
    "this month",
    "now",
    "2026",
    "2025",
    "2027",
    "what's happening",
    "what is happening",
    "developments",
    "trends",
    "updates",
    "news",
    "breakthroughs",
)


NEWS_QUERY_HINTS = (
    "news",
    "today",
    "latest",
    "recent",
    "this week",
    "what happened",
    "what's happening",
    "developments",
    "updates",
)


class TavilyResearchProvider(ResearchProvider):
    """Tavily Search API adapter."""

    name = "tavily"
    endpoint = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv(
                "TAVILY_API_KEY",
                "",
            ).strip()
        )

        self.timeout = max(
            5.0,
            float(timeout),
        )

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[SearchResult]:
        if not self.api_key:
            raise ResearchProviderUnavailable(
                "Tavily API key is not configured."
            )

        query = query.strip()

        max_results = max(
            1,
            min(
                int(max_results),
                20,
            ),
        )

        search_depth = self._choose_search_depth(
            query
        )

        topic = self._choose_topic(
            query
        )

        payload = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }

        exclude_domains = self._get_excluded_domains()

        if exclude_domains:
            payload["exclude_domains"] = (
                exclude_domains
            )

        headers = {
            "Authorization": (
                f"Bearer {self.api_key}"
            ),
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
            ) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                )

            response.raise_for_status()

            data = response.json()

        except httpx.HTTPStatusError as error:
            raise ResearchProviderError(
                "Tavily returned HTTP "
                f"{error.response.status_code}."
            ) from error

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
        ) as error:
            raise ResearchProviderError(
                f"Tavily network request failed: {error}"
            ) from error

        except (
            httpx.HTTPError,
            ValueError,
        ) as error:
            raise ResearchProviderError(
                f"Tavily request failed: {error}"
            ) from error

        results: list[SearchResult] = []

        raw_results = data.get(
            "results",
            [],
        )

        if not isinstance(
            raw_results,
            list,
        ):
            return []

        seen_urls: set[str] = set()

        for item in raw_results:
            if not isinstance(
                item,
                dict,
            ):
                continue

            url = str(
                item.get("url")
                or ""
            ).strip()

            if not url:
                continue

            normalized_url = (
                url.rstrip("/")
                .casefold()
            )

            if normalized_url in seen_urls:
                continue

            seen_urls.add(
                normalized_url
            )

            parsed_domain = (
                urlparse(url)
                .netloc
                .lower()
                .split(":")[0]
                .removeprefix("www.")
            )

            title = str(
                item.get("title")
                or "Untitled source"
            ).strip()

            snippet = str(
                item.get("content")
                or ""
            ).strip()

            raw_content = str(
                item.get("raw_content")
                or ""
            ).strip()

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    provider=self.name,
                    domain=parsed_domain,
                    published_at=(
                        self._parse_datetime(
                            item.get(
                                "published_date"
                            )
                        )
                    ),
                    content=(
                        raw_content
                        or snippet
                    ),
                )
            )

        return results

    @staticmethod
    def _choose_search_depth(
        query: str,
    ) -> str:
        configured = os.getenv(
            "TAVILY_SEARCH_DEPTH",
            "",
        ).strip().lower()

        if configured in {
            "basic",
            "advanced",
        }:
            return configured

        normalized = query.casefold()

        if any(
            hint in normalized
            for hint in CURRENT_QUERY_HINTS
        ):
            return "advanced"

        return "basic"

    @staticmethod
    def _choose_topic(
        query: str,
    ) -> str:
        configured = os.getenv(
            "TAVILY_TOPIC",
            "",
        ).strip().lower()

        if configured in {
            "general",
            "news",
        }:
            return configured

        normalized = query.casefold()

        if any(
            hint in normalized
            for hint in NEWS_QUERY_HINTS
        ):
            return "news"

        return "general"

    @staticmethod
    def _get_excluded_domains() -> list[str]:
        configured = os.getenv(
            "TAVILY_EXCLUDE_DOMAINS",
            "",
        ).strip()

        if configured:
            domains = [
                item.strip()
                for item in configured.split(",")
                if item.strip()
            ]

            return domains

        return list(
            DEFAULT_EXCLUDED_DOMAINS
        )

    @staticmethod
    def _parse_datetime(
        value: object,
    ) -> datetime | None:
        if not value:
            return None

        text = str(
            value
        ).strip()

        try:
            return datetime.fromisoformat(
                text.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None