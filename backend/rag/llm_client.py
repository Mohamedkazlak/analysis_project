import httpx

from core.config import settings
from rag.errors import LlmNotConfigured, LlmUpstreamError


async def chat_completion(messages: list[dict], temperature: float = 0.1) -> str:
    """OpenAI-compatible chat call. The key stays on the server."""
    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL or not settings.LLM_MODEL:
        raise LlmNotConfigured()
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json={
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise LlmUpstreamError() from exc
    except ValueError as exc:
        raise LlmUpstreamError() from exc
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmUpstreamError() from exc
    if not isinstance(content, str) or not content.strip():
        raise LlmUpstreamError()
    return content
