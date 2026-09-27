from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .registry import ToolRegistry
from .types import ToolManifest, ToolResult


@dataclass(frozen=True)
class ToolExecutionPolicy:
    """Policy boundary between Zoya orchestration and registered tools."""

    allowed_permissions: frozenset[str] = frozenset({"local_read", "local_write"})
    allow_network_tools: bool = False
    allowed_network_tools: frozenset[str] = frozenset({"imagegen"})
    require_confirmation_for_permissions: frozenset[str] = frozenset()
    max_timeout_seconds: float = 120.0


@dataclass(frozen=True)
class ToolExecutionRequest:
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    confirmed: bool = False
    source: str = "brain"


@dataclass
class ToolExecutionResult:
    """Normalized execution-layer result.

    status is one of: executed, confirmation_required, blocked, failed.
    """

    status: str
    tool_name: str
    tool_result: ToolResult | None = None
    reason_code: str | None = None
    message: str | None = None
    manifest: dict[str, Any] | None = None

    @property
    def success(self) -> bool:
        return self.status == "executed" and bool(self.tool_result and self.tool_result.success)


class ToolExecutor:
    """Single policy-controlled gateway for all tool execution.

    Brain/orchestration should call this layer rather than invoking ToolRegistry
    directly. The executor performs capability checks and confirmation checks,
    then delegates actual work to the registry.
    """

    _VALID_STATUSES = frozenset({"executed", "confirmation_required", "blocked", "failed"})

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        policy: ToolExecutionPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or ToolExecutionPolicy()

    def manifest(self, tool_name: str) -> dict[str, Any] | None:
        tool = self.registry.get(tool_name)
        if tool is None:
            return None
        manifest: ToolManifest = tool.manifest
        return {
            "name": manifest.name,
            "description": manifest.description,
            "permission": manifest.permission,
            "network_required": manifest.network_required,
            "requires_confirmation": manifest.requires_confirmation,
            "timeout_seconds": manifest.timeout_seconds,
            "input_schema": dict(manifest.input_schema),
        }

    def list_manifests(self) -> list[dict[str, Any]]:
        """Return all registered tool manifests without executing anything."""
        manifests: list[dict[str, Any]] = []
        for item in self.registry.list_manifests():
            if isinstance(item, dict):
                manifests.append(dict(item))
        return manifests

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        tool = self.registry.get(request.tool_name)
        if tool is None:
            return ToolExecutionResult(
                status="failed",
                tool_name=request.tool_name,
                reason_code="tool_not_found",
                message=f"Tool is not registered: {request.tool_name}",
            )

        manifest = tool.manifest
        manifest_dict = self.manifest(request.tool_name)
        permission = manifest.permission

        if permission not in self.policy.allowed_permissions:
            return ToolExecutionResult(
                status="blocked",
                tool_name=request.tool_name,
                reason_code="permission_denied",
                message=f"Tool permission is not allowed: {permission}",
                manifest=manifest_dict,
            )

        if (
            manifest.network_required
            and not self.policy.allow_network_tools
            and request.tool_name not in self.policy.allowed_network_tools
        ):
            return ToolExecutionResult(
                status="blocked",
                tool_name=request.tool_name,
                reason_code="network_not_allowed",
                message="Network-required tools are disabled by the current execution policy.",
                manifest=manifest_dict,
            )

        if manifest.timeout_seconds > self.policy.max_timeout_seconds:
            return ToolExecutionResult(
                status="blocked",
                tool_name=request.tool_name,
                reason_code="timeout_policy_exceeded",
                message=(
                    f"Tool timeout ({manifest.timeout_seconds}s) exceeds the execution policy "
                    f"limit ({self.policy.max_timeout_seconds}s)."
                ),
                manifest=manifest_dict,
            )

        needs_confirmation = (
            manifest.requires_confirmation
            or permission in self.policy.require_confirmation_for_permissions
        )
        if needs_confirmation and not request.confirmed:
            return ToolExecutionResult(
                status="confirmation_required",
                tool_name=request.tool_name,
                reason_code="confirmation_required",
                message="User confirmation is required before this tool can execute.",
                manifest=manifest_dict,
            )

        try:
            tool_result = self.registry.execute(
                request.tool_name,
                dict(request.arguments),
            )
        except Exception as exc:  # pragma: no cover - defensive boundary
            return ToolExecutionResult(
                status="failed",
                tool_name=request.tool_name,
                reason_code="executor_exception",
                message="Tool execution failed unexpectedly.",
                manifest=manifest_dict,
                tool_result=ToolResult.fail(
                    tool_name=request.tool_name,
                    code="executor_exception",
                    message="Tool execution failed unexpectedly.",
                    details={"error_type": type(exc).__name__},
                ),
            )

        return ToolExecutionResult(
            status="executed" if tool_result.success else "failed",
            tool_name=request.tool_name,
            tool_result=tool_result,
            reason_code=None if tool_result.success else (tool_result.error or {}).get("code"),
            message=tool_result.user_message,
            manifest=manifest_dict,
        )
