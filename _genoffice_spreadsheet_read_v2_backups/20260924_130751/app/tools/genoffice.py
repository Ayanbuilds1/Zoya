from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .base import ZoyaTool
from .types import ToolManifest, ToolResult


class GenOfficeTool(ZoyaTool):
    """Controlled local adapter for the GenOffice CLI.

    v1 intentionally exposes only local file operations:
    - info: inspect a document
    - convert: convert between supported formats
    - create: create a native office file from a source file
    - render: render a document to PNGs for verification/inspection

    Cloud-facing GenOffice commands (search/image/media) are deliberately not
    exposed by this first adapter.
    """

    manifest = ToolManifest(
        name="genoffice",
        description="Local document, spreadsheet, presentation and PDF operations through GenOffice CLI.",
        input_schema={
            "type": "object",
            "required": ["operation", "input_file"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["info", "convert", "create", "render"],
                },
                "input_file": {"type": "string"},
                "output_file": {"type": "string"},
                "output_dir": {"type": "string"},
                "target_format": {
                    "type": "string",
                    "enum": ["docx", "xlsx", "pptx", "pdf", "html", "md"],
                },
            },
        },
        permission="local_write",
        network_required=False,
        requires_confirmation=False,
        timeout_seconds=120.0,
    )

    _OPERATIONS = {"info", "convert", "create", "render"}
    _TARGET_FORMATS = {"docx", "xlsx", "pptx", "pdf", "html", "md"}

    def __init__(self, *, workspace_root: str | os.PathLike[str]) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def _safe_path(self, raw: Any, *, must_exist: bool, directory: bool = False) -> Path:
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

        if must_exist:
            if directory and not resolved.is_dir():
                raise FileNotFoundError(str(resolved))
            if not directory and not resolved.is_file():
                raise FileNotFoundError(str(resolved))

        if not must_exist:
            if directory:
                resolved.mkdir(parents=True, exist_ok=True)
            else:
                resolved.parent.mkdir(parents=True, exist_ok=True)

        return resolved

    @staticmethod
    def _require_string(arguments: Mapping[str, Any], key: str) -> str:
        value = arguments.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string.")
        return value.strip()

    def _binary(self) -> str | None:
        return shutil.which("genoffice")

    @staticmethod
    def _result_payload(completed: subprocess.CompletedProcess[str]) -> Any:
        stdout = (completed.stdout or "").strip()
        if not stdout:
            return {}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"raw_output": stdout}

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.manifest.timeout_seconds,
            check=False,
        )

    def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        operation = arguments.get("operation")
        if operation not in self._OPERATIONS:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="invalid_operation",
                message=f"Unsupported GenOffice operation: {operation}",
            )

        binary = self._binary()
        if binary is None:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="tool_unavailable",
                message="GenOffice CLI is not installed or 'genoffice' is not on PATH.",
            )

        try:
            input_file = self._safe_path(
                self._require_string(arguments, "input_file"),
                must_exist=True,
            )

            if operation == "info":
                command = [binary, "info", str(input_file), "--json"]
                completed = self._run(command)
                output_file = None
                output_dir = None

            elif operation == "convert":
                target_format = self._require_string(arguments, "target_format").lower()
                if target_format not in self._TARGET_FORMATS:
                    raise ValueError(f"Unsupported target_format: {target_format}")
                output_file = self._safe_path(
                    self._require_string(arguments, "output_file"),
                    must_exist=False,
                )
                output_dir = None
                command = [
                    binary,
                    "convert",
                    str(input_file),
                    "--to",
                    target_format,
                    "--out",
                    str(output_file),
                    "--json",
                ]
                completed = self._run(command)

            elif operation == "create":
                target_format = self._require_string(arguments, "target_format").lower()
                if target_format not in self._TARGET_FORMATS:
                    raise ValueError(f"Unsupported target_format: {target_format}")
                output_file = self._safe_path(
                    self._require_string(arguments, "output_file"),
                    must_exist=False,
                )
                output_dir = None
                command = [
                    binary,
                    "create",
                    "--type",
                    target_format,
                    "--from",
                    str(input_file),
                    "--out",
                    str(output_file),
                    "--json",
                ]
                completed = self._run(command)

            else:  # render
                output_dir = self._safe_path(
                    self._require_string(arguments, "output_dir"),
                    must_exist=False,
                    directory=True,
                )
                output_file = None
                command = [
                    binary,
                    "render",
                    str(input_file),
                    "--out",
                    str(output_dir),
                    "--json",
                ]
                completed = self._run(command)

            if completed.returncode != 0:
                stderr = (completed.stderr or "").strip()
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="execution_failed",
                    message="GenOffice could not complete the requested operation.",
                    details={
                        "returncode": completed.returncode,
                        "stderr": stderr[-1600:],
                    },
                )

            payload = self._result_payload(completed)

            if operation in {"convert", "create"} and output_file is not None:
                if not output_file.is_file():
                    return ToolResult.fail(
                        tool_name=self.manifest.name,
                        code="output_missing",
                        message="GenOffice reported success but the output file was not created.",
                    )
                user_message = "GenOffice completed successfully."
                payload = {
                    "operation": operation,
                    "input_file": str(input_file),
                    "output_file": str(output_file),
                    "result": payload,
                }
            elif operation == "render" and output_dir is not None:
                generated = sorted(
                    str(path)
                    for path in output_dir.rglob("*")
                    if path.is_file()
                )
                if not generated:
                    return ToolResult.fail(
                        tool_name=self.manifest.name,
                        code="output_missing",
                        message="GenOffice reported success but no rendered files were created.",
                    )
                user_message = "GenOffice rendered the document successfully."
                payload = {
                    "operation": operation,
                    "input_file": str(input_file),
                    "output_dir": str(output_dir),
                    "output_files": generated,
                    "result": payload,
                }
            else:
                user_message = "GenOffice inspected the file successfully."
                payload = {
                    "operation": operation,
                    "input_file": str(input_file),
                    "result": payload,
                }

            return ToolResult.ok(
                tool_name=self.manifest.name,
                data=payload,
                user_message=user_message,
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
                message="GenOffice operation timed out.",
            )
        except OSError as exc:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="execution_error",
                message="GenOffice could not be started.",
                details={"error": str(exc)},
            )
