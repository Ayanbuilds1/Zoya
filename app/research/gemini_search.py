from __future__ import annotations

import asyncio
import os
from dataclasses import fields
from urllib.parse import urlparse

from google import genai
from google.genai import types

from app.research.models import SearchResult
from app.research.provider import (
    ResearchProvider,
    ResearchProviderError,
    ResearchProviderUnavailable,
)


class GeminiGoogleSearchProvider(ResearchProvider):
    """Gemini Google Search grounding provider.

    Uses Gemini 3.6 Flash by default. The older research implementation in
    this project was still pointed at an obsolete model; current Google docs
    list gemini-3.6-flash as supporting Google Search grounding.
    """

    name = "gemini"
    REQUEST_TIMEOUT_SECONDS = 25.0

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv(
            "GEMINI_RESEARCH_MODEL",
            "gemini-3.6-flash",
        ).strip() or "gemini-3.6-flash"
        self.client = (
            genai.Client(api_key=self.api_key)
            if self.api_key
            else None
        )

    async def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        if not await self.is_available():
            raise ResearchProviderUnavailable(
                "GEMINI_API_KEY is not configured."
            )

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._search_sync,
                    query,
                    max_results,
                ),
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as error:
            raise ResearchProviderError(
                "Gemini Google Search timed out."
            ) from error
        except ResearchProviderError:
            raise
        except Exception as error:
            raise ResearchProviderError(
                f"Gemini Google Search failed: {error}"
            ) from error

    def _search_sync(
        self,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )

        print(
            f"🔎 [RESEARCH] Gemini Google Search: {query!r} "
            f"(model={self.model})"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=query,
            config=config,
        )

        candidate = None
        if getattr(response, "candidates", None):
            candidate = response.candidates[0]

        metadata = getattr(candidate, "grounding_metadata", None)
        if metadata is None:
            print("⚠️ [RESEARCH] Gemini returned no grounding metadata.")
            return []

        queries = getattr(metadata, "web_search_queries", None) or []
        real_queries = [str(item).strip() for item in queries if str(item).strip()]
        if real_queries:
            print(
                "🔎 [RESEARCH] Executed Google searches: "
                + " | ".join(real_queries)
            )
        else:
            print("⚠️ [RESEARCH] Gemini reported no executed search queries.")

        chunks = getattr(metadata, "grounding_chunks", None) or []
        supports = getattr(metadata, "grounding_supports", None) or []

        snippets_by_index: dict[int, list[str]] = {}
        for support in supports:
            segment = getattr(support, "segment", None)
            text = getattr(segment, "text", None) if segment else None
            if not text:
                continue
            for raw_index in (getattr(support, "grounding_chunk_indices", None) or []):
                try:
                    idx = int(raw_index)
                except (TypeError, ValueError):
                    continue
                snippets_by_index.setdefault(idx, []).append(str(text).strip())

        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        for index, chunk in enumerate(chunks):
            web = getattr(chunk, "web", None)
            url = getattr(web, "uri", None) if web else None
            if not url:
                continue
            url = str(url).strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = (
                getattr(web, "title", None) if web else None
            ) or "Web source"
            domain = urlparse(url).hostname or ""
            domain = domain.removeprefix("www.")
            snippet = " ".join(snippets_by_index.get(index, []))
            snippet = snippet[:700]

            results.append(
                self._make_search_result(
                    url=url,
                    title=str(title).strip(),
                    snippet=snippet,
                    domain=domain,
                    content=snippet,
                )
            )

            if len(results) >= max_results:
                break

        print(
            f"✅ [RESEARCH] Gemini returned {len(results)} grounded sources."
        )
        return results

    @staticmethod
    def _make_search_result(
        *,
        url: str,
        title: str,
        snippet: str,
        domain: str,
        content: str,
    ) -> SearchResult:
        """Build against both the current and older SearchResult schemas."""
        field_names = {field.name for field in fields(SearchResult)}
        values: dict[str, object] = {}

        for name, value in {
            "url": url,
            "title": title,
            "snippet": snippet,
            "content": content,
            "domain": domain,
            "provider": "gemini",
            "source": "gemini",
            "published_at": None,
            "published_date": None,
            "relevance_score": 0.7,
            "is_authoritative": False,
            "freshness_days": None,
            "covers_key_aspects": [],
        }.items():
            if name in field_names:
                values[name] = value

        return SearchResult(**values)
