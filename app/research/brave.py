from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from app.research.models import SearchResult
from app.research.provider import (
    ResearchProvider,
    ResearchProviderError,
    ResearchProviderUnavailable,
)


class BraveResearchProvider(ResearchProvider):
    """Brave Search API adapter."""

    name = "brave"
    endpoint = (
        "https://api.search.brave.com/"
        "res/v1/web/search"
    )

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("BRAVE_API_KEY", "").strip()
        )
        self.timeout = timeout

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[SearchResult]:
        if not self.api_key:
            raise ResearchProviderUnavailable(
                "Brave Search API key is not configured."
            )

        count = max(
            1,
            min(max_results, 20),
        )

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }

        params = {
            "q": query,
            "count": count,
        }

        search_lang = os.getenv(
            "BRAVE_SEARCH_LANG",
            "",
        ).strip()

        country = os.getenv(
            "BRAVE_COUNTRY",
            "",
        ).strip()

        if search_lang:
            params["search_lang"] = search_lang

        if country:
            params["country"] = country

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:
                response = await client.get(
                    self.endpoint,
                    headers=headers,
                    params=params,
                )

            response.raise_for_status()
            data = response.json()

        except httpx.HTTPStatusError as error:
            raise ResearchProviderError(
                f"Brave returned HTTP "
                f"{error.response.status_code}."
            ) from error

        except (httpx.HTTPError, ValueError) as error:
            raise ResearchProviderError(
                f"Brave request failed: {error}"
            ) from error

        results: list[SearchResult] = []

        web_results = (
            data.get("web", {})
            .get("results", [])
        )

        for item in web_results:
            url = str(
                item.get("url") or ""
            ).strip()

            if not url:
                continue

            domain = urlparse(url).netloc.lower()

            snippet_parts: list[str] = []

            description = str(
                item.get("description")
                or ""
            ).strip()

            if description:
                snippet_parts.append(
                    description
                )

            for extra in (
                item.get("extra_snippets", [])
                or []
            ):
                text = str(extra).strip()

                if text:
                    snippet_parts.append(text)

            results.append(
                SearchResult(
                    title=str(
                        item.get("title")
                        or "Untitled source"
                    ),
                    url=url,
                    snippet=" ".join(
                        snippet_parts
                    ),
                    provider=self.name,
                    domain=domain,
                    content=" ".join(
                        snippet_parts
                    ),
                )
            )

        return results