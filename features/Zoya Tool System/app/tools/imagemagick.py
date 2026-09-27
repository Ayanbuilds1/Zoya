from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .base import ZoyaTool
from .types import ToolManifest, ToolResult


class ImageMagickTool(ZoyaTool):
    """Controlled local image-processing adapter.

    This intentionally supports a small allow-list of operations. It never accepts
    arbitrary ImageMagick command-line flags from the user.
    """

    manifest = ToolManifest(
        name="imagemagick",
        description="Local image conversion, resizing and cropping.",
        input_schema={
            "type": "object",
            "required": ["operation", "input_file", "output_file"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["convert", "resize", "crop"],
                },
                "input_file": {"type": "string"},
                "output_file": {"type": "string"},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
                "crop_width": {"type": "integer", "minimum": 1},
                "crop_height": {"type": "integer", "minimum": 1},
                "x": {"type": "integer", "minimum": 0},
                "y": {"type": "integer", "minimum": 0},
            },
        },
        permission="local_write",
        network_required=False,
        requires_confirmation=False,
        timeout_seconds=30.0,
    )

    _OPERATIONS = {"convert", "resize", "crop"}

    def __init__(self, *, workspace_root: str | os.PathLike[str]) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def _safe_path(self, raw: Any, *, must_exist: bool) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("File path must be a non-empty string.")

        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate

        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError("File path is outside the configured workspace.") from exc

        if must_exist and not resolved.is_file():
            raise FileNotFoundError(str(resolved))

        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    @staticmethod
    def _positive_int(arguments: Mapping[str, Any], key: str) -> int:
        value = arguments.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{key} must be a positive integer.")
        return value

    @staticmethod
    def _non_negative_int(arguments: Mapping[str, Any], key: str) -> int:
        value = arguments.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer.")
        return value

    def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        operation = arguments.get("operation")
        if operation not in self._OPERATIONS:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="invalid_operation",
                message=f"Unsupported ImageMagick operation: {operation}",
            )

        binary = shutil.which("magick")
        if binary is None:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="tool_unavailable",
                message="ImageMagick is not installed or 'magick' is not on PATH.",
            )

        try:
            input_file = self._safe_path(arguments.get("input_file"), must_exist=True)
            output_file = self._safe_path(arguments.get("output_file"), must_exist=False)

            command: list[str] = [binary, str(input_file)]

            if operation == "convert":
                pass
            elif operation == "resize":
                width = self._positive_int(arguments, "width")
                height = self._positive_int(arguments, "height")
                command.extend(["-resize", f"{width}x{height}"])
            elif operation == "crop":
                crop_width = self._positive_int(arguments, "crop_width")
                crop_height = self._positive_int(arguments, "crop_height")
                x = self._non_negative_int(arguments, "x")
                y = self._non_negative_int(arguments, "y")
                command.extend(["-crop", f"{crop_width}x{crop_height}+{x}+{y}"])

            command.append(str(output_file))

            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.manifest.timeout_seconds,
                check=False,
            )

            if completed.returncode != 0:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="execution_failed",
                    message="ImageMagick failed to process the image.",
                    details={
                        "returncode": completed.returncode,
                        "stderr": completed.stderr[-1200:],
                    },
                )

            if not output_file.is_file():
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="output_missing",
                    message="ImageMagick reported success but the output file was not created.",
                )

            return ToolResult.ok(
                tool_name=self.manifest.name,
                data={
                    "operation": operation,
                    "input_file": str(input_file),
                    "output_file": str(output_file),
                },
                user_message="Image processing completed successfully.",
            )
        except FileNotFoundError as exc:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="input_missing",
                message="Input file was not found inside the configured workspace.",
                details={"path": str(exc)},
            )
        except (TypeError, ValueError) as exc:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="invalid_arguments",
                message=str(exc),
            )
        except subprocess.TimeoutExpired:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="timeout",
                message="Image processing timed out.",
            )
        except OSError as exc:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="execution_error",
                message="ImageMagick could not be started.",
                details={"error": str(exc)},
            )
