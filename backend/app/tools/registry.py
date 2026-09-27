from __future__ import annotations

from typing import Iterable

from .base import ZoyaTool
from .types import ToolResult


class ToolRegistry:
    """In-memory registry for capability discovery and controlled execution."""

    def __init__(self, tools: Iterable[ZoyaTool] | None = None) -> None:
        self._tools: dict[str, ZoyaTool] = {}
        for tool in tools or ():
            self.register(tool)

    def register(self, tool: ZoyaTool) -> None:
        name = tool.manifest.name.strip()
        if not name:
            raise ValueError("Tool name cannot be empty.")
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> ZoyaTool | None:
        return self._tools.get(name)

    def list_manifests(self) -> list[dict]:
        return [
            {
                "name": tool.manifest.name,
                "description": tool.manifest.description,
                "permission": tool.manifest.permission,
                "network_required": tool.manifest.network_required,
                "requires_confirmation": tool.manifest.requires_confirmation,
                "timeout_seconds": tool.manifest.timeout_seconds,
                "input_schema": dict(tool.manifest.input_schema),
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult.fail(
                tool_name=name,
                code="tool_not_found",
                message=f"Tool is not registered: {name}",
            )
        return tool.execute(arguments)
