from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from urllib.parse import urlparse

from app.research.models import (
    EvidenceStatus,
    SearchResult,
)


AUTHORITATIVE_DOMAIN_SUFFIXES = (
    ".gov",
    ".gov.in",
    ".gov.uk",
    ".gov.au",
    ".edu",
    ".edu.in",
    ".ac.uk",
    ".ac.in",
)


AUTHORITATIVE_DOMAINS = {
    "who.int",
    "un.org",
    "rbi.org.in",
    "nasa.gov",
    "python.org",
    "developer.mozilla.org",
    "w3.org",
    "ietf.org",
    "github.com",
    "openai.com",
    "anthropic.com",
    "google.com",
    "googleblog.com",
    "blog.google",
    "microsoft.com",
    "news.microsoft.com",
    "apple.com",
    "meta.com",
    "nvidia.com",
    "deepmind.google",
    "aws.amazon.com",
    "worldbank.org",
}


FIRST_PARTY_DOMAINS = {
    "openai.com",
    "anthropic.com",
    "google.com",
    "blog.google",
    "deepmind.google",
    "microsoft.com",
    "news.microsoft.com",
    "apple.com",
    "meta.com",
    "nvidia.com",
    "amazon.com",
    "aws.amazon.com",
    "github.com",
}


STRONG_EDITORIAL_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "nytimes.com",
    "theguardian.com",
    "washingtonpost.com",
    "ft.com",
    "wsj.com",
    "bloomberg.com",
    "forbes.com",
    "time.com",
    "npr.org",
    "pbs.org",
    "abcnews.go.com",
    "cnbc.com",
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
    "variety.com",
    "hollywoodreporter.com",
    "deadline.com",
}


DATABASE_LIKE_DOMAINS = {
    "imdb.com",
    "boxofficeindia.com",
    "boxofficemojo.com",
}


LOW_VALUE_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "reddit.com",
    "quora.com",
    "linkedin.com",
}


LOW_VALUE_PATH_HINTS = (
    "/profile/",
    "/profiles/",
    "/people/",
    "/person/",
    "/jobs/",
    "/careers/",
    "/directory/",
    "/contact/",
    "/tag/",
    "/category/",
)


STOP_WORDS = {
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
    "in",
    "my",
    "our",
    "their",
    "mein",
    "me",
    "mujhe",
    "batao",
    "bata",
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
    "chal",
    "the",
    "tha",
    "thi",
    "yeh",
    "ye",
    "wahi",
    "woh",
}


# Generic semantic dimensions.
# These are not topic-specific rules; they help detect whether
# a question asks for multiple sides/aspects.
DIMENSION_GROUPS = (
    ("male", "female"),
    ("men", "women"),
    ("actor", "actress"),
    ("actors", "actresses"),
    ("pros", "cons"),
    ("advantages", "disadvantages"),
    ("benefits", "drawbacks"),
    ("causes", "effects"),
    ("short term", "long term"),
    ("beginner", "advanced"),
)


class EvidenceEvaluator:
    """
    Evidence evaluator for research stopping and source quality.

    There is no fixed minimum source count and no target source count.

    Evaluation considers:
    - relevance
    - source quality
    - independent-domain diversity
    - coverage of material dimensions
    - strength of supporting evidence

    The class also exposes select_best_sources() so the orchestrator
    can keep the final evidence context compact instead of passing every
    search candidate to the final AI model.
    """

    MAX_EVALUATION_CONTEXT_CHARS = 6000
    MAX_SOURCE_CONTENT_CHARS = 600

    async def evaluate(
        self,
        query: str,
        sources: list[SearchResult],
        ai_provider=None,
    ) -> EvidenceStatus:
        filtered_sources = self.filter_sources(
            query,
            sources,
        )

        if not filtered_sources:
            return self._insufficient_status(
                query=query,
                reason=(
                    "No sufficiently relevant sources were returned."
                ),
                gaps=[
                    "Need more directly relevant sources."
                ],
            )

        heuristic = self._heuristic_evaluation(
            query,
            filtered_sources,
        )

        if heuristic.sufficient:
            return heuristic

        if ai_provider is None:
            return heuristic

        prompt = self._build_evaluation_prompt(
            query,
            filtered_sources,
        )

        try:
            raw = await asyncio.to_thread(
                ai_provider.send_message,
                prompt,
            )

            parsed = self._parse_json(
                raw
            )

            if isinstance(parsed, dict):
                return self._status_from_ai(
                    query=query,
                    parsed=parsed,
                    fallback=heuristic,
                )

        except Exception as error:
            print(
                "⚠️ Evidence AI evaluation failed."
            )
            print(
                f"Error type: {type(error).__name__}"
            )
            print(
                f"Error message: {error}"
            )

        return heuristic

    @classmethod
    def filter_sources(
        cls,
        query: str,
        sources: Iterable[SearchResult],
    ) -> list[SearchResult]:
        normalized_sources = cls._normalize_sources(
            sources
        )

        if not normalized_sources:
            return []

        query_terms = cls._query_terms(
            query
        )

        candidates: list[
            tuple[
                float,
                SearchResult,
            ]
        ] = []

        for source in normalized_sources:
            score = cls._relevance_score(
                query=query,
                query_terms=query_terms,
                source=source,
            )

            if score <= 0:
                continue

            low_value = cls._is_low_value(
                source
            )

            strong_domain = (
                cls._domain_quality(
                    source.domain
                ) >= 0.80
            )

            if (
                low_value
                and not strong_domain
                and score < 0.58
            ):
                continue

            candidates.append(
                (
                    score,
                    source,
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            source
            for _, source in candidates
        ]

    @classmethod
    def select_best_sources(
        cls,
        query: str,
        sources: Iterable[SearchResult],
        *,
        max_selected: int | None = None,
    ) -> list[SearchResult]:
        """
        Select compact evidence from a larger candidate pool.

        This is evidence-driven rather than count-driven:
        - strong sources are preferred
        - independent domains receive a bonus
        - sources covering new question dimensions receive a bonus
        - redundant weak sources are deprioritized

        max_selected is only a caller safety ceiling.
        """

        candidates = cls.filter_sources(
            query,
            sources,
        )

        if not candidates:
            return []

        dimensions = cls._query_dimensions(
            query
        )

        selected: list[
            SearchResult
        ] = []

        selected_domains: set[str] = set()
        covered_dimensions: set[str] = set()

        remaining = list(
            candidates
        )

        while remaining:
            best_source = None
            best_score = float(
                "-inf"
            )

            for source in remaining:
                base_score = cls._source_strength(
                    source
                )

                domain_bonus = (
                    0.18
                    if source.domain
                    not in selected_domains
                    else 0.0
                )

                new_dimensions = (
                    cls._source_dimensions(
                        source,
                        dimensions,
                    )
                    - covered_dimensions
                )

                coverage_bonus = (
                    0.20
                    * len(
                        new_dimensions
                    )
                )

                score = (
                    base_score
                    + domain_bonus
                    + coverage_bonus
                )

                if score > best_score:
                    best_score = score
                    best_source = source

            if best_source is None:
                break

            selected.append(
                best_source
            )

            if best_source.domain:
                selected_domains.add(
                    best_source.domain
                )

            covered_dimensions.update(
                cls._source_dimensions(
                    best_source,
                    dimensions,
                )
            )

            remaining.remove(
                best_source
            )

            if (
                max_selected is not None
                and len(selected)
                >= max_selected
            ):
                break

            if (
                dimensions
                and dimensions.issubset(
                    covered_dimensions
                )
            ):
                if cls._has_strong_corroboration(
                    selected
                ):
                    break

            if (
                not dimensions
                and cls._has_strong_corroboration(
                    selected
                )
            ):
                break

        return selected

    @classmethod
    def _heuristic_evaluation(
        cls,
        query: str,
        sources: list[SearchResult],
    ) -> EvidenceStatus:
        dimensions = cls._query_dimensions(
            query
        )

        covered_dimensions = (
            cls._covered_dimensions(
                sources,
                dimensions,
            )
        )

        meaningful_sources = [
            source
            for source in sources
            if cls._source_strength(
                source
            ) >= 0.50
        ]

        strong_sources = [
            source
            for source in meaningful_sources
            if cls._source_strength(
                source
            ) >= 0.80
        ]

        distinct_domains = {
            source.domain
            for source in meaningful_sources
            if source.domain
        }

        coverage_complete = (
            not dimensions
            or dimensions.issubset(
                covered_dimensions
            )
        )

        has_independent_corroboration = (
            len(
                distinct_domains
            ) >= 2
        )

        has_strong_single_source = any(
            cls._source_strength(
                source
            ) >= 0.92
            for source in meaningful_sources
        )

        broad_scope = (
            cls._is_broad_scope_query(
                query
            )
        )

        sufficient = False

        if coverage_complete:
            sufficient = (
                has_strong_single_source
                or (
                    len(strong_sources) >= 2
                    and has_independent_corroboration
                )
                or (
                    not broad_scope
                    and len(meaningful_sources) >= 2
                    and has_independent_corroboration
                )
            )

            if (
                broad_scope
                and not sufficient
            ):
                sufficient = (
                    len(strong_sources) >= 2
                    and has_independent_corroboration
                )

        if sufficient:
            return EvidenceStatus(
                sufficient=True,
                reason=(
                    "Evidence covers the material scope of the question "
                    "with sufficient source quality and independence."
                ),
                gaps=[],
                next_queries=[],
                key_findings=[],
                conflicts=[],
            )

        gaps: list[str] = []
        next_queries: list[str] = []

        missing_dimensions = sorted(
            dimensions
            - covered_dimensions
        )

        if missing_dimensions:
            for dimension in missing_dimensions:
                gaps.append(
                    (
                        "Coverage is missing for the "
                        f"{dimension} aspect."
                    )
                )

                next_queries.append(
                    cls._build_dimension_query(
                        query,
                        dimension,
                    )
                )

        if not strong_sources:
            gaps.append(
                (
                    "Need at least one stronger or "
                    "more authoritative source."
                )
            )

            next_queries.append(
                query
            )

        elif (
            not has_independent_corroboration
            and broad_scope
        ):
            gaps.append(
                (
                    "Need independent corroboration "
                    "from another strong source."
                )
            )

            next_queries.append(
                query
            )

        if not next_queries:
            next_queries.append(
                query
            )

        return EvidenceStatus(
            sufficient=False,
            reason=(
                "Evidence is relevant but the current set does not yet "
                "cover the full question with enough quality or diversity."
            ),
            gaps=gaps,
            next_queries=next_queries[:4],
            key_findings=[],
            conflicts=[],
        )

    @classmethod
    def _status_from_ai(
        cls,
        query: str,
        parsed: dict,
        fallback: EvidenceStatus,
    ) -> EvidenceStatus:
        sufficient = bool(
            parsed.get(
                "sufficient",
                fallback.sufficient,
            )
        )

        gaps = cls._clean_list(
            parsed.get(
                "gaps"
            )
        )

        next_queries = cls._clean_list(
            parsed.get(
                "next_queries"
            )
        )

        key_findings = cls._clean_list(
            parsed.get(
                "key_findings"
            )
        )

        conflicts = cls._clean_list(
            parsed.get(
                "conflicts"
            )
        )

        dimensions = cls._query_dimensions(
            query
        )

        if not sufficient and not next_queries:
            next_queries = fallback.next_queries

        if (
            sufficient
            and not cls._ai_claims_complete_scope(
                query,
                gaps,
            )
        ):
            if fallback.sufficient:
                sufficient = True
            else:
                sufficient = False
                next_queries = (
                    next_queries
                    or fallback.next_queries
                )

        if (
            not sufficient
            and dimensions
            and not gaps
        ):
            next_queries = (
                next_queries
                or fallback.next_queries
            )

        reason = str(
            parsed.get(
                "reason"
            )
            or fallback.reason
        ).strip()

        return EvidenceStatus(
            sufficient=sufficient,
            reason=reason,
            gaps=(
                gaps
                or fallback.gaps
            ),
            next_queries=next_queries,
            key_findings=key_findings,
            conflicts=conflicts,
        )

    @classmethod
    def _normalize_sources(
        cls,
        sources: Iterable[SearchResult],
    ) -> list[SearchResult]:
        normalized: list[
            SearchResult
        ] = []

        seen: set[str] = set()

        for source in sources:
            url = (
                getattr(
                    source,
                    "url",
                    "",
                )
                or ""
            ).strip()

            if not url:
                continue

            normalized_url = (
                url.rstrip("/")
                .casefold()
            )

            if normalized_url in seen:
                continue

            seen.add(
                normalized_url
            )

            domain = (
                getattr(
                    source,
                    "domain",
                    "",
                )
                or urlparse(
                    url
                ).netloc
            )

            domain = (
                domain
                .lower()
                .split(":")[0]
                .removeprefix("www.")
            )

            source.domain = domain

            source.is_authoritative = (
                cls._is_authoritative(
                    domain
                )
            )

            normalized.append(
                source
            )

        return normalized

    @staticmethod
    def _query_terms(
        query: str,
    ) -> set[str]:
        terms = re.findall(
            r"[A-Za-z0-9]{3,}",
            query,
        )

        return {
            term.casefold()
            for term in terms
            if term.casefold()
            not in STOP_WORDS
        }

    @classmethod
    def _relevance_score(
        cls,
        *,
        query: str,
        query_terms: set[str],
        source: SearchResult,
    ) -> float:
        title = (
            getattr(
                source,
                "title",
                "",
            )
            or ""
        ).casefold()

        snippet = (
            getattr(
                source,
                "snippet",
                "",
            )
            or ""
        ).casefold()

        content = (
            getattr(
                source,
                "content",
                "",
            )
            or ""
        ).casefold()

        domain = (
            getattr(
                source,
                "domain",
                "",
            )
            or ""
        ).casefold()

        if not query_terms:
            return 0.0

        title_hits = sum(
            1
            for term in query_terms
            if term in title
        )

        body_hits = sum(
            1
            for term in query_terms
            if (
                term in snippet
                or term in content
            )
        )

        quality = cls._domain_quality(
            domain
        )

        relevance_score = float(
            getattr(
                source,
                "relevance_score",
                0.0,
            )
            or 0.0
        )

        score = (
            (
                min(
                    1.0,
                    title_hits
                    / max(
                        2,
                        len(query_terms),
                    ),
                )
                * 0.35
            )
            + (
                min(
                    1.0,
                    body_hits
                    / max(
                        3,
                        len(query_terms),
                    ),
                )
                * 0.35
            )
            + (
                quality
                * 0.20
            )
            + (
                min(
                    1.0,
                    relevance_score,
                )
                * 0.10
            )
        )

        normalized_query = (
            query.casefold()
        )

        if (
            normalized_query
            and normalized_query
            in (
                title
                + " "
                + snippet
            )
        ):
            score += 0.10

        return min(
            1.0,
            score,
        )

    @classmethod
    def _source_strength(
        cls,
        source: SearchResult,
    ) -> float:
        quality = cls._domain_quality(
            source.domain
        )

        relevance = float(
            getattr(
                source,
                "relevance_score",
                0.0,
            )
            or 0.0
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

        if len(content) >= 600:
            content_score = 1.0
        elif len(content) >= 250:
            content_score = 0.70
        else:
            content_score = 0.40

        return min(
            1.0,
            (
                quality
                * 0.55
            )
            + (
                min(
                    1.0,
                    relevance,
                )
                * 0.20
            )
            + (
                content_score
                * 0.25
            ),
        )

    @classmethod
    def _domain_quality(
        cls,
        domain: str,
    ) -> float:
        host = (
            domain
            or ""
        ).lower()

        host = (
            host
            .split(":")[0]
            .removeprefix("www.")
        )

        if not host:
            return 0.30

        if (
            host in AUTHORITATIVE_DOMAINS
            or host.endswith(
                AUTHORITATIVE_DOMAIN_SUFFIXES
            )
        ):
            return 1.00

        if host in FIRST_PARTY_DOMAINS:
            return 0.98

        if host in STRONG_EDITORIAL_DOMAINS:
            return 0.90

        if host in DATABASE_LIKE_DOMAINS:
            return 0.72

        if host in LOW_VALUE_DOMAINS:
            return 0.25

        return 0.58

    @classmethod
    def _query_dimensions(
        cls,
        query: str,
    ) -> set[str]:
        normalized = " ".join(
            query.casefold().split()
        )

        dimensions: set[str] = set()

        for left, right in DIMENSION_GROUPS:
            if (
                left in normalized
                and right in normalized
            ):
                dimensions.add(
                    left
                )
                dimensions.add(
                    right
                )

        return dimensions

    @classmethod
    def _source_dimensions(
        cls,
        source: SearchResult,
        dimensions: set[str],
    ) -> set[str]:
        if not dimensions:
            return set()

        combined = " ".join(
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

        covered: set[str] = set()

        for dimension in dimensions:
            if dimension in combined:
                covered.add(
                    dimension
                )

        return covered

    @classmethod
    def _covered_dimensions(
        cls,
        sources: list[SearchResult],
        dimensions: set[str],
    ) -> set[str]:
        covered: set[str] = set()

        for source in sources:
            covered.update(
                cls._source_dimensions(
                    source,
                    dimensions,
                )
            )

        return covered

    @classmethod
    def _has_strong_corroboration(
        cls,
        sources: list[SearchResult],
    ) -> bool:
        strong_sources = [
            source
            for source in sources
            if cls._source_strength(
                source
            ) >= 0.78
        ]

        domains = {
            source.domain
            for source in strong_sources
            if source.domain
        }

        return len(
            domains
        ) >= 2

    @staticmethod
    def _is_authoritative(
        domain: str,
    ) -> bool:
        normalized = (
            domain
            .lower()
            .split(":")[0]
            .removeprefix("www.")
        )

        if normalized in AUTHORITATIVE_DOMAINS:
            return True

        return normalized.endswith(
            AUTHORITATIVE_DOMAIN_SUFFIXES
        )

    @staticmethod
    def _is_first_party(
        domain: str,
    ) -> bool:
        normalized = (
            domain
            .lower()
            .split(":")[0]
            .removeprefix("www.")
        )

        return (
            normalized in FIRST_PARTY_DOMAINS
            or any(
                normalized.endswith(
                    f".{base}"
                )
                for base in FIRST_PARTY_DOMAINS
            )
        )

    @staticmethod
    def _is_low_value(
        source: SearchResult,
    ) -> bool:
        domain = (
            getattr(
                source,
                "domain",
                "",
            )
            or ""
        ).lower()

        domain = (
            domain
            .removeprefix("www.")
        )

        if domain in LOW_VALUE_DOMAINS:
            return True

        url = (
            getattr(
                source,
                "url",
                "",
            )
            or ""
        ).casefold()

        return any(
            hint in url
            for hint in LOW_VALUE_PATH_HINTS
        )

    @staticmethod
    def _is_broad_scope_query(
        query: str,
    ) -> bool:
        normalized = (
            query.casefold()
        )

        return (
            "all " in normalized
            or "list" in normalized
            or "who are" in normalized
            or "which are" in normalized
            or "kaun kaun" in normalized
            or "kaun se" in normalized
            or "top" in normalized
            or "major" in normalized
        )

    @staticmethod
    def _build_dimension_query(
        query: str,
        dimension: str,
    ) -> str:
        return (
            f"{query} specifically covering "
            f"{dimension} with recent or authoritative sources"
        )

    @classmethod
    def _ai_claims_complete_scope(
        cls,
        query: str,
        gaps: list[str],
    ) -> bool:
        dimensions = cls._query_dimensions(
            query
        )

        if not dimensions:
            return not gaps

        gap_text = " ".join(
            gaps
        ).casefold()

        return not any(
            dimension in gap_text
            for dimension in dimensions
        )

    @classmethod
    def _build_evaluation_prompt(
        cls,
        query: str,
        sources: list[SearchResult],
    ) -> str:
        source_blocks: list[str] = []
        used_chars = 0

        for index, source in enumerate(
            sources,
            start=1,
        ):
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

            content = content[
                : cls.MAX_SOURCE_CONTENT_CHARS
            ]

            block = "\n".join(
                [
                    f"SOURCE {index}",
                    (
                        "Title: "
                        f"{getattr(source, 'title', '')}"
                    ),
                    (
                        "URL: "
                        f"{getattr(source, 'url', '')}"
                    ),
                    (
                        "Domain: "
                        f"{getattr(source, 'domain', '')}"
                    ),
                    (
                        "Quality score: "
                        f"{cls._source_strength(source):.2f}"
                    ),
                    (
                        "Evidence: "
                        f"{content}"
                    ),
                ]
            )

            remaining = (
                cls.MAX_EVALUATION_CONTEXT_CHARS
                - used_chars
            )

            if remaining <= 0:
                break

            source_blocks.append(
                block[:remaining]
            )

            used_chars += len(
                block
            )

        dimensions = sorted(
            cls._query_dimensions(
                query
            )
        )

        dimension_instruction = (
            ", ".join(
                dimensions
            )
            if dimensions
            else "none explicitly detected"
        )

        return (
            "You are Zoya's research evidence evaluator.\n\n"
            "Decide whether the evidence is sufficient to answer "
            "the user's actual question accurately.\n\n"
            "RULES:\n"
            "- There is NO minimum source count.\n"
            "- There is NO target source count.\n"
            "- Source count alone must never decide sufficiency.\n"
            "- Every material aspect of the user's question must be covered.\n"
            "- If the question has multiple dimensions, all material "
            "dimensions must be represented in the evidence before stopping.\n"
            "- Prefer authoritative, first-party, institutional, and "
            "strong editorial sources.\n"
            "- Do not treat weak social/forum sources as the primary "
            "support when stronger evidence exists.\n"
            "- Reject unrelated profile, directory, career, training, "
            "or generic pages.\n"
            "- A current question requires current evidence; an old "
            "publication does not become current merely because it "
            "matches the topic.\n"
            "- If a material dimension is missing, return a targeted "
            "follow-up query for that specific dimension.\n"
            "- Return JSON only.\n\n"
            "JSON schema:\n"
            "{"
            '"sufficient": true|false, '
            '"reason": "...", '
            '"gaps": ["..."], '
            '"next_queries": ["..."], '
            '"key_findings": ["..."], '
            '"conflicts": ["..."]'
            "}\n\n"
            f"USER QUESTION:\n{query}\n\n"
            "EXPLICIT DIMENSIONS TO CHECK:\n"
            f"{dimension_instruction}\n\n"
            "COLLECTED SOURCES:\n"
            + "\n\n".join(
                source_blocks
            )
        )

    @staticmethod
    def _parse_json(
        raw: str,
    ) -> dict | None:
        if not raw:
            return None

        text = str(
            raw
        ).strip()

        if text.startswith(
            "```"
        ):
            text = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                text,
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            ).strip()

        try:
            data = json.loads(
                text
            )
        except json.JSONDecodeError:
            start = text.find(
                "{"
            )

            end = text.rfind(
                "}"
            )

            if (
                start < 0
                or end <= start
            ):
                return None

            try:
                data = json.loads(
                    text[
                        start:end + 1
                    ]
                )
            except json.JSONDecodeError:
                return None

        return (
            data
            if isinstance(
                data,
                dict,
            )
            else None
        )

    @staticmethod
    def _clean_list(
        value: object,
    ) -> list[str]:
        if not isinstance(
            value,
            list,
        ):
            return []

        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    @staticmethod
    def _insufficient_status(
        *,
        query: str,
        reason: str,
        gaps: list[str],
    ) -> EvidenceStatus:
        return EvidenceStatus(
            sufficient=False,
            reason=reason,
            gaps=gaps,
            next_queries=[
                query
            ],
            key_findings=[],
            conflicts=[],
        )