from collections.abc import AsyncIterator, Iterator


async def async_chunk_stream(
    chunks: Iterator[str],
) -> AsyncIterator[str]:
    """
    Convert a synchronous iterator into an async chunk stream.

    This helper is kept small and provider-agnostic. The actual provider
    execution is handled by ZoyaChatService so synchronous AI SDK calls
    never block FastAPI's event loop.
    """
    for chunk in chunks:
        yield chunk