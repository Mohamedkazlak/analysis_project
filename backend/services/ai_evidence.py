"""Structured evidence for one authorized AI decision.

Metrics are copied from repository results that were already calculated in SQL.
This module does not query the database and does not invent a value when the
underlying dataset is empty.
"""

from __future__ import annotations

from typing import Any, Optional

from services.predictions import is_university_landing


def _metric(
    name: str,
    value: Any,
    *,
    entity: Optional[str] = None,
    unit: str = "percent",
    dataset: str,
    comparison: Optional[dict] = None,
) -> dict:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return {}
    return {
        "id": f"{dataset}:{name}:{entity or 'scope'}",
        "name": name,
        "entity": entity,
        "value": number,
        "unit": unit,
        "source": "deterministic_sql",
        "dataset": dataset,
        "comparison": comparison,
    }


def _scope_average(rows: list[dict], key: str) -> Optional[float]:
    values = []
    for row in rows:
        try:
            values.append(float(row[key]))
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _add(metrics: list[dict], item: dict) -> None:
    if item:
        metrics.append(item)


def build_evidence(role: str, data: dict[str, Any]) -> list[dict]:
    """Return the metrics this role can actually see in `data`."""
    metrics: list[dict] = []

    if role == "student":
        dashboard = data.get("dashboard") or {}
        average = dashboard.get("average")
        class_average = dashboard.get("classAverage")
        if average is None or not dashboard.get("scoreTimeline"):
            return []
        comparison = None
        if class_average is not None:
            comparison = {
                "name": "class_average",
                "scopeAverage": float(class_average),
            }
        _add(
            metrics,
            _metric(
                "average",
                average,
                entity=dashboard.get("studentName") or "You",
                dataset="student_dashboard",
                comparison=comparison,
            ),
        )
        if class_average is not None:
            _add(
                metrics,
                _metric(
                    "class_average",
                    class_average,
                    entity="class",
                    dataset="student_dashboard",
                ),
            )
        overall = dashboard.get("overallAverage")
        if overall is not None:
            _add(
                metrics,
                _metric(
                    "overall_average",
                    overall,
                    entity=dashboard.get("studentName") or "You",
                    dataset="transcript_entries",
                ),
            )
        for row in dashboard.get("scoreTimeline") or []:
            _add(
                metrics,
                _metric(
                    "exam_score",
                    row.get("score"),
                    entity=row.get("exam"),
                    dataset="scoreTimeline",
                    comparison=(
                        {
                            "name": "class_average",
                            "scopeAverage": float(row["classAverage"]),
                        }
                        if row.get("classAverage") is not None
                        else None
                    ),
                ),
            )
        for row in dashboard.get("topics") or []:
            _add(
                metrics,
                _metric(
                    "topic_score",
                    row.get("score"),
                    entity=row.get("topic"),
                    dataset="topics",
                ),
            )
        return metrics[:24]

    if role in ("senior_management", "program_director"):
        overview = data.get("overview") or {}
        colleges = overview.get("passRateByCollege") or []
        courses = overview.get("passRateByCourse") or []
        totals = overview.get("totals") or {}
        if is_university_landing(role, data) and totals.get("passRate") is not None:
            _add(
                metrics,
                _metric(
                    "pass_rate",
                    totals.get("passRate"),
                    entity="University",
                    dataset="totals",
                ),
            )
            if totals.get("attendance") is not None:
                _add(
                    metrics,
                    _metric(
                        "attendance_rate",
                        totals.get("attendance"),
                        entity="University",
                        dataset="totals",
                    ),
                )
            if totals.get("students") is not None:
                _add(
                    metrics,
                    _metric(
                        "students",
                        totals.get("students"),
                        entity="University",
                        unit="count",
                        dataset="totals",
                    ),
                )
        scope = _scope_average(colleges, "passRate")
        for row in colleges:
            _add(
                metrics,
                _metric(
                    "pass_rate",
                    row.get("passRate"),
                    entity=row.get("college"),
                    dataset="passRateByCollege",
                    comparison=(
                        {"name": "pass_rate", "scopeAverage": scope}
                        if scope is not None
                        else None
                    ),
                ),
            )
            _add(
                metrics,
                _metric(
                    "participants",
                    row.get("participants"),
                    entity=row.get("college"),
                    unit="count",
                    dataset="passRateByCollege",
                ),
            )
        for row in courses[:12]:
            _add(
                metrics,
                _metric(
                    "pass_rate",
                    row.get("passRate"),
                    entity=row.get("course"),
                    dataset="passRateByCourse",
                ),
            )
        integrity = data.get("integrity") or {}
        if integrity.get("totalAttempts"):
            _add(
                metrics,
                _metric(
                    "flagged_attempts",
                    integrity.get("flaggedCount") or 0,
                    unit="count",
                    dataset="integrity",
                    comparison={
                        "name": "monitored_attempts",
                        "scopeAverage": float(integrity["totalAttempts"]),
                    },
                ),
            )
        items = data.get("items") or {}
        for row in (items.get("needsReview") or [])[:3]:
            _add(
                metrics,
                _metric(
                    "discrimination_index",
                    row.get("discriminationIndex"),
                    entity=f"{row.get('exam')} Q{row.get('number')}",
                    unit="index",
                    dataset="item_analysis",
                ),
            )
        participation = data.get("participation") or {}
        if participation.get("attendanceRate") is not None:
            _add(
                metrics,
                _metric(
                    "attendance_rate",
                    participation.get("attendanceRate"),
                    dataset="participation",
                ),
            )
        for row in (participation.get("attendanceByCurriculum") or [])[:12]:
            _add(
                metrics,
                _metric(
                    "attendance_rate",
                    row.get("attendance"),
                    entity=row.get("course"),
                    dataset="attendanceByCurriculum",
                ),
            )
        performance = data.get("performance") or {}
        below = [
            row
            for row in performance.get("ranked") or []
            if row.get("status") == "Fail"
        ]
        if performance.get("ranked"):
            _add(
                metrics,
                _metric(
                    "students_below_pass",
                    len(below),
                    unit="count",
                    dataset="student_performance",
                ),
            )
        return metrics[:24]

    if role == "academic_affairs":
        participation = data.get("participation") or {}
        performance = data.get("performance") or {}
        if participation.get("attendanceRate") is not None:
            _add(
                metrics,
                _metric(
                    "attendance_rate",
                    participation.get("attendanceRate"),
                    dataset="participation",
                ),
            )
        for row in participation.get("attendanceByCurriculum") or []:
            _add(
                metrics,
                _metric(
                    "attendance_rate",
                    row.get("attendance"),
                    entity=row.get("course"),
                    dataset="attendanceByCurriculum",
                ),
            )
        below = [
            row
            for row in performance.get("ranked") or []
            if row.get("status") == "Fail"
        ]
        if performance.get("ranked"):
            _add(
                metrics,
                _metric(
                    "students_below_pass",
                    len(below),
                    unit="count",
                    dataset="student_performance",
                ),
            )
        return metrics[:24]

    if role == "professor":
        sections = (data.get("courses") or {}).get("sections") or []
        scope = _scope_average(sections, "average")
        for row in sections:
            _add(
                metrics,
                _metric(
                    "section_average",
                    row.get("average"),
                    entity=row.get("section"),
                    dataset="sections",
                    comparison=(
                        {"name": "section_average", "scopeAverage": scope}
                        if scope is not None
                        else None
                    ),
                ),
            )
            _add(
                metrics,
                _metric(
                    "pass_rate",
                    row.get("passRate"),
                    entity=row.get("section"),
                    dataset="sections",
                ),
            )
        for row in (data.get("participation") or {}).get(
            "attendanceByCurriculum"
        ) or []:
            _add(
                metrics,
                _metric(
                    "attendance_rate",
                    row.get("attendance"),
                    entity=row.get("course"),
                    dataset="attendanceByCurriculum",
                ),
            )
        for row in ((data.get("items") or {}).get("needsReview") or [])[:3]:
            _add(
                metrics,
                _metric(
                    "discrimination_index",
                    row.get("discriminationIndex"),
                    entity=f"{row.get('exam')} Q{row.get('number')}",
                    unit="index",
                    dataset="item_analysis",
                ),
            )
        return metrics[:24]

    if role == "it_academic_integrity":
        report = data.get("integrity") or {}
        if report.get("totalAttempts"):
            _add(
                metrics,
                _metric(
                    "flagged_attempts",
                    report.get("flaggedCount") or 0,
                    unit="count",
                    dataset="integrity",
                    comparison={
                        "name": "monitored_attempts",
                        "scopeAverage": float(report["totalAttempts"]),
                    },
                ),
            )
            _add(
                metrics,
                _metric(
                    "monitored_attempts",
                    report.get("totalAttempts"),
                    unit="count",
                    dataset="integrity",
                ),
            )
        for row in (data.get("flagged") or [])[:3]:
            _add(
                metrics,
                _metric(
                    "integrity_signals",
                    len(row.get("evidence") or []),
                    entity=row.get("student"),
                    unit="count",
                    dataset="flagged_attempts",
                ),
            )
        return [m for m in metrics if m][:24]

    return []
