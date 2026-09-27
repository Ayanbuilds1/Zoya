from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .base import ZoyaTool
from .types import ToolManifest, ToolResult


class GeminiImageGenerationTool(ZoyaTool):
    """Text-to-image generation through Google's Gemini image API.

    The tool performs only prompt-to-image generation in v1. It keeps all
    generated files inside Zoya's configured workspace and never accepts
    arbitrary HTTP destinations or raw provider request parameters.
    """

    manifest = ToolManifest(
        name="imagegen",
        description=(
            "Generate a new image from a natural-language prompt using the Gemini image model. "
            "Supports user-supplied image prompts, optional aspect ratio, resolution, and a local output path."
        ),
        input_schema={
            "type": "object",
            "required": ["prompt"],
            "properties": {
                "prompt": {"type": "string"},
                "output_file": {"type": "string"},
                "aspect_ratio": {
                    "type": "string",
                    "enum": [
                        "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
                        "9:16", "16:9", "21:9", "1:8", "8:1", "1:4", "4:1",
                    ],
                },
                "image_size": {
                    "type": "string",
                    "enum": ["512", "1K", "2K", "4K"],
                },
            },
        },
        permission="local_write",
        network_required=True,
        requires_confirmation=False,
        timeout_seconds=120.0,
    )

    _API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
    _DEFAULT_MODEL = "gemini-3.1-flash-image"
    _ASPECT_RATIOS = {
        "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
        "9:16", "16:9", "21:9", "1:8", "8:1", "1:4", "4:1",
    }
    _IMAGE_SIZES = {"512", "1K", "2K", "4K"}

    def __init__(self, *, workspace_root: str | os.PathLike[str]) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def _safe_output_path(self, raw: Any | None) -> Path:
        if raw is None or not str(raw).strip():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw = f"generated_images/zoya_image_{stamp}.png"

        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("output_file must be a non-empty string.")

        candidate = Path(raw.strip())
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate

        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError("File path is outside the configured workspace.") from exc

        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    @staticmethod
    def _require_prompt(arguments: Mapping[str, Any]) -> str:
        value = arguments.get("prompt")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("prompt must be a non-empty string.")
        return value.strip()

    @classmethod
    def _extract_image_payload(cls, payload: Any) -> tuple[str, str]:
        """Return base64 image data and MIME type from a Gemini interaction."""
        candidates: list[Any] = []

        if isinstance(payload, dict):
            output_image = payload.get("output_image")
            if isinstance(output_image, dict):
                candidates.append(output_image)

            outputs = payload.get("outputs")
            if isinstance(outputs, list):
                candidates.extend(outputs)

            steps = payload.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict):
                        content = step.get("content")
                        if isinstance(content, list):
                            candidates.extend(content)

                        summary = step.get("summary")
                        if isinstance(summary, list):
                            candidates.extend(summary)

        def walk(value: Any) -> tuple[str, str] | None:
            if isinstance(value, dict):
                data = value.get("data")
                mime = value.get("mime_type") or value.get("mimeType") or "image/png"
                item_type = str(value.get("type") or "").lower()
                if isinstance(data, str) and data and (
                    item_type == "image" or str(mime).startswith("image/")
                ):
                    return data, str(mime)
                for child in value.values():
                    found = walk(child)
                    if found:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = walk(child)
                    if found:
                        return found
            return None

        for candidate in candidates:
            found = walk(candidate)
            if found:
                return found

        found = walk(payload)
        if found:
            return found

        raise ValueError("Gemini returned no image data.")

    @staticmethod
    def _decode_error(response: urllib.error.HTTPError) -> str:
        try:
            body = response.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        if not body:
            return f"HTTP {response.code}"
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    message = error.get("message")
                    if isinstance(message, str) and message.strip():
                        return message.strip()
        except json.JSONDecodeError:
            pass
        return body[:1200]

    def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        try:
            prompt = self._require_prompt(arguments)
            output_file = self._safe_output_path(arguments.get("output_file"))

            aspect_ratio = arguments.get("aspect_ratio") or "1:1"
            if aspect_ratio not in self._ASPECT_RATIOS:
                raise ValueError(f"Unsupported aspect_ratio: {aspect_ratio}")

            image_size = arguments.get("image_size") or "1K"
            if image_size not in self._IMAGE_SIZES:
                raise ValueError(f"Unsupported image_size: {image_size}")

            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="missing_api_key",
                    message="Gemini image generation needs GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment.",
                )

            model = os.getenv("GEMINI_IMAGE_MODEL", self._DEFAULT_MODEL).strip() or self._DEFAULT_MODEL
            body: dict[str, Any] = {
                "model": model,
                "input": [{"type": "text", "text": prompt}],
                "response_format": {
                    "type": "image",
                    "aspect_ratio": aspect_ratio,
                    "image_size": image_size,
                },
            }

            request = urllib.request.Request(
                self._API_URL,
                data=json.dumps(body).encode("utf-8"),
                method="POST",
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            try:
                with urllib.request.urlopen(request, timeout=self.manifest.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                provider_message = self._decode_error(exc)
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="provider_http_error",
                    message="Gemini image generation failed.",
                    details={"http_status": exc.code, "provider_message": provider_message},
                )
            except urllib.error.URLError as exc:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="network_error",
                    message="Could not reach the Gemini image generation service.",
                    details={"reason": str(exc.reason)},
                )
            except TimeoutError:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="timeout",
                    message="Gemini image generation timed out.",
                )

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="invalid_provider_response",
                    message="Gemini returned an invalid image-generation response.",
                    details={"error": str(exc)},
                )

            image_data, returned_mime = self._extract_image_payload(payload)
            try:
                image_bytes = base64.b64decode(image_data, validate=True)
            except Exception as exc:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="invalid_image_data",
                    message="Gemini returned invalid image data.",
                    details={"error": type(exc).__name__},
                )

            if not image_bytes:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="empty_image",
                    message="Gemini returned an empty image.",
                )

            output_file.write_bytes(image_bytes)

            # Gemini may return PNG even when the requested output format was
            # JPEG. Keep the provider's actual bytes and report the returned MIME.
            return ToolResult.ok(
                tool_name=self.manifest.name,
                data={
                    "operation": "generate",
                    "output_file": str(output_file),
                    "mime_type": returned_mime,
                    "model": model,
                    "aspect_ratio": aspect_ratio,
                    "image_size": image_size,
                    "prompt": prompt,
                },
                user_message="Image generated successfully.",
            )

        except FileNotFoundError as exc:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="file_error",
                message=f"Output path could not be prepared: {exc}",
            )
        except ValueError as exc:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="invalid_input",
                message=str(exc),
            )
        except OSError as exc:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="file_error",
                message="The generated image could not be written to disk.",
                details={"error_type": type(exc).__name__},
            )
        except Exception as exc:  # defensive capability boundary
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="unexpected_error",
                message="Image generation failed unexpectedly.",
                details={"error_type": type(exc).__name__},
            )
