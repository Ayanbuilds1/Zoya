from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .execution import ToolExecutionResult


@dataclass(frozen=True)
class ToolResponsePresentation:
    """Stable user-facing representation of a tool execution result."""

    status: str
    tool_name: str
    text: str
    output_files: tuple[str, ...] = ()


class ToolResultPresenter:
    """Convert internal tool execution results into safe user-facing text.

    This layer deliberately does not call an AI model. It only interprets the
    structured result/status produced by ToolExecutor.
    """

    @staticmethod
    def present(result: "ToolExecutionResult") -> ToolResponsePresentation:
        output_files = ToolResultPresenter._output_files(result)

        if result.status == "confirmation_required":
            text = (
                result.message
                or "Is tool action ko execute karne se pehle aapki confirmation chahiye."
            )
            return ToolResponsePresentation(
                status=result.status,
                tool_name=result.tool_name,
                text=text,
                output_files=output_files,
            )

        if result.status == "blocked":
            text = result.message or "Ye tool action current execution policy ne block kar diya."
            return ToolResponsePresentation(
                status=result.status,
                tool_name=result.tool_name,
                text=text,
                output_files=output_files,
            )

        if result.success and result.tool_result is not None:
            text = (
                result.tool_result.user_message
                or "Tool action successfully complete ho gaya."
            )
            if output_files:
                text += "\n" + "\n".join(
                    f"Output: {path}" for path in output_files
                )
            return ToolResponsePresentation(
                status="executed",
                tool_name=result.tool_name,
                text=text,
                output_files=output_files,
            )

        text = (
            result.message
            or (
                result.tool_result.user_message
                if result.tool_result is not None
                else None
            )
            or "Tool action complete nahi ho paya."
        )
        return ToolResponsePresentation(
            status=result.status,
            tool_name=result.tool_name,
            text=text,
            output_files=output_files,
        )

    @staticmethod
    def _output_files(result: "ToolExecutionResult") -> tuple[str, ...]:
        if result.tool_result is None:
            return ()

        data: dict[str, Any] = result.tool_result.data or {}
        values: list[str] = []

        output_file = data.get("output_file")
        if isinstance(output_file, str) and output_file.strip():
            values.append(output_file.strip())

        output_files = data.get("output_files")
        if isinstance(output_files, (list, tuple)):
            for value in output_files:
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())

        # Stable order + de-duplication.
        return tuple(dict.fromkeys(values))
