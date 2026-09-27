from __future__ import annotations

from pathlib import Path

from .imagemagick import ImageMagickTool
from .registry import ToolRegistry


def build_default_registry(*, workspace_root: str | Path) -> ToolRegistry:
    """Create the initial registry without changing Zoya's existing core flow."""

    return ToolRegistry(
        tools=[
            ImageMagickTool(workspace_root=workspace_root),
        ]
    )
