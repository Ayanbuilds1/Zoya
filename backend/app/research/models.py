from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class SearchResult:
    """Normalized search result shared by every research provider."""

    title: str
    url: str
    snippet: str = ""
    provider: str = ""
    domain: str = ""
    published_at: Optional[datetime] = None
    content: str = ""
    is_authoritative: bool = False


@dataclass(slots=True)
class EvidenceStatus:
    """Qualitative assessment of the evidence collected so far."""

    sufficient: bool
    reason: str
    gaps: list[str] = field(default_factory=list)
    next_queries: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResearchResult:
    """Complete research run returned to the chat layer."""

    query: str
    sources: list[SearchResult]
    evidence_status: EvidenceStatus
    providers_used: list[str]
    search_count: int
    research_duration: float
    evidence_context: str
    search_queries: list[str] = field(default_factory=list)

    @property
    def key_findings(self) -> list[str]:
        return self.evidence_status.key_findings

    @property
    def conflicts(self) -> list[str]:
        return self.evidence_status.conflicts