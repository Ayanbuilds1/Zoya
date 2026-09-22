from __future__ import annotations

import asyncio
import os
import re
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from app.core.ai import create_ai_provider
from app.research.brave import BraveResearchProvider
from app.research.evidence import EvidenceEvaluator
from app.research.gemini_search import (
    GeminiGoogleSearchProvider,
)
from app.research.models import (
    EvidenceStatus,
    ResearchResult,
    SearchResult,
)
from app.research.provider import (
    ResearchProvider,
    ResearchProviderUnavailable,
)
from app.research.tavily import TavilyResearchProvider


ResearchEventEmitter = Callable[
    [str, dict],
    Awaitable[None],
]


async def _noop_emit(
    event_name: str,
    payload: dict,
) -> None:
    del event_name, payload


class ResearchOrchestrator:
    """
    Provider-independent web research orchestration.

    Research rules:
    - No minimum source requirement.
    - No target source count.
    - Hard maximum of 20 sources.
    - Search-call budget is separate from source count.
    - Provider failures fall through to another provider.
    - Irrelevant provider results are filtered before evidence evaluation.
    - Follow-up queries stay related to the original topic.
    - Research stops when evidence is sufficient.
    - Final AI receives selected evidence rather than the raw candidate pool.
    """

    HARD_MAX_SOURCES = 20

    INSTITUTIONAL_SUFFIXES = (
        ".gov",
        ".gov.in",
        ".nic.in",
        ".mil",
        ".edu",
        ".edu.in",
        ".ac.in",
        ".ac.uk",
        ".int",
    )

    HIGH_QUALITY_EDITORIAL_DOMAINS = {
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "bbc.co.uk",
        "ft.com",
        "wsj.com",
        "nytimes.com",
        "theguardian.com",
        "bloomberg.com",
        "forbes.com",
        "economist.com",
        "npr.org",
        "pbs.org",
        "abcnews.go.com",
        "cnbc.com",
        "washingtonpost.com",
        "time.com",
        "aljazeera.com",
        "dw.com",
        "indiatoday.in",
        "indianexpress.com",
        "thehindu.com",
        "hindustantimes.com",
        "timesofindia.indiatimes.com",
        "ndtv.com",
        "news18.com",
        "livemint.com",
        "moneycontrol.com",
    }

    UGC_AND_SOCIAL_DOMAINS = {
        "reddit.com",
        "quora.com",
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "instagram.com",
        "tiktok.com",
        "x.com",
        "twitter.com",
        "threads.net",
        "medium.com",
        "substack.com",
    }

    LOW_SIGNAL_PATH_WORDS = (
        "affiliate",
        "sponsored",
        "advertorial",
        "coupon",
        "deal",
        "shopping",
        "buy",
        "product",
    )

    def __init__(
        self,
        providers: list[ResearchProvider] | None = None,
        evaluator: EvidenceEvaluator | None = None,
        ai_provider=None,
        *,
        max_sources: int | None = None,
        max_searches: int | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.providers = (
            providers
            or self._providers_from_environment()
        )

        self.evaluator = (
            evaluator
            or EvidenceEvaluator()
        )

        self.ai_provider = (
            ai_provider
            if ai_provider is not None
            else self._create_optional_ai_provider()
        )

        configured_max_sources = int(
            max_sources
            if max_sources is not None
            else os.getenv(
                "RESEARCH_MAX_SOURCES",
                "20",
            )
        )

        self.max_sources = min(
            self.HARD_MAX_SOURCES,
            max(
                1,
                configured_max_sources,
            ),
        )

        self.max_searches = max(
            1,
            int(
                max_searches
                if max_searches is not None
                else os.getenv(
                    "RESEARCH_MAX_SEARCHES",
                    "10",
                )
            ),
        )

        self.timeout_seconds = max(
            1.0,
            float(
                timeout_seconds
                if timeout_seconds is not None
                else os.getenv(
                    "RESEARCH_TIMEOUT",
                    "30",
                )
            ),
        )

    # ================================================================
    # MAIN RESEARCH LOOP
    # ================================================================

    async def execute(
        self,
        query: str,
        *,
        emit: ResearchEventEmitter | None = None,
    ) -> ResearchResult:
        query = query.strip()

        if not query:
            raise ValueError(
                "Research query cannot be empty."
            )

        emit = emit or _noop_emit

        started = time.monotonic()

        await emit(
            "research_start",
            {},
        )

        sources: list[
            SearchResult
        ] = []

        providers_used: list[str] = []

        search_queries: list[str] = []

        attempted: set[
            tuple[str, str]
        ] = set()

        current_queries = [
            query
        ]

        last_status = EvidenceStatus(
            sufficient=False,
            reason=(
                "Research has not started."
            ),
        )

        while True:
            # ----------------------------------------------------------
            # GLOBAL SAFETY BUDGETS
            # ----------------------------------------------------------

            if self._timed_out(
                started
            ):
                last_status = EvidenceStatus(
                    sufficient=False,
                    reason=(
                        "Research time budget exhausted."
                    ),
                    gaps=[
                        "The research time budget ended before "
                        "all requested evidence could be collected."
                    ],
                    next_queries=[],
                    key_findings=[],
                    conflicts=[],
                )
                break

            if len(sources) >= self.max_sources:
                last_status = EvidenceStatus(
                    sufficient=False,
                    reason=(
                        "The absolute research source safety ceiling "
                        "was reached before additional evidence could "
                        "be collected."
                    ),
                    gaps=[
                        "Research stopped at the hard safety ceiling."
                    ],
                    next_queries=[],
                    key_findings=[],
                    conflicts=[],
                )
                break

            if (
                len(search_queries)
                >= self.max_searches
            ):
                last_status = EvidenceStatus(
                    sufficient=False,
                    reason=(
                        "The maximum research search-call budget "
                        "was reached."
                    ),
                    gaps=[
                        "Additional searches were limited by the "
                        "configured search budget."
                    ],
                    next_queries=[],
                    key_findings=[],
                    conflicts=[],
                )
                break

            if not current_queries:
                last_status = EvidenceStatus(
                    sufficient=bool(
                        sources
                    ),
                    reason=(
                        "No additional relevant research queries "
                        "remain."
                    ),
                    gaps=[],
                    next_queries=[],
                    key_findings=[],
                    conflicts=[],
                )
                break

            search_query = (
                current_queries
                .pop(0)
                .strip()
            )

            if not search_query:
                continue

            # ----------------------------------------------------------
            # PROVIDER SELECTION
            # ----------------------------------------------------------

            provider = await self._select_untried_provider(
                query=search_query,
                attempted=attempted,
            )

            if provider is None:
                last_status = EvidenceStatus(
                    sufficient=False,
                    reason=(
                        "All configured research providers were "
                        "already attempted or unavailable."
                    ),
                    gaps=[
                        "No additional provider was available "
                        "for more corroboration."
                    ],
                    next_queries=[],
                    key_findings=[],
                    conflicts=[],
                )
                break

            attempt_key = (
                provider.name,
                search_query.casefold(),
            )

            attempted.add(
                attempt_key
            )

            search_queries.append(
                search_query
            )

            await emit(
                "research_query",
                {
                    "query": search_query,
                    "provider": provider.name,
                },
            )

            # ----------------------------------------------------------
            # SEARCH
            # ----------------------------------------------------------

            try:
                remaining_seconds = max(
                    1.0,
                    self.timeout_seconds
                    - (
                        time.monotonic()
                        - started
                    ),
                )

                provider_results = (
                    await asyncio.wait_for(
                        provider.search(
                            search_query,
                            max_results=min(
                                10,
                                self.max_sources
                                - len(sources),
                            ),
                        ),
                        timeout=remaining_seconds,
                    )
                )

            except ResearchProviderUnavailable as error:
                await emit(
                    "research_analyzing",
                    {
                        "status": "provider_error",
                        "provider": provider.name,
                        "message": str(error),
                    },
                )

                self._requeue_same_query_if_possible(
                    current_queries,
                    search_query,
                )

                continue

            except asyncio.TimeoutError:
                await emit(
                    "research_analyzing",
                    {
                        "status": "provider_error",
                        "provider": provider.name,
                        "message": (
                            "Provider search timed out."
                        ),
                    },
                )

                self._requeue_same_query_if_possible(
                    current_queries,
                    search_query,
                )

                continue

            except Exception as error:
                await emit(
                    "research_analyzing",
                    {
                        "status": "provider_error",
                        "provider": provider.name,
                        "message": str(error),
                    },
                )

                self._requeue_same_query_if_possible(
                    current_queries,
                    search_query,
                )

                continue

            # ----------------------------------------------------------
            # FILTER NEW CANDIDATES
            # ----------------------------------------------------------

            filtered_results = (
                self.evaluator.filter_sources(
                    search_query,
                    provider_results,
                )
            )

            if not filtered_results:
                await emit(
                    "research_analyzing",
                    {
                        "status": "no_relevant_sources",
                        "provider": provider.name,
                        "current_count": len(
                            sources
                        ),
                    },
                )

                self._requeue_same_query_if_possible(
                    current_queries,
                    search_query,
                )

                continue

            if provider.name not in providers_used:
                providers_used.append(
                    provider.name
                )

            # ----------------------------------------------------------
            # MERGE + RANK
            # ----------------------------------------------------------

            sources = self._merge_sources(
                sources,
                filtered_results,
            )

            sources = self._rank_sources(
                query=query,
                sources=sources,
            )

            await emit(
                "research_analyzing",
                {
                    "current_count": len(
                        sources
                    ),
                    "status": "evaluating",
                },
            )

            # ----------------------------------------------------------
            # IMPORTANT:
            #
            # Always evaluate against the ORIGINAL USER QUESTION,
            # not merely the latest follow-up search query.
            #
            # This prevents a follow-up such as:
            # "female Bollywood superstars"
            #
            # from causing the evaluator to forget that the original
            # question also asked about the male side.
            # ----------------------------------------------------------

            last_status = (
                await self.evaluator.evaluate(
                    query,
                    sources,
                    ai_provider=self.ai_provider,
                )
            )

            # ----------------------------------------------------------
            # DETERMINISTIC EARLY STOP
            #
            # This is deliberately separate from source COUNT.
            #
            # It asks:
            # "Do we already have enough useful independent evidence?"
            #
            # rather than:
            # "Have we collected N sources?"
            # ----------------------------------------------------------

            if self._research_evidence_is_sufficient(
                query=query,
                sources=sources,
                evaluator_status=last_status,
            ):
                last_status = EvidenceStatus(
                    sufficient=True,
                    reason=(
                        "Evidence now covers the material scope of "
                        "the question with sufficient source quality "
                        "and independent corroboration."
                    ),
                    gaps=[],
                    next_queries=[],
                    key_findings=(
                        last_status.key_findings
                    ),
                    conflicts=(
                        last_status.conflicts
                    ),
                )

                await emit(
                    "research_analyzing",
                    {
                        "current_count": len(
                            sources
                        ),
                        "status": "stopping",
                    },
                )

                break

            # ----------------------------------------------------------
            # FOLLOW-UP QUERY GENERATION
            # ----------------------------------------------------------

            next_queries = (
                self._clean_follow_up_queries(
                    original_query=query,
                    current_query=search_query,
                    next_queries=(
                        last_status.next_queries
                    ),
                )
            )

            for next_query in next_queries:
                if next_query.casefold() not in {
                    item.casefold()
                    for item in current_queries
                }:
                    current_queries.append(
                        next_query
                    )

            # If evidence is not sufficient and no targeted query was
            # generated, try the same research question through another
            # provider, provided one remains.
            if (
                not next_queries
                and self._has_untried_provider(
                    query=search_query,
                    attempted=attempted,
                )
            ):
                current_queries.insert(
                    0,
                    search_query,
                )

            await emit(
                "research_analyzing",
                {
                    "current_count": len(
                        sources
                    ),
                    "status": (
                        "continuing"
                        if current_queries
                        else "stopping"
                    ),
                },
            )

        duration = (
            time.monotonic()
            - started
        )

        # --------------------------------------------------------------
        # FINAL EVIDENCE SELECTION
        #
        # No fixed target source count.
        #
        # max_sources remains only the absolute safety ceiling.
        # --------------------------------------------------------------

        final_sources = (
            self.evaluator.select_best_sources(
                query=query,
                sources=sources,
                max_selected=None,
            )
        )

        if not final_sources and sources:
            final_sources = (
                self._rank_sources(
                    query=query,
                    sources=sources,
                )[:1]
            )

        # Never expose the raw search candidate pool as final evidence.
        for source_index, source in enumerate(
            final_sources,
            start=1,
        ):
            await emit(
                "research_sources",
                {
                    "source_index": source_index,
                    "url": source.url,
                    "title": source.title,
                    "snippet": (
                        source.snippet[:500]
                    ),
                    "domain": source.domain,
                    "freshness": (
                        source.published_at.isoformat()
                        if source.published_at
                        else None
                    ),
                },
            )

        # --------------------------------------------------------------
        # Build tightly controlled evidence context for final AI.
        # --------------------------------------------------------------

        evidence_context = (
            self._build_evidence_context(
                query=query,
                sources=final_sources,
                status=last_status,
            )
        )

        result = ResearchResult(
            query=query,
            sources=final_sources,
            evidence_status=last_status,
            providers_used=providers_used,
            search_count=len(
                search_queries
            ),
            research_duration=duration,
            evidence_context=evidence_context,
            search_queries=search_queries,
        )

        await emit(
            "research_complete",
            {
                "total_sources": len(
                    result.sources
                ),
                "providers_used": (
                    providers_used
                ),
                "evidence_status": (
                    "sufficient"
                    if last_status.sufficient
                    else "incomplete"
                ),
            },
        )

        return result

    # ================================================================
    # EVIDENCE STOPPING
    # ================================================================

    def _research_evidence_is_sufficient(
        self,
        *,
        query: str,
        sources: list[SearchResult],
        evaluator_status: EvidenceStatus,
    ) -> bool:
        """
        Decide whether searching can stop.

        This does NOT use a fixed source count.

        It considers:
        - evaluator's evidence decision
        - question dimensions
        - independent domains
        - source strength
        - broadness of the request
        """

        if not sources:
            return False

        selected = (
            self.evaluator.select_best_sources(
                query=query,
                sources=sources,
                max_selected=None,
            )
        )

        if not selected:
            return False

        dimensions = set()

        try:
            dimensions = (
                self.evaluator._query_dimensions(
                    query
                )
            )
        except Exception:
            dimensions = set()

        covered_dimensions = set()

        try:
            covered_dimensions = (
                self.evaluator._covered_dimensions(
                    selected,
                    dimensions,
                )
            )
        except Exception:
            covered_dimensions = set()

        coverage_complete = (
            not dimensions
            or dimensions.issubset(
                covered_dimensions
            )
        )

        strong_sources = []

        for source in selected:
            try:
                strength = (
                    self.evaluator._source_strength(
                        source
                    )
                )
            except Exception:
                strength = 0.0

            if strength >= 0.78:
                strong_sources.append(
                    source
                )

        strong_domains = {
            source.domain
            for source in strong_sources
            if source.domain
        }

        independent_corroboration = (
            len(
                strong_domains
            ) >= 2
        )

        try:
            broad_scope = (
                self.evaluator._is_broad_scope_query(
                    query
                )
            )
        except Exception:
            broad_scope = False

        # An explicit evaluator sufficiency decision is respected only
        # when material coverage is also complete.
        if (
            evaluator_status.sufficient
            and coverage_complete
        ):
            return True

        # Strong evidence with complete coverage can stop even when the
        # generic evaluator was conservative.
        if coverage_complete:
            if independent_corroboration:
                return True

            # For a narrow factual question, one exceptionally strong
            # source can be enough.
            if (
                not broad_scope
                and any(
                    self._safe_source_strength(
                        source
                    ) >= 0.92
                    for source in selected
                )
            ):
                return True

        return False

    def _safe_source_strength(
        self,
        source: SearchResult,
    ) -> float:
        try:
            return float(
                self.evaluator._source_strength(
                    source
                )
            )
        except Exception:
            return 0.0

    # ================================================================
    # PROVIDER SELECTION
    # ================================================================

    async def _select_untried_provider(
        self,
        *,
        query: str,
        attempted: set[
            tuple[str, str]
        ],
    ) -> ResearchProvider | None:
        normalized_query = (
            query.casefold()
        )

        for provider in self.providers:
            if (
                provider.name,
                normalized_query,
            ) in attempted:
                continue

            try:
                available = await provider.is_available()
            except Exception:
                available = False

            if available:
                return provider

        return None

    async def _provider_available(
        self,
        provider: ResearchProvider,
    ) -> bool:
        try:
            return await provider.is_available()
        except Exception:
            return False

    def _has_untried_provider(
        self,
        *,
        query: str,
        attempted: set[
            tuple[str, str]
        ],
    ) -> bool:
        normalized_query = (
            query.casefold()
        )

        return any(
            (
                provider.name,
                normalized_query,
            )
            not in attempted
            for provider in self.providers
        )

    @staticmethod
    def _requeue_same_query_if_possible(
        current_queries: list[str],
        query: str,
    ) -> None:
        query_key = query.casefold()

        if not any(
            queued.casefold() == query_key
            for queued in current_queries
        ):
            current_queries.insert(
                0,
                query,
            )

    # ================================================================
    # SOURCE QUALITY / RANKING
    # ================================================================

    @classmethod
    def _rank_sources(
        cls,
        *,
        query: str,
        sources: list[SearchResult],
    ) -> list[SearchResult]:
        ranked: list[
            tuple[
                tuple[
                    float,
                    float,
                    float,
                    float,
                    float,
                ],
                SearchResult,
            ]
        ] = []

        for source in sources:
            quality_score = (
                cls._domain_quality_score(
                    source.domain
                )
            )

            relevance_score = (
                cls._safe_relevance_score(
                    source
                )
            )

            topical_score = (
                cls._topical_overlap_score(
                    query=query,
                    source=source,
                )
            )

            content_score = (
                cls._content_quality_score(
                    source
                )
            )

            path_penalty = (
                cls._low_signal_path_penalty(
                    source
                )
            )

            final_quality = max(
                0.0,
                quality_score
                - path_penalty,
            )

            ranked.append(
                (
                    (
                        final_quality,
                        topical_score,
                        relevance_score,
                        content_score,
                        -path_penalty,
                    ),
                    source,
                )
            )

        ranked.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            source
            for _, source in ranked
        ]

    @classmethod
    def _domain_quality_score(
        cls,
        domain: str,
    ) -> float:
        host = (
            domain
            or ""
        ).strip().lower()

        host = (
            host.removeprefix("www.")
        )

        if not host:
            return 0.35

        if host.endswith(
            cls.INSTITUTIONAL_SUFFIXES
        ):
            return 1.00

        if host in cls.HIGH_QUALITY_EDITORIAL_DOMAINS:
            return 0.88

        if host in cls.UGC_AND_SOCIAL_DOMAINS:
            return 0.28

        if any(
            marker in host
            for marker in (
                "feed",
                "aggregator",
                "syndication",
            )
        ):
            return 0.35

        return 0.58

    @staticmethod
    def _safe_relevance_score(
        source: SearchResult,
    ) -> float:
        value = getattr(
            source,
            "relevance_score",
            0.5,
        )

        try:
            value = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.5

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )

    @staticmethod
    def _topical_overlap_score(
        *,
        query: str,
        source: SearchResult,
    ) -> float:
        query_terms = (
            ResearchOrchestrator._query_terms(
                query
            )
        )

        if not query_terms:
            return 0.0

        source_text = " ".join(
            [
                getattr(
                    source,
                    "title",
                    "",
                )
                or "",
                getattr(
                    source,
                    "snippet",
                    "",
                )
                or "",
                getattr(
                    source,
                    "content",
                    "",
                )
                or "",
            ]
        ).casefold()

        if not source_text:
            return 0.0

        matched = sum(
            1
            for term in query_terms
            if term in source_text
        )

        return min(
            1.0,
            matched
            / max(
                1,
                min(
                    len(query_terms),
                    8,
                ),
            ),
        )

    @staticmethod
    def _content_quality_score(
        source: SearchResult,
    ) -> float:
        content = (
            getattr(
                source,
                "content",
                "",
            )
            or ""
        ).strip()

        snippet = (
            getattr(
                source,
                "snippet",
                "",
            )
            or ""
        ).strip()

        if len(content) >= 1200:
            return 1.0

        if len(content) >= 600:
            return 0.85

        if len(content) >= 250:
            return 0.70

        if len(snippet) >= 200:
            return 0.50

        if snippet:
            return 0.35

        return 0.10

    @classmethod
    def _low_signal_path_penalty(
        cls,
        source: SearchResult,
    ) -> float:
        url = (
            getattr(
                source,
                "url",
                "",
            )
            or ""
        ).casefold()

        if not url:
            return 0.0

        matches = sum(
            1
            for word in cls.LOW_SIGNAL_PATH_WORDS
            if word in url
        )

        return min(
            0.20,
            matches * 0.05,
        )

    # ================================================================
    # QUERY CLEANING
    # ================================================================

    @staticmethod
    def _query_terms(
        query: str,
    ) -> set[str]:
        stop_words = {
            "what",
            "when",
            "where",
            "which",
            "who",
            "how",
            "why",
            "latest",
            "current",
            "recent",
            "today",
            "now",
            "this",
            "that",
            "these",
            "those",
            "about",
            "with",
            "into",
            "from",
            "for",
            "and",
            "the",
            "are",
            "was",
            "were",
            "have",
            "has",
            "had",
            "can",
            "could",
            "would",
            "should",
            "will",
            "mein",
            "kya",
            "ka",
            "ke",
            "ki",
            "ko",
            "se",
            "par",
            "hai",
            "hain",
            "ho",
            "rahe",
            "wala",
            "wali",
            "wale",
            "mujhe",
            "batao",
            "bata",
            "karo",
            "kar",
            "tha",
            "thi",
            "the",
            "yeh",
            "ye",
            "woh",
            "wahi",
        }

        return {
            token.casefold()
            for token in re.findall(
                r"[A-Za-z0-9]{3,}",
                query,
            )
            if token.casefold()
            not in stop_words
        }

    @classmethod
    def _clean_follow_up_queries(
        cls,
        *,
        original_query: str,
        current_query: str,
        next_queries: list[str],
    ) -> list[str]:
        original_terms = cls._query_terms(
            original_query
        )

        current_terms = cls._query_terms(
            current_query
        )

        combined_terms = (
            original_terms
            | current_terms
        )

        clean: list[str] = []

        for item in next_queries:
            candidate = item.strip()

            if not candidate:
                continue

            candidate_terms = cls._query_terms(
                candidate
            )

            if not candidate_terms:
                continue

            overlap = (
                candidate_terms
                & combined_terms
            )

            if not overlap:
                continue

            clean.append(
                candidate
            )

        return clean[:3]

    # ================================================================
    # GENERAL HELPERS
    # ================================================================

    def _timed_out(
        self,
        started: float,
    ) -> bool:
        return (
            time.monotonic()
            - started
        ) >= self.timeout_seconds

    @staticmethod
    def _merge_sources(
        existing: list[SearchResult],
        incoming: list[SearchResult],
    ) -> list[SearchResult]:
        merged = list(
            existing
        )

        seen_urls = {
            source.url.rstrip("/")
            .casefold()
            for source in existing
            if getattr(
                source,
                "url",
                None,
            )
        }

        for source in incoming:
            normalized_url = (
                (
                    source.url
                    or ""
                )
                .rstrip("/")
                .casefold()
            )

            if (
                not normalized_url
                or normalized_url
                in seen_urls
            ):
                continue

            if not getattr(
                source,
                "domain",
                None,
            ):
                source.domain = (
                    urlparse(
                        source.url
                    ).netloc.lower()
                )

            seen_urls.add(
                normalized_url
            )

            merged.append(
                source
            )

        return merged

    @classmethod
    def _build_evidence_context(
        cls,
        *,
        query: str,
        sources: list[SearchResult],
        status: EvidenceStatus,
    ) -> str:
        lines = [
            "WEB RESEARCH EVIDENCE",
            f"User question: {query}",
            "",
            "CRITICAL SYNTHESIS RULES",
            (
                "Use only the evidence below for externally verifiable "
                "claims."
            ),
            (
                "Do not invent facts, sources, dates, numbers, rankings, "
                "recognition, or other unsupported details."
            ),
            (
                "Do NOT say 'no source was found', 'there is no source', "
                "or similar wording unless the research result contains "
                "zero usable sources AND the research assessment explicitly "
                "states that no relevant evidence was returned."
            ),
            (
                "If a specific claim is not established by the collected "
                "evidence, say that the available evidence does not "
                "directly establish that claim."
            ),
            (
                "Do not convert 'the sources do not establish X' into "
                "'X does not exist' or 'no source exists'."
            ),
            (
                "Do not infer that a source is missing merely because "
                "it does not use the exact word used by the user."
            ),
            (
                "For subjective labels such as 'superstar', explain the "
                "observable criteria used by the sources and avoid "
                "presenting the label as an objective official ranking "
                "unless a source explicitly establishes one."
            ),
            (
                "When multiple source claims disagree, describe the "
                "disagreement instead of silently merging them."
            ),
            (
                "Cite claims to the actual sources that support them."
            ),
            "",
            "SOURCE HANDLING RULES",
            (
                "- Prefer primary/official or institutional sources "
                "for factual claims when available."
            ),
            (
                "- Prefer established editorial sources when primary "
                "sources are unavailable."
            ),
            (
                "- Treat social media, forums, and user-generated "
                "sources as supporting evidence rather than the main "
                "factual backbone."
            ),
            "",
        ]

        for index, source in enumerate(
            sources,
            start=1,
        ):
            quality_label = (
                cls._source_quality_label(
                    source.domain
                )
            )

            content = (
                getattr(
                    source,
                    "content",
                    "",
                )
                or getattr(
                    source,
                    "snippet",
                    "",
                )
                or ""
            ).strip()

            content = content[:700]

            lines.extend(
                [
                    f"SOURCE {index}",
                    f"Quality class: {quality_label}",
                    f"Title: {source.title}",
                    f"URL: {source.url}",
                    f"Domain: {source.domain}",
                    f"Provider: {source.provider}",
                    f"Evidence: {content}",
                    "",
                ]
            )

        lines.extend(
            [
                "RESEARCH ASSESSMENT",
                f"Sufficient: {status.sufficient}",
                f"Reason: {status.reason}",
            ]
        )

        if status.gaps:
            lines.append(
                "Gaps: "
                + "; ".join(
                    status.gaps
                )
            )

        if status.conflicts:
            lines.append(
                "Conflicts: "
                + "; ".join(
                    status.conflicts
                )
            )

        return "\n".join(
            lines
        )

    @classmethod
    def _source_quality_label(
        cls,
        domain: str,
    ) -> str:
        score = cls._domain_quality_score(
            domain
        )

        if score >= 0.95:
            return "institutional / official"

        if score >= 0.84:
            return "established editorial"

        if score <= 0.30:
            return "user-generated / social"

        return "general web source"

    # ================================================================
    # PROVIDER CONSTRUCTION
    # ================================================================

    @staticmethod
    def _providers_from_environment() -> list[
        ResearchProvider
    ]:
        provider_names = [
            item.strip().lower()
            for item in os.getenv(
                "RESEARCH_PROVIDERS",
                "gemini,tavily,brave",
            ).split(",")
            if item.strip()
        ]

        providers: list[
            ResearchProvider
        ] = []

        seen: set[str] = set()

        for name in provider_names:
            if name in seen:
                continue

            seen.add(
                name
            )

            if name in {
                "gemini",
                "gemini_search",
            }:
                providers.append(
                    GeminiGoogleSearchProvider()
                )

            elif name == "tavily":
                providers.append(
                    TavilyResearchProvider()
                )

            elif name == "brave":
                providers.append(
                    BraveResearchProvider()
                )

        return providers

    @staticmethod
    def _create_optional_ai_provider():
        try:
            return create_ai_provider()
        except Exception:
            return None