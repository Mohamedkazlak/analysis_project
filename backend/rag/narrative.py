"""Optional wording layer. Numbers stay on the deterministic decision.

Narration always runs after the deterministic decision has already been
cached and served (see `services.ai_insights`), so a slow model can never
hold up a dashboard card. Each sentence is rewritten on its own, one at a
time, instead of asking the model to edit several fields in a single JSON
reply: the configured model keeps reasoning even when asked not to, and
that cost compounds with every extra field in one prompt. A failed or slow
step only leaves that one sentence as the original SQL wording.
"""

import asyncio
import re
from typing import Any

from core.config import settings
from rag.errors import LlmNotConfigured, LlmUpstreamError
from rag.llm_client import chat_completion

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# The configured model is one slow shared instance. Concurrent calls make
# every one of them slower, so narration queues through this many slots.
_NARRATION_SLOT = asyncio.Semaphore(max(1, settings.AI_NARRATIVE_MAX_CONCURRENCY))

_REWRITE_SYSTEM = (
    "Rewrite this academic insight in one or two plain sentences. "
    "Use only numbers already in the text. "
    "Do not add a cause, a forecast, a person, or a metric that is not already there."
)


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def _safe_text(original: str, rewritten: str, corpus: str) -> str:
    if not rewritten or not rewritten.strip():
        return original
    if not _numbers(rewritten) <= _numbers(corpus):
        return original
    return rewritten.strip()


def narration_enabled() -> bool:
    return bool(
        settings.AI_NARRATIVE_ENABLED
        and settings.LLM_API_KEY
        and settings.LLM_BASE_URL
        and settings.LLM_MODEL
    )


async def narrate_sentence(text: str) -> str:
    """Rephrase one SQL sentence.

    A new number, a JSON-shaped reply, or a slow/failed model all fall back
    to the original sentence untouched.
    """
    original = (text or "").strip()
    if not original or not narration_enabled():
        return text
    try:
        async with _NARRATION_SLOT:
            raw = await chat_completion(
                [
                    {"role": "system", "content": _REWRITE_SYSTEM},
                    {"role": "user", "content": original},
                ],
                temperature=0.2,
                max_tokens=300,
                timeout=settings.AI_NARRATIVE_TIMEOUT_SECONDS,
            )
    except (LlmNotConfigured, LlmUpstreamError):
        return text
    rewritten = raw.strip()
    if rewritten.startswith("{"):
        return text
    return _safe_text(original, rewritten, original)


def _rewrite_targets(result: dict[str, Any]) -> list[tuple[tuple, str]]:
    """(path, text) for every sentence eligible for narration, in read order."""
    targets: list[tuple[tuple, str]] = []
    insight = result.get("insight")
    if isinstance(insight, dict):
        if isinstance(insight.get("headline"), str) and insight["headline"]:
            targets.append((("insight", "headline"), insight["headline"]))
        if isinstance(insight.get("body"), str) and insight["body"]:
            targets.append((("insight", "body"), insight["body"]))
        warnings = insight.get("warnings")
        if isinstance(warnings, list):
            for i, warning in enumerate(warnings):
                if (
                    isinstance(warning, dict)
                    and isinstance(warning.get("text"), str)
                    and warning["text"]
                ):
                    targets.append(
                        (("insight", "warnings", i, "text"), warning["text"])
                    )
    prediction = result.get("prediction")
    if (
        isinstance(prediction, dict)
        and isinstance(prediction.get("summary"), str)
        and prediction["summary"]
    ):
        targets.append((("prediction", "summary"), prediction["summary"]))
    recommendations = result.get("recommendations")
    if isinstance(recommendations, dict):
        items = recommendations.get("items")
        if isinstance(items, list):
            for i, item in enumerate(items):
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("text"), str)
                    and item["text"]
                ):
                    targets.append(
                        (("recommendations", "items", i, "text"), item["text"])
                    )
    return targets


def has_narratable_text(result: dict[str, Any]) -> bool:
    return bool(_rewrite_targets(result))


def _set_path(result: dict[str, Any], path: tuple, value: str) -> None:
    node: Any = result
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


async def apply_llm_narratives(result: dict[str, Any]) -> dict[str, Any]:
    """Rephrase insight, standing, warnings, and recommendations, one sentence
    at a time.

    The rows, evidence, and which warnings/recommendations exist are already
    fixed. This never adds a warning, a recommendation, a prediction row, or
    a metric.
    """
    if not narration_enabled():
        return result
    for path, text in _rewrite_targets(result):
        _set_path(result, path, await narrate_sentence(text))
    return result
