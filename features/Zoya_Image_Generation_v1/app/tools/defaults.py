from __future__ import annotations

from pathlib import Path

from .genoffice import GenOfficeTool
from .imagegen import GeminiImageGenerationTool
from .imagemagick import ImageMagickTool
from .registry import ToolRegistry


def build_default_registry(*, workspace_root: str | Path) -> ToolRegistry:
    """Create the default local tool registry."""

    return ToolRegistry(
        tools=[
            ImageMagickTool(workspace_root=workspace_root),
            GenOfficeTool(workspace_root=workspace_root),
            GeminiImageGenerationTool(workspace_root=workspace_root),
        ]
    )
