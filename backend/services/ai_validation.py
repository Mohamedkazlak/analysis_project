"""Reject narration that is not supported by the deterministic decision.

A failed check drops that sentence back to the SQL wording. The warning list,
recommendation list, prediction numbers, and severities are never edited here.
"""

from __future__ import annotations

import re
from typing import Any

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_ENTITY = re.compile(r"\b[A-Z][A-Za-z0-9][A-Za-z0-9'’.-]*")
_CAUSE = re.compile(
    r"\b(because|due to|caused by|as a result|therefore|which usually)\b",
    re.IGNORECASE,
)
_SEVERITY = re.compile(r"\b(critical|severe|urgent)\b", re.IGNORECASE)
_FALLING = re.compile(
    r"\b(declin\w*|falling|dropped|worse|decreas\w*)\b", re.IGNORECASE
)
_RISING = re.compile(r"\b(rising|improv\w*|increas\w*)\b", re.IGNORECASE)

# Ordinary words a rewrite may capitalize. Proper nouns must already be in
# the evidence or the original sentence.
_GENERIC = {
    "across",
    "after",
    "attendance",
    "attempt",
    "attempts",
    "average",
    "averages",
    "below",
    "class",
    "college",
    "colleges",
    "course",
    "courses",
    "current",
    "curriculum",
    "data",
    "exam",
    "exams",
    "fewer",
    "flagged",
    "forecast",
    "from",
    "high",
    "history",
    "index",
    "insight",
    "interval",
    "item",
    "linear",
    "low",
    "medium",
    "monitored",
    "next",
    "observation",
    "observations",
    "pass",
    "period",
    "performance",
    "point",
    "points",
    "professor",
    "projected",
    "projection",
    "question",
    "questions",
    "rate",
    "recommendation",
    "recorded",
    "review",
    "scope",
    "section",
    "sections",
    "showing",
    "standing",
    "student",
    "students",
    "term",
    "the",
    "there",
    "this",
    "threshold",
    "warning",
    "warnings",
    "within",
    "year",
    "yearly",
    "your",
}


def number_forms(value: Any) -> set[str]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return set()
    forms = {str(value), str(number), f"{number:.1f}", f"{number:.2f}"}
    if number.is_integer():
        forms.add(str(int(number)))
    trimmed = f"{number:.2f}".rstrip("0").rstrip(".")
    forms.add(trimmed)
    return {form for form in forms if form}


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text or ""))


def evidence_corpus(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for metric in result.get("evidence") or []:
        if not isinstance(metric, dict):
            continue
        parts.append(str(metric.get("entity") or ""))
        parts.append(str(metric.get("name") or ""))
        parts.extend(number_forms(metric.get("value")))
        comparison = metric.get("comparison") or {}
        if isinstance(comparison, dict):
            parts.append(str(comparison.get("name") or ""))
            parts.extend(number_forms(comparison.get("scopeAverage")))
    for warning in result.get("warnings") or []:
        if isinstance(warning, dict):
            parts.append(str(warning.get("entity") or ""))
            parts.append(str(warning.get("text") or ""))
            parts.append(str(warning.get("severity") or ""))
            parts.extend(number_forms(warning.get("value")))
            parts.extend(number_forms(warning.get("threshold")))
    prediction = result.get("prediction") or {}
    if isinstance(prediction, dict):
        parts.extend(number_forms(prediction.get("forecastValue")))
        parts.extend(number_forms(prediction.get("intervalLow")))
        parts.extend(number_forms(prediction.get("intervalHigh")))
        for row in prediction.get("rows") or []:
            if isinstance(row, dict):
                parts.append(str(row.get("label") or ""))
                parts.append(str(row.get("value") or ""))
    recommendations = result.get("recommendations") or {}
    if isinstance(recommendations, dict):
        for item in recommendations.get("items") or []:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
                parts.extend(number_forms(item.get("value")))
                parts.extend(number_forms(item.get("threshold")))
    return " ".join(part for part in parts if part)


def _entities_ok(rewritten: str, corpus: str) -> bool:
    corpus_l = corpus.lower()
    for match in _ENTITY.finditer(rewritten or ""):
        token = match.group(0)
        lowered = token.lower()
        if lowered in _GENERIC:
            continue
        if lowered in corpus_l or token in corpus:
            continue
        return False
    return True


def _direction_ok(prediction: dict | None, original: str, rewritten: str) -> bool:
    if not isinstance(prediction, dict):
        return True
    direction = prediction.get("direction")
    if (
        direction == "rising"
        and _FALLING.search(rewritten)
        and not _FALLING.search(original)
    ):
        return False
    if (
        direction == "falling"
        and _RISING.search(rewritten)
        and not _RISING.search(original)
    ):
        return False
    return True


def _forecast_ok(prediction: dict | None, rewritten: str, *, summary: bool) -> bool:
    if not summary or not isinstance(prediction, dict):
        return True
    if prediction.get("kind") != "forecast":
        return True
    forms = number_forms(prediction.get("forecastValue"))
    if not forms:
        return True
    return any(form in rewritten for form in forms)


def narration_is_valid(
    original: str,
    rewritten: str,
    corpus: str,
    *,
    prediction: dict | None = None,
    summary: bool = False,
) -> tuple[bool, str]:
    cleaned = (rewritten or "").strip()
    if not cleaned or cleaned.startswith("{") or cleaned.startswith("["):
        return False, "malformed"
    allowed = _numbers(original) | _numbers(corpus)
    if not _numbers(cleaned) <= allowed:
        return False, "numbers"
    if not _entities_ok(cleaned, f"{original}\n{corpus}"):
        return False, "entities"
    if _CAUSE.search(cleaned) and not _CAUSE.search(original):
        return False, "cause"
    if _SEVERITY.search(cleaned) and not _SEVERITY.search(original):
        return False, "severity"
    if summary and not _direction_ok(prediction, original, cleaned):
        return False, "direction"
    if not _forecast_ok(prediction, cleaned, summary=summary):
        return False, "prediction"
    return True, "ok"
