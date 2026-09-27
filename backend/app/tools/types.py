from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolManifest:
    """Static description of a Zoya tool capability."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    permission: str = "local_read"
    network_required: bool = False
    requires_confirmation: bool = False
    timeout_seconds: float = 30.0


@dataclass
class ToolResult:
    """Normalized result returned by every tool invocation."""

    success: bool
    tool_name: str
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    user_message: str | None = None

    @classmethod
    def ok(
        cls,
        *,
        tool_name: str,
        data: dict[str, Any] | None = None,
        user_message: str | None = None,
    ) -> "ToolResult":
        return cls(
            success=True,
            tool_name=tool_name,
            data=data or {},
            user_message=user_message,
        )

    @classmethod
    def fail(
        cls,
        *,
        tool_name: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> "ToolResult":
        return cls(
            success=False,
            tool_name=tool_name,
            error={
                "code": code,
                "message": message,
                "details": details or {},
            },
            user_message=message,
        )
