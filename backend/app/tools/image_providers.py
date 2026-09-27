from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .image_provider import (
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageProviderError,
    aspect_to_dimensions,
    closest_supported_dimensions,
)


def _safe_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _http_json(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=_safe_json_bytes(payload),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **headers,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1600]
        message = body or f"HTTP {exc.code}"

        if exc.code == 401:
            raise ImageProviderError(
                "Provider authentication failed.",
                code="invalid_api_key",
                permanent=True,
                provider_status=exc.code,
            ) from exc
        if exc.code == 402:
            raise ImageProviderError(
                "Provider budget or allocation is exhausted.",
                code="quota_exhausted",
                retryable=True,
                provider_status=exc.code,
            ) from exc
        if exc.code == 429:
            raise ImageProviderError(
                "Provider rate limit was reached.",
                code="rate_limited",
                retryable=True,
                provider_status=exc.code,
            ) from exc
        if exc.code >= 500:
            raise ImageProviderError(
                "Provider service error.",
                code="server_error",
                retryable=True,
                provider_status=exc.code,
            ) from exc

        raise ImageProviderError(
            "Provider rejected the image request.",
            code="provider_http_error",
            permanent=400 <= exc.code < 500,
            provider_status=exc.code,
            details={"provider_message": message},
        ) from exc
    except urllib.error.URLError as exc:
        raise ImageProviderError(
            "Could not reach the image provider.",
            code="network_error",
            retryable=True,
            details={"reason": str(exc.reason)},
        ) from exc
    except TimeoutError as exc:
        raise ImageProviderError(
            "Image provider request timed out.",
            code="timeout",
            retryable=True,
        ) from exc

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImageProviderError(
            "Provider returned an invalid JSON response.",
            code="invalid_provider_response",
            retryable=True,
            details={"error_type": type(exc).__name__},
        ) from exc

    if not isinstance(parsed, dict):
        raise ImageProviderError(
            "Provider returned an unexpected response.",
            code="invalid_provider_response",
            retryable=True,
        )

    return parsed


def _walk_for_b64(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("b64_json", "base64", "data"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                # "data" is only accepted here when it really looks like base64
                # rather than a URL or a MIME/data URI wrapper.
                if key != "data" or "," not in value:
                    return value
        for value in payload.values():
            found = _walk_for_b64(value)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _walk_for_b64(value)
            if found:
                return found
    return None


def _walk_for_url(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("url", "image_url"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        for value in payload.values():
            found = _walk_for_url(value)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _walk_for_url(value)
            if found:
                return found
    return None


def _decode_base64(value: str) -> tuple[bytes, str | None]:
    mime: str | None = None
    raw_value = value

    if value.startswith("data:") and "," in value:
        header, raw_value = value.split(",", 1)
        if ";" in header:
            mime = header[5:].split(";", 1)[0] or None
        else:
            mime = header[5:] or None

    try:
        data = base64.b64decode(raw_value, validate=True)
    except Exception as exc:
        raise ImageProviderError(
            "Provider returned invalid image data.",
            code="invalid_image_data",
            retryable=True,
            details={"error_type": type(exc).__name__},
        ) from exc

    if not data:
        raise ImageProviderError(
            "Provider returned empty image data.",
            code="empty_image",
            retryable=True,
        )

    return data, mime


def _download_image(url: str, timeout: float) -> tuple[bytes, str | None]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "image/*"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type")
    except urllib.error.HTTPError as exc:
        raise ImageProviderError(
            "Generated image could not be downloaded.",
            code="artifact_download_error",
            retryable=exc.code >= 500,
            permanent=400 <= exc.code < 500,
            provider_status=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        raise ImageProviderError(
            "Generated image could not be downloaded.",
            code="artifact_download_error",
            retryable=True,
            details={"reason": str(exc.reason)},
        ) from exc
    except TimeoutError as exc:
        raise ImageProviderError(
            "Generated image download timed out.",
            code="timeout",
            retryable=True,
        ) from exc

    if not data:
        raise ImageProviderError(
            "Provider returned an empty image artifact.",
            code="empty_image",
            retryable=True,
        )

    return data, content_type


def _write_artifact(
    *,
    data: bytes,
    output_file: Path,
    mime_type: str | None,
) -> tuple[Path, str]:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(data)

    if not output_file.exists() or output_file.stat().st_size <= 0:
        raise ImageProviderError(
            "Generated image artifact could not be verified on disk.",
            code="artifact_write_failed",
            retryable=False,
        )

    return output_file, mime_type or "image/png"


class _OpenAICompatibleImageProvider:
    name = "openai_compatible"

    def supports(self, request: ImageGenerationRequest) -> bool:
        return True

    def _make_payload(
        self,
        request: ImageGenerationRequest,
        *,
        model: str,
        size: str,
    ) -> dict[str, Any]:
        payload = {
            "prompt": request.prompt,
            "model": model,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt
        if request.seed is not None:
            payload["seed"] = request.seed
        return payload


class FreeLLMAPIProvider(_OpenAICompatibleImageProvider):
    """Adapter for the self-hosted FreeLLMAPI OpenAI-compatible gateway."""

    name = "freellmapi"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
        default_model: str | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1")
        ).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("FREELLMAPI_API_KEY")
        self.timeout = timeout
        self.default_model = (
            default_model
            or os.getenv("FREELLMAPI_IMAGE_MODEL", "auto")
        )

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.api_key:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=request.model or self.default_model,
                error_code="missing_api_key",
                error_message="FreeLLMAPI unified API key is not configured.",
                permanent=True,
            )

        width, height = aspect_to_dimensions(
            request.aspect_ratio,
            request.image_size,
        )
        model = request.model or self.default_model
        payload = self._make_payload(
            request,
            model=model,
            size=f"{width}x{height}",
        )

        started = time.monotonic()
        try:
            response = _http_json(
                url=f"{self.base_url}/images/generations",
                payload=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            b64 = _walk_for_b64(response)
            mime_type = "image/png"

            if b64:
                data, detected_mime = _decode_base64(b64)
                mime_type = detected_mime or mime_type
            else:
                url = _walk_for_url(response)
                if not url:
                    raise ImageProviderError(
                        "FreeLLMAPI returned no image artifact.",
                        code="invalid_provider_response",
                        retryable=True,
                    )
                data, detected_mime = _download_image(url, self.timeout)
                mime_type = detected_mime or mime_type

            output_file = request.output_file
            if output_file is None:
                raise ImageProviderError(
                    "Image output path was not supplied by the tool.",
                    code="invalid_configuration",
                    permanent=True,
                )

            path, mime_type = _write_artifact(
                data=data,
                output_file=output_file,
                mime_type=mime_type,
            )

            request_id = response.get("id")
            return ImageGenerationResult(
                success=True,
                provider=self.name,
                model=model,
                image_path=str(path),
                mime_type=mime_type,
                request_id=str(request_id) if request_id else None,
                width=width,
                height=height,
                generation_time_seconds=round(time.monotonic() - started, 3),
            )
        except ImageProviderError as exc:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=model,
                error_code=exc.code,
                error_message=str(exc),
                retryable=exc.retryable,
                permanent=exc.permanent,
                metadata={"provider_status": exc.provider_status, **exc.details},
            )


class PollinationsProvider(_OpenAICompatibleImageProvider):
    """Adapter for Pollinations' current OpenAI-compatible image API."""

    name = "pollinations"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
        default_model: str | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("POLLINATIONS_BASE_URL", "https://gen.pollinations.ai")
        ).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("POLLINATIONS_API_KEY")
        self.timeout = timeout
        self.default_model = (
            default_model
            or os.getenv(
                "POLLINATIONS_IMAGE_MODEL",
                "black-forest-labs/flux.1-schnell",
            )
        )

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.api_key:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=request.model or self.default_model,
                error_code="missing_api_key",
                error_message="Pollinations API key is not configured.",
                permanent=True,
            )

        width, height = aspect_to_dimensions(
            request.aspect_ratio,
            request.image_size,
        )
        model = request.model or self.default_model

        payload = self._make_payload(
            request,
            model=model,
            size=f"{width}x{height}",
        )

        # Pollinations accepts quality values; medium is a neutral default.
        payload["quality"] = "medium"

        started = time.monotonic()
        try:
            response = _http_json(
                url=f"{self.base_url}/v1/images/generations",
                payload=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            b64 = _walk_for_b64(response)
            mime_type = "image/png"

            if b64:
                data, detected_mime = _decode_base64(b64)
                mime_type = detected_mime or mime_type
            else:
                url = _walk_for_url(response)
                if not url:
                    raise ImageProviderError(
                        "Pollinations returned no image artifact.",
                        code="invalid_provider_response",
                        retryable=True,
                    )
                data, detected_mime = _download_image(url, self.timeout)
                mime_type = detected_mime or mime_type

            output_file = request.output_file
            if output_file is None:
                raise ImageProviderError(
                    "Image output path was not supplied by the tool.",
                    code="invalid_configuration",
                    permanent=True,
                )

            path, mime_type = _write_artifact(
                data=data,
                output_file=output_file,
                mime_type=mime_type,
            )

            return ImageGenerationResult(
                success=True,
                provider=self.name,
                model=model,
                image_path=str(path),
                mime_type=mime_type,
                request_id=str(response.get("id")) if response.get("id") else None,
                width=width,
                height=height,
                generation_time_seconds=round(time.monotonic() - started, 3),
            )
        except ImageProviderError as exc:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=model,
                error_code=exc.code,
                error_message=str(exc),
                retryable=exc.retryable,
                permanent=exc.permanent,
                metadata={"provider_status": exc.provider_status, **exc.details},
            )


class NvidiaProvider:
    """Direct NVIDIA hosted Visual GenAI API adapter."""

    name = "nvidia"

    _SUPPORTED_FLUX2_RESOLUTIONS = (
        (672, 1568),
        (688, 1504),
        (720, 1456),
        (752, 1392),
        (800, 1328),
        (832, 1248),
        (880, 1184),
        (944, 1104),
        (1024, 1024),
        (1104, 944),
        (1184, 880),
        (1248, 832),
        (1328, 800),
        (1392, 752),
        (1456, 720),
        (1504, 688),
        (1568, 672),
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        default_model: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("NVIDIA_API_KEY")
        self.base_url = (
            base_url
            or os.getenv(
                "NVIDIA_IMAGE_BASE_URL",
                "https://ai.api.nvidia.com/v1/genai",
            )
        ).rstrip("/")
        self.timeout = timeout
        self.default_model = (
            default_model
            or os.getenv(
                "NVIDIA_IMAGE_MODEL",
                "black-forest-labs/flux.2-klein-4b",
            )
        )

    def supports(self, request: ImageGenerationRequest) -> bool:
        if str(request.image_size).upper() != "1K":
            return False

        dimensions = closest_supported_dimensions(
            request.aspect_ratio,
            self._SUPPORTED_FLUX2_RESOLUTIONS,
        )
        if dimensions is None:
            return False

        # Require the provider-native resolution to represent the requested
        # aspect ratio closely rather than silently pretending to support it.
        requested = {
            "1:1": 1.0,
            "16:9": 16 / 9,
            "9:16": 9 / 16,
            "4:3": 4 / 3,
            "3:4": 3 / 4,
            "3:2": 3 / 2,
            "2:3": 2 / 3,
            "4:5": 4 / 5,
            "5:4": 5 / 4,
        }.get(request.aspect_ratio, 1.0)

        actual = dimensions[0] / dimensions[1]
        return abs(actual - requested) <= 0.035

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.api_key:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=request.model or self.default_model,
                error_code="missing_api_key",
                error_message="NVIDIA API key is not configured.",
                permanent=True,
            )

        model = request.model or self.default_model

        dimensions = closest_supported_dimensions(
            request.aspect_ratio,
            self._SUPPORTED_FLUX2_RESOLUTIONS,
        )
        if dimensions is None:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=model,
                error_code="unsupported_aspect_ratio",
                error_message="NVIDIA does not have a compatible resolution for the requested aspect ratio.",
                permanent=True,
            )

        width, height = dimensions
        payload: dict[str, Any] = {
            "mode": "Image Generation",
            "prompt": request.prompt,
            "height": height,
            "width": width,
            "seed": request.seed if request.seed is not None else 0,
            "steps": 4,
        }

        started = time.monotonic()

        try:
            response = _http_json(
                url=f"{self.base_url}/{model}",
                payload=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )

            b64 = _walk_for_b64(response)
            if not b64:
                raise ImageProviderError(
                    "NVIDIA returned no image artifact.",
                    code="invalid_provider_response",
                    retryable=True,
                )

            data, mime_type = _decode_base64(b64)

            output_file = request.output_file
            if output_file is None:
                raise ImageProviderError(
                    "Image output path was not supplied by the tool.",
                    code="invalid_configuration",
                    permanent=True,
                )

            path, mime_type = _write_artifact(
                data=data,
                output_file=output_file,
                mime_type=mime_type or "image/png",
            )

            return ImageGenerationResult(
                success=True,
                provider=self.name,
                model=model,
                image_path=str(path),
                mime_type=mime_type,
                request_id=str(response.get("id")) if response.get("id") else None,
                width=width,
                height=height,
                generation_time_seconds=round(time.monotonic() - started, 3),
            )

        except ImageProviderError as exc:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=model,
                error_code=exc.code,
                error_message=str(exc),
                retryable=exc.retryable,
                permanent=exc.permanent,
                metadata={"provider_status": exc.provider_status, **exc.details},
            )


class LocalSDProvider:
    """Local stable-diffusion.cpp emergency provider."""

    name = "local_sd"

    def __init__(
        self,
        *,
        binary_path: str | None = None,
        model_path: str | None = None,
        timeout: float = 600.0,
    ) -> None:
        self.binary_path = binary_path or os.getenv("LOCAL_SD_BINARY", "")
        self.model_path = model_path or os.getenv("LOCAL_SD_MODEL", "")
        self.timeout = timeout
        self.model_argument = os.getenv("LOCAL_SD_MODEL_ARGUMENT", "-m")
        self.steps = int(os.getenv("LOCAL_SD_STEPS", "8"))

    def supports(self, request: ImageGenerationRequest) -> bool:
        # The adapter itself is capable of all normal text-to-image ratios and
        # tiers. Runtime availability is checked in generate().
        return True

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.binary_path or not self.model_path:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model="local_sd",
                error_code="invalid_configuration",
                error_message="LOCAL_SD_BINARY and LOCAL_SD_MODEL must be configured.",
                permanent=True,
            )

        binary = Path(self.binary_path)
        model = Path(self.model_path)

        if not binary.exists():
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=str(model),
                error_code="binary_not_found",
                error_message="stable-diffusion.cpp binary was not found.",
                permanent=True,
            )

        if not model.exists():
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=str(model),
                error_code="model_not_found",
                error_message="stable-diffusion.cpp model was not found.",
                permanent=True,
            )

        output_file = request.output_file
        if output_file is None:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=str(model),
                error_code="invalid_configuration",
                error_message="Image output path was not supplied by the tool.",
                permanent=True,
            )

        width, height = aspect_to_dimensions(
            request.aspect_ratio,
            "512" if request.image_size == "512" else "1K",
        )

        # Keep the local emergency path conservative. Large 2K/4K requests
        # intentionally stay external; the local adapter remains lightweight.
        if width > 1344 or height > 1344:
            scale = 1344 / max(width, height)
            width = int(width * scale) // 2 * 2
            height = int(height * scale) // 2 * 2

        command = [
            str(binary),
            self.model_argument,
            str(model),
            "-p",
            request.prompt,
            "-W",
            str(width),
            "-H",
            str(height),
            "--steps",
            str(self.steps),
            "-o",
            str(output_file),
            "--backend",
            "cpu",
        ]

        if request.negative_prompt:
            command.extend(["-n", request.negative_prompt])

        if request.seed is not None:
            command.extend(["--seed", str(request.seed)])

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=str(binary.parent),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=str(model),
                error_code="timeout",
                error_message="Local image generation timed out.",
                retryable=True,
            )
        except OSError as exc:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=str(model),
                error_code="process_error",
                error_message="stable-diffusion.cpp could not be started.",
                permanent=True,
                metadata={"error_type": type(exc).__name__},
            )

        if completed.returncode != 0:
            diagnostic = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "stable-diffusion.cpp exited with an error."
            )
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=str(model),
                error_code="local_generation_failed",
                error_message="Local image generation failed.",
                retryable=False,
                metadata={"process_output": diagnostic[-1600:]},
            )

        if not output_file.exists() or output_file.stat().st_size <= 0:
            return ImageGenerationResult(
                success=False,
                provider=self.name,
                model=str(model),
                error_code="artifact_write_failed",
                error_message="stable-diffusion.cpp completed but no image artifact was found.",
                retryable=False,
            )

        return ImageGenerationResult(
            success=True,
            provider=self.name,
            model=str(model),
            image_path=str(output_file),
            mime_type="image/png",
            width=width,
            height=height,
            generation_time_seconds=round(time.monotonic() - started, 3),
            metadata={"backend": "cpu"},
        )
