"""Deterministic gap attribution into ranked drivers."""

from __future__ import annotations

from typing import Any

from core.locale import Language, topic as localize_topic, txt
from services.ai_facts.models import Driver
from services.ai_thresholds import PASS_RATE_THRESHOLD


def _pass_rate(rows: list[dict], key: str = "passRate") -> list[tuple[str, float, int]]:
    out = []
    for row in rows or []:
        label = row.get("course") or row.get("college") or row.get("entity") or "?"
        value = row.get(key)
        if value is None:
            continue
        n = int(row.get("participants") or row.get("students") or row.get("n") or 0)
        out.append((str(label), float(value), n))
    return out


def attribute_gap(
    *,
    scope_pass_rate: float | None,
    benchmark_pass_rate: float | None,
    courses: list[dict],
    sections: list[dict] | None = None,
    topics: list[dict] | None = None,
    yoy: list[dict] | None = None,
    language: Language = "en",
) -> list[Driver]:
    """Decompose (benchmark - scope) into ranked positive contributions.

    contribution_points are percentage points of pass-rate gap explained.
    """
    drivers: list[Driver] = []
    if scope_pass_rate is None:
        return drivers
    benchmark = (
        float(benchmark_pass_rate)
        if benchmark_pass_rate is not None
        else PASS_RATE_THRESHOLD
    )
    gap = benchmark - float(scope_pass_rate)
    if gap <= 0.5:
        return drivers

    course_rows = _pass_rate(courses)
    # Weight by how far below threshold and by participants.
    weighted = []
    for label, rate, n in course_rows:
        shortfall = max(0.0, PASS_RATE_THRESHOLD - rate)
        if shortfall <= 0:
            continue
        weight = shortfall * max(n, 1)
        weighted.append((label, shortfall, weight, n))
    total_w = sum(w for _, _, w, _ in weighted) or 1.0
    for label, shortfall, weight, n in sorted(weighted, key=lambda x: -x[2])[:5]:
        contrib = gap * (weight / total_w)
        drivers.append(
            Driver(
                label=txt(language, f"Course {label}", f"مقرر {label}"),
                contribution_points=round(contrib, 2),
                evidence_refs=[
                    f"{label} shortfall {shortfall:g} pts vs review line",
                    f"students_or_attempts={n}",
                ],
                kind="course",
            )
        )

    for row in sections or []:
        label = row.get("section") or row.get("label")
        delta = row.get("delta")
        if label is None or delta is None:
            continue
        if float(delta) >= 5:
            drivers.append(
                Driver(
                    label=txt(language, f"Section {label}", f"شعبة {label}"),
                    contribution_points=round(min(gap * 0.25, float(delta) * 0.4), 2),
                    evidence_refs=[f"section_delta={float(delta):g}"],
                    kind="section",
                )
            )

    for row in topics or []:
        label = row.get("topic") or row.get("label")
        rate = row.get("correct_rate")
        if label is None or rate is None:
            continue
        if float(rate) <= 0.35:
            topic_label = localize_topic(language, str(label))
            drivers.append(
                Driver(
                    label=txt(language, f"Topic {topic_label}", f"موضوع {topic_label}"),
                    contribution_points=round(gap * 0.2, 2),
                    evidence_refs=[f"correct_rate={float(rate):g}"],
                    kind="topic",
                )
            )

    for row in yoy or []:
        label = row.get("label") or txt(language, "Year-over-year", "التغيّر السنوي")
        delta = row.get("delta")
        if delta is None:
            continue
        if float(delta) <= -5:
            drivers.append(
                Driver(
                    label=str(label),
                    contribution_points=round(
                        min(gap * 0.3, abs(float(delta)) * 0.5), 2
                    ),
                    evidence_refs=[f"yoy_delta={float(delta):g}"],
                    kind="yoy",
                )
            )

    drivers.sort(key=lambda d: -d.contribution_points)
    # Renormalize top drivers to not exceed gap by much.
    s = sum(d.contribution_points for d in drivers) or 1.0
    if s > gap * 1.2:
        scale = gap / s
        for d in drivers:
            d.contribution_points = round(d.contribution_points * scale, 2)
    return drivers


def extract_section_topic_signals(
    ctx_data: dict[str, Any],
) -> tuple[list[dict], list[dict]]:
    """Optional signals from item analysis / course performance if present.

    ``load_ai_context`` stores payloads under ``courses`` / ``items``; older
    aliases are still accepted.
    """
    sections: list[dict] = []
    topics: list[dict] = []
    course_perf = (
        ctx_data.get("courses")
        or ctx_data.get("coursePerformance")
        or ctx_data.get("course_performance")
        or {}
    )
    raw_sections = course_perf.get("bySection") or course_perf.get("sections") or []
    means = [
        float(row["average"]) for row in raw_sections if row.get("average") is not None
    ]
    overall = (sum(means) / len(means)) if means else None
    for row in raw_sections:
        section = dict(row)
        if section.get("delta") is None and overall is not None:
            avg = section.get("average")
            if avg is not None:
                section["delta"] = abs(float(avg) - overall)
        sections.append(section)

    item = (
        ctx_data.get("items")
        or ctx_data.get("itemAnalysis")
        or ctx_data.get("item_analysis")
        or {}
    )
    topic_rows = item.get("byTopic") or item.get("topics") or []
    if not topic_rows:
        # Derive topic rates from question rows when topic aggregates are absent.
        by_topic: dict[str, list[float]] = {}
        for q in item.get("questions") or item.get("needsReview") or []:
            topic = q.get("topic") or q.get("name")
            if not topic:
                continue
            pct = q.get("pctCorrect")
            if pct is None and q.get("correct_rate") is not None:
                pct = float(q["correct_rate"]) * 100.0
            if pct is None and q.get("correctRate") is not None:
                pct = float(q["correctRate"]) * (
                    100.0 if float(q["correctRate"]) <= 1.0 else 1.0
                )
            if pct is None:
                continue
            rate = float(pct) / 100.0 if float(pct) > 1.0 else float(pct)
            by_topic.setdefault(str(topic), []).append(rate)
        topic_rows = [
            {"topic": name, "correct_rate": sum(vals) / len(vals)}
            for name, vals in by_topic.items()
        ]
    for row in topic_rows:
        rate = row.get("correctRate") or row.get("correct_rate")
        if rate is None and row.get("pctCorrect") is not None:
            rate = float(row["pctCorrect"]) / 100.0
        if rate is not None and float(rate) > 1.0:
            rate = float(rate) / 100.0
        topics.append(
            {
                "topic": row.get("topic") or row.get("name"),
                "correct_rate": rate,
            }
        )
    return sections, topics
