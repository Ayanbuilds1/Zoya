from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class ImageGenerationRequest:
    """Provider-neutral image-generation request."""

    prompt: str
    aspect_ratio: str = "1:1"
    image_size: str = "1K"
    output_file: Path | None = None
    model: str | None = None
    negative_prompt: str | None = None
    seed: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenerationResult:
    """Normalized provider result before it becomes a Zoya ToolResult."""

    success: bool
    provider: str
    model: str | None = None
    image_path: str | None = None
    image_url: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    request_id: str | None = None
    generation_time_seconds: float | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    permanent: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ImageProviderError(RuntimeError):
    """Normalized provider failure used by the router."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool = False,
        permanent: bool = False,
        provider_status: int | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.permanent = permanent
        self.provider_status = provider_status
        self.details = dict(details or {})


class ImageProvider(Protocol):
    """Provider contract used by ImageProviderRouter."""

    name: str

    def supports(self, request: ImageGenerationRequest) -> bool:
        ...

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        ...


def normalize_aspect_ratio(value: str | None) -> str:
    ratio = str(value or "1:1").strip()
    return ratio if ratio else "1:1"


def size_label_to_square_edge(image_size: str) -> int:
    normalized = str(image_size or "1K").upper()
    return {
        "512": 512,
        "1K": 1024,
        "2K": 2048,
        "4K": 4096,
    }.get(normalized, 1024)


def aspect_to_dimensions(
    aspect_ratio: str,
    image_size: str,
) -> tuple[int, int]:
    """Choose practical output dimensions for generic remote providers."""

    edge = size_label_to_square_edge(image_size)
    ratios = {
        "1:1": (1, 1),
        "16:9": (16, 9),
        "9:16": (9, 16),
        "4:3": (4, 3),
        "3:4": (3, 4),
        "3:2": (3, 2),
        "2:3": (2, 3),
        "4:5": (4, 5),
        "5:4": (5, 4),
        "21:9": (21, 9),
    }
    width_ratio, height_ratio = ratios.get(aspect_ratio, (1, 1))

    # Keep the longer side near the requested quality tier.
    if width_ratio >= height_ratio:
        width = edge
        height = max(1, round(edge * height_ratio / width_ratio))
    else:
        height = edge
        width = max(1, round(edge * width_ratio / height_ratio))

    # Keep dimensions even; several diffusion stacks expect even dimensions.
    width -= width % 2
    height -= height % 2
    return max(width, 2), max(height, 2)


def closest_supported_dimensions(
    aspect_ratio: str,
    supported: tuple[tuple[int, int], ...],
) -> tuple[int, int] | None:
    """Pick the closest provider-native resolution for a requested ratio."""

    if not supported:
        return None

    ratios = {
        "1:1": 1.0,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "3:2": 3 / 2,
        "2:3": 2 / 3,
        "4:5": 4 / 5,
        "5:4": 5 / 4,
    }
    target = ratios.get(aspect_ratio, 1.0)
    return min(
        supported,
        key=lambda item: abs((item[0] / item[1]) - target),
    )
