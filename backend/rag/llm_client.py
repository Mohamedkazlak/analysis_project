import re

import httpx

from core.config import settings
from rag.errors import LlmNotConfigured, LlmUpstreamError

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def _visible(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _THINK_BLOCK.sub("", value).strip()


def _message_text(message: object, *, sql: bool = False) -> str:
    """For SQL, a finished SELECT may sit in the reasoning channel."""
    if not isinstance(message, dict):
        return ""
    content = _visible(message.get("content"))
    if not sql:
        return content
    reasoning = _visible(message.get("reasoning_content"))
    if re.search(r"\bfrom\b", content, re.IGNORECASE):
        return content
    if re.search(r"\bfrom\b", reasoning, re.IGNORECASE):
        return reasoning
    return content or reasoning


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int | None = None,
    *,
    sql: bool = False,
    timeout: float | None = None,
) -> str:
    """OpenAI-compatible chat call. The key stays on the server.

    Thinking is disabled and max_tokens is capped so one completion finishes
    and releases the model server for the next question.
    """
    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL or not settings.LLM_MODEL:
        raise LlmNotConfigured()
    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    body: dict = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    try:
        async with httpx.AsyncClient(
            timeout=settings.LLM_TIMEOUT_SECONDS if timeout is None else timeout
        ) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise LlmUpstreamError() from exc
    except ValueError as exc:
        raise LlmUpstreamError() from exc
    try:
        content = _message_text(payload["choices"][0]["message"], sql=sql)
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmUpstreamError() from exc
    if not content:
        raise LlmUpstreamError()
    return content
