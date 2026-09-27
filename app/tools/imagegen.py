from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .base import ZoyaTool
from .image_provider import ImageGenerationRequest
from .image_providers import (
    FreeLLMAPIProvider,
    LocalSDProvider,
    NvidiaProvider,
    PollinationsProvider,
)
from .image_router import ImageProviderRouter
from .types import ToolManifest, ToolResult


class ImageGenerationTool(ZoyaTool):
    """Provider-neutral text-to-image tool with ordered fallback."""

    manifest = ToolManifest(
        name="imagegen",
        description=(
            "Generate a new image from a natural-language prompt using the configured "
            "image-provider fallback chain. Supports aspect ratio, quality tier, and "
            "a local workspace output path."
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
                        "9:16", "16:9", "21:9",
                    ],
                },
                "image_size": {
                    "type": "string",
                    "enum": ["512", "1K", "2K", "4K"],
                },
                "model": {
                    "type": "string",
                    "description": "Optional provider/model override for adapters that support it.",
                },
            },
        },
        permission="local_write",
        network_required=True,
        requires_confirmation=False,
        timeout_seconds=120.0,
    )

    _ASPECT_RATIOS = {
        "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
        "9:16", "16:9", "21:9",
    }
    _IMAGE_SIZES = {"512", "1K", "2K", "4K"}

    def __init__(self, *, workspace_root: str | os.PathLike[str]) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.router = ImageProviderRouter(
            providers=(
                FreeLLMAPIProvider(),
                PollinationsProvider(),
                NvidiaProvider(),
                LocalSDProvider(),
            ),
            provider_order=self._provider_order(),
            cooldown_seconds=float(
                os.getenv("IMAGE_PROVIDER_COOLDOWN_SECONDS", "30")
            ),
        )

    @staticmethod
    def _provider_order() -> list[str]:
        raw = os.getenv(
            "IMAGE_PROVIDER_ORDER",
            "freellmapi,pollinations,nvidia,local_sd",
        )
        return [
            item.strip().lower()
            for item in raw.split(",")
            if item.strip()
        ]

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
            raise ValueError(
                "File path is outside the configured workspace."
            ) from exc

        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    @staticmethod
    def _require_prompt(arguments: Mapping[str, Any]) -> str:
        value = arguments.get("prompt")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("prompt must be a non-empty string.")
        return value.strip()

    def execute(self, arguments: Mapping[str, Any]) -> ToolResult:
        try:
            prompt = self._require_prompt(arguments)
            output_file = self._safe_output_path(arguments.get("output_file"))

            aspect_ratio = str(arguments.get("aspect_ratio") or "1:1")
            if aspect_ratio not in self._ASPECT_RATIOS:
                raise ValueError(
                    f"Unsupported aspect_ratio: {aspect_ratio}"
                )

            image_size = str(arguments.get("image_size") or "1K").upper()
            if image_size not in self._IMAGE_SIZES:
                raise ValueError(
                    f"Unsupported image_size: {image_size}"
                )

            model = arguments.get("model")
            model = (
                str(model).strip()
                if isinstance(model, str) and model.strip()
                else None
            )

            request = ImageGenerationRequest(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                output_file=output_file,
                model=model,
            )

            result = self.router.generate(request)

            if not result.success:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code=result.error_code or "image_generation_failed",
                    message=result.error_message
                    or "Image generation failed through all configured providers.",
                    details={
                        "provider": result.provider,
                        "attempted_providers": result.metadata.get(
                            "attempted_providers", []
                        ),
                        "fallback_failures": result.metadata.get(
                            "failures",
                            result.metadata.get("fallback_failures", []),
                        ),
                    },
                )

            # Anti-fake-success guard: a provider result is only considered
            # successful when the artifact exists and contains bytes.
            if not result.image_path:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="missing_artifact",
                    message="Image provider reported success but returned no artifact path.",
                )

            artifact = Path(result.image_path)
            if not artifact.exists() or artifact.stat().st_size <= 0:
                return ToolResult.fail(
                    tool_name=self.manifest.name,
                    code="missing_artifact",
                    message="Image generation did not produce a verified image artifact.",
                )

            return ToolResult.ok(
                tool_name=self.manifest.name,
                data={
                    "operation": "generate",
                    "output_file": str(artifact),
                    "mime_type": result.mime_type,
                    "provider": result.provider,
                    "model": result.model,
                    "width": result.width,
                    "height": result.height,
                    "request_id": result.request_id,
                    "generation_time_seconds": result.generation_time_seconds,
                    "attempted_providers": result.metadata.get(
                        "attempted_providers",
                        [],
                    ),
                    "fallback_failures": result.metadata.get(
                        "fallback_failures",
                        [],
                    ),
                },
                user_message=(
                    f"Image generated successfully using {result.provider} "
                    f"and saved to {artifact}."
                ),
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
        except Exception as exc:
            return ToolResult.fail(
                tool_name=self.manifest.name,
                code="unexpected_error",
                message="Image generation failed unexpectedly.",
                details={"error_type": type(exc).__name__},
            )


# Backward-compatible alias so existing imports/tests do not immediately break.
GeminiImageGenerationTool = ImageGenerationTool
