from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
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
    """
    Gemini provider using Google's built-in Google Search grounding.

    Extracts grounded web sources from Gemini response metadata.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv(
                "GEMINI_API_KEY",
                "",
            ).strip()
        )

        self.model = (
            model
            or os.getenv(
                "GEMINI_RESEARCH_MODEL",
                "",
            ).strip()
            or os.getenv(
                "GEMINI_MODEL",
                "",
            ).strip()
            or "gemini-2.5-flash"
        )

        self._client = (
            genai.Client(
                api_key=self.api_key,
            )
            if self.api_key
            else None
        )

    async def is_available(self) -> bool:
        return self._client is not None

    async def search(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[SearchResult]:
        if self._client is None:
            raise ResearchProviderUnavailable(
                "Gemini API key is not configured."
            )

        max_results = max(
            1,
            min(
                20,
                int(max_results),
            ),
        )

        config = types.GenerateContentConfig(
            tools=[
                types.Tool(
                    google_search=types.GoogleSearch()
                )
            ]
        )

        prompt = (
            "You are a web research agent.\n"
            "Use Google Search to research the user's question "
            "with current web information.\n"
            "Prefer authoritative and recent sources.\n"
            "Do not invent sources or URLs.\n"
            "Return a concise factual research summary.\n\n"
            f"User question:\n{query}"
        )

        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=self.model,
                contents=prompt,
                config=config,
            )

        except Exception as error:
            raise ResearchProviderError(
                f"Gemini Google Search failed: {error}"
            ) from error

        results = self._extract_grounding_sources(
            response=response,
            max_results=max_results,
        )

        if not results:
            print(
                "\n⚠️ Gemini returned no grounded web sources."
            )

            self._print_grounding_diagnostics(
                response
            )

        return results

    @classmethod
    def _extract_grounding_sources(
        cls,
        response,
        max_results: int,
    ) -> list[SearchResult]:
        candidates = cls._read(
            response,
            "candidates",
            default=[],
        )

        if not candidates:
            return []

        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        for candidate in candidates:
            grounding_metadata = cls._read(
                candidate,
                "grounding_metadata",
                default=None,
            )

            if grounding_metadata is None:
                continue

            grounding_chunks = cls._read(
                grounding_metadata,
                "grounding_chunks",
                default=[],
            )

            grounding_supports = cls._read(
                grounding_metadata,
                "grounding_supports",
                default=[],
            )

            support_snippets = (
                cls._build_support_snippets(
                    grounding_supports
                )
            )

            response_text = cls._read(
                response,
                "text",
                default="",
            )

            response_text = str(
                response_text or ""
            ).strip()

            for chunk_index, chunk in enumerate(
                grounding_chunks
            ):
                web_chunk = cls._read(
                    chunk,
                    "web",
                    default=None,
                )

                if web_chunk is None:
                    continue

                url = cls._read(
                    web_chunk,
                    "uri",
                    default="",
                )

                title = cls._read(
                    web_chunk,
                    "title",
                    default="Untitled source",
                )

                domain = cls._read(
                    web_chunk,
                    "domain",
                    default="",
                )

                url = str(
                    url or ""
                ).strip()

                title = str(
                    title or "Untitled source"
                ).strip()

                domain = str(
                    domain or ""
                ).strip().lower()

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

                if not domain:
                    domain = (
                        urlparse(
                            url
                        ).netloc.lower()
                    )

                snippet = (
                    support_snippets.get(
                        chunk_index,
                        "",
                    ).strip()
                )

                if not snippet:
                    snippet = response_text[
                        :1200
                    ]

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet[:1200],
                        provider=self.name,
                        domain=domain,
                        content=(
                            snippet
                            or response_text
                        ),
                    )
                )

                if len(results) >= max_results:
                    return results

        return results

    @classmethod
    def _build_support_snippets(
        cls,
        grounding_supports,
    ) -> dict[int, str]:
        snippets: dict[int, list[str]] = {}

        for support in grounding_supports:
            indices = cls._read(
                support,
                "grounding_chunk_indices",
                default=[],
            )

            if not indices:
                indices = cls._read(
                    support,
                    "groundingChunkIndices",
                    default=[],
                )

            segment = cls._read(
                support,
                "segment",
                default=None,
            )

            text = ""

            if segment is not None:
                text = cls._read(
                    segment,
                    "text",
                    default="",
                )

            text = str(
                text or ""
            ).strip()

            if not text:
                continue

            for index in indices:
                try:
                    numeric_index = int(
                        index
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                snippets.setdefault(
                    numeric_index,
                    [],
                ).append(text)

        return {
            index: " ".join(
                parts
            )[:1600]
            for index, parts
            in snippets.items()
        }

    @staticmethod
    def _read(
        value,
        key: str,
        default=None,
    ):
        """
        Support both object-style and dictionary-style
        response representations.
        """
        if value is None:
            return default

        if isinstance(
            value,
            Mapping,
        ):
            if key in value:
                return value[key]

            camel_key = (
                key.split("_")[0]
                + "".join(
                    part.capitalize()
                    for part
                    in key.split("_")[1:]
                )
            )

            if camel_key in value:
                return value[
                    camel_key
                ]

            return default

        result = getattr(
            value,
            key,
            None,
        )

        if result is not None:
            return result

        camel_key = (
            key.split("_")[0]
            + "".join(
                part.capitalize()
                for part
                in key.split("_")[1:]
            )
        )

        return getattr(
            value,
            camel_key,
            default,
        )

    @classmethod
    def _print_grounding_diagnostics(
        cls,
        response,
    ) -> None:
        try:
            candidates = cls._read(
                response,
                "candidates",
                default=[],
            )

            print(
                f"Gemini candidates: {len(candidates)}"
            )

            for index, candidate in enumerate(
                candidates[:3]
            ):
                metadata = cls._read(
                    candidate,
                    "grounding_metadata",
                    default=None,
                )

                if metadata is None:
                    print(
                        f"Candidate {index}: "
                        "no grounding_metadata"
                    )
                    continue

                chunks = cls._read(
                    metadata,
                    "grounding_chunks",
                    default=[],
                )

                queries = cls._read(
                    metadata,
                    "web_search_queries",
                    default=[],
                )

                print(
                    f"Candidate {index}: "
                    f"{len(chunks)} grounding chunks"
                )

                if queries:
                    print(
                        "Google search queries:"
                    )

                    for search_query in queries:
                        print(
                            f"  - {search_query}"
                        )

        except Exception as error:
            print(
                "Gemini grounding diagnostics failed:"
            )
            print(
                f"{type(error).__name__}: {error}"
            )