from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from .types import ToolManifest, ToolResult


class ZoyaTool(ABC):
    """Stable interface between Zoya orchestration and an external capability."""

    manifest: ToolManifest

    @abstractmethod
    def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        raise NotImplementedError
