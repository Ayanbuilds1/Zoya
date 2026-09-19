class ZoyaError(Exception):
    """Base exception for Zoya application errors."""


class AIServiceError(ZoyaError):
    """Raised when the AI service cannot produce a response."""

    def __init__(
        self,
        message: str,
        user_message: str | None = None,
        failed_providers: list[str] | None = None,
    ) -> None:
        super().__init__(message)

        self.user_message = (
            user_message
            or "Zoya AI service is temporarily unavailable."
        )

        self.failed_providers = failed_providers or []


class AIProviderError(ZoyaError):
    """Raised when an individual AI provider fails."""

    def __init__(
        self,
        provider: str,
        message: str,
        is_retryable: bool = True,
    ) -> None:
        super().__init__(message)

        self.provider = provider
        self.is_retryable = is_retryable