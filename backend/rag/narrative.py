"""Optional wording layer. Numbers stay on the deterministic decision."""

import json
import re
from typing import Any

from core.config import settings
from rag.errors import LlmNotConfigured, LlmUpstreamError
from rag.llm_client import chat_completion

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def _safe_text(original: str, rewritten: str, corpus: str) -> str:
    if not rewritten or not rewritten.strip():
        return original
    if not _numbers(rewritten) <= _numbers(corpus):
        return original
    return rewritten.strip()


async def apply_llm_narratives(result: dict[str, Any]) -> dict[str, Any]:
    """Rephrase insight, standing, and recommendation text when explicitly enabled.

    Warning rows are produced by the deterministic rules before this runs.
    This function never adds a warning, a prediction row, or a metric.
    """
    if not settings.AI_NARRATIVE_ENABLED or not settings.LLM_API_KEY:
        return result
    corpus = json.dumps(result, default=str)
    if not _numbers(corpus):
        return result

    try:
        raw = await chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Rewrite the supplied academic narrative in plain language. "
                        "Return JSON with optional keys insight_body, prediction_summary, "
                        "and recommendation_texts (a list of strings in the same order). "
                        "Use only numbers that already appear in the input. "
                        "If the input says the data is insufficient, keep that meaning. "
                        "Do not add warnings, people, or metrics."
                    ),
                },
                {"role": "user", "content": corpus},
            ],
            temperature=0.2,
        )
    except (LlmNotConfigured, LlmUpstreamError):
        return result

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return result
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return result
    if not isinstance(payload, dict):
        return result

    insight = result.get("insight")
    if insight and isinstance(payload.get("insight_body"), str):
        insight["body"] = _safe_text(
            insight.get("body") or "", payload["insight_body"], corpus
        )
    prediction = result.get("prediction")
    if prediction and isinstance(payload.get("prediction_summary"), str):
        prediction["summary"] = _safe_text(
            prediction.get("summary") or "",
            payload["prediction_summary"],
            corpus,
        )
    recommendations = result.get("recommendations") or {}
    items = recommendations.get("items") if isinstance(recommendations, dict) else None
    texts = payload.get("recommendation_texts")
    if isinstance(items, list) and isinstance(texts, list):
        for item, text in zip(items, texts):
            if isinstance(item, dict) and isinstance(text, str):
                item["text"] = _safe_text(item.get("text") or "", text, corpus)
    return result
