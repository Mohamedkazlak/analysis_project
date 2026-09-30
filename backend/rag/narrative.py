"""Optional wording layer. Facts stay on the deterministic decision.

Narration always runs after the deterministic decision has already been
cached and served (see `services.ai_insights`), so a slow model can never
hold up a dashboard card. Every SQL sentence goes out in one model call.
A failed, malformed, or ungrounded reply leaves that sentence as the
original SQL wording. Validation failures are logged and never shown.
"""

import asyncio
import json
import logging
from typing import Any

from core.config import settings
from core.locale import Language, normalize_language
from rag.errors import LlmNotConfigured, LlmUpstreamError
from rag.llm_client import chat_completion
from services.ai_validation import evidence_corpus, narration_is_valid

logger = logging.getLogger(__name__)

# The configured model is one slow shared instance. Concurrent calls make
# every one of them slower, so narration queues through this many slots.
_NARRATION_SLOT = asyncio.Semaphore(max(1, settings.AI_NARRATIVE_MAX_CONCURRENCY))

_REWRITE_SYSTEM_EN = (
    "You narrate a university dashboard that was already calculated from the database. "
    "Rewrite each sentence in concise professional academic English. "
    "Use only numbers and names that already appear in that sentence or the evidence list. "
    "Do not calculate a new metric. Do not add a warning, a recommendation, a person, "
    "or a cause. Do not change whether a sentence is current standing or a forecast. "
    'Return JSON only: {"sentences":[{"id":"...","text":"..."}]} with the same ids.'
)

_REWRITE_SYSTEM_AR = (
    "You narrate a university dashboard that was already calculated from the database. "
    "Rewrite each sentence in concise professional academic Arabic (Modern Standard Arabic). "
    "Keep every number and proper name exactly as written; do not translate numbers into words. "
    "Use only numbers and names that already appear in that sentence or the evidence list. "
    "Do not calculate a new metric. Do not add a warning, a recommendation, a person, "
    "or a cause. Do not change whether a sentence is current standing or a forecast. "
    'Return JSON only: {"sentences":[{"id":"...","text":"..."}]} with the same ids.'
)


def _rewrite_system(language: Language) -> str:
    return _REWRITE_SYSTEM_AR if language == "ar" else _REWRITE_SYSTEM_EN


def narration_enabled() -> bool:
    return bool(
        settings.AI_NARRATIVE_ENABLED
        and settings.LLM_API_KEY
        and settings.LLM_BASE_URL
        and settings.LLM_MODEL
    )


def _narrative_timeout() -> float:
    """One call may use the background budget. It must end before that wait cancels it."""
    budget = settings.AI_NARRATIVE_BACKGROUND_BUDGET_SECONDS
    return max(settings.AI_NARRATIVE_TIMEOUT_SECONDS, budget - 5)


def _load_json_object(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _parse_rewrites(raw: str) -> dict[str, str]:
    payload = _load_json_object(raw)
    rows = payload.get("sentences") if payload else None
    if not isinstance(rows, list):
        return {}
    rewrites: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        sentence_id = row.get("id")
        text = row.get("text")
        if isinstance(sentence_id, (str, int)) and isinstance(text, str):
            rewrites[str(sentence_id)] = text
    return rewrites


def _decision_language(result: dict[str, Any]) -> Language:
    metadata = (
        result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    )
    return normalize_language(str(metadata.get("language") or "en"))


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
    """Rephrase insight, standing, warnings, and recommendations in one call.

    The rows, evidence, and which warnings/recommendations exist are already
    fixed. This never adds a warning, a recommendation, a prediction row, or
    a metric. A sentence the model changes with a new number stays as the
    SQL wording.
    """
    targets = _rewrite_targets(result)
    if not narration_enabled() or not targets:
        return result
    language = _decision_language(result)
    corpus = evidence_corpus(result)
    prediction = (
        result.get("prediction") if isinstance(result.get("prediction"), dict) else None
    )
    sentences = [
        {"id": str(index), "text": text} for index, (_, text) in enumerate(targets)
    ]
    user = f"Evidence:\n{corpus.strip()}\n\nSentences:\n{json.dumps(sentences, ensure_ascii=False)}"
    try:
        async with _NARRATION_SLOT:
            raw = await chat_completion(
                [
                    {"role": "system", "content": _rewrite_system(language)},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                max_tokens=900,
                timeout=_narrative_timeout(),
            )
    except (LlmNotConfigured, LlmUpstreamError):
        result["validation"] = {"status": "fallback", "failures": len(targets)}
        return result
    rewrites = _parse_rewrites(raw)
    failures = 0
    kept = 0
    for index, (path, text) in enumerate(targets):
        rewritten = rewrites.get(str(index), "").strip()
        if not rewritten:
            failures += 1
            continue
        summary = path[:2] == ("prediction", "summary")
        ok, reason = narration_is_valid(
            text,
            rewritten,
            f"{text}\n{corpus}",
            prediction=prediction,
            summary=summary,
        )
        if not ok:
            logger.warning("AI narration rejected (%s)", reason)
            failures += 1
            continue
        _set_path(result, path, rewritten)
        kept += 1
    result["validation"] = {
        "status": "fallback" if failures else "passed",
        "failures": failures,
    }
    if kept == 0 and failures == 0:
        result["validation"] = {"status": "not_run", "failures": 0}
    return result
