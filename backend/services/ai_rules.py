"""Deterministic warning rules.

The model may later reword `text`. It cannot add, remove, or re-rank these
warnings. Thresholds are configuration, not model output.
"""

from __future__ import annotations

from typing import Any, Optional

from core.utils import PASS_MARK

# Review line for a pass rate. Distinct from the student pass mark.
PASS_RATE_THRESHOLD = 70.0
# Medium attendance warning. High severity starts at the lower line.
ATTENDANCE_THRESHOLD = 80.0
ATTENDANCE_WATCH = 90.0
DISCRIMINATION_THRESHOLD = 0.2
DECLINE_THRESHOLD = 10.0


def _warning(
    rule: str,
    *,
    metric: str,
    value: float,
    threshold: float,
    severity: str,
    text: str,
    entity: Optional[str] = None,
) -> dict:
    return {
        "id": f"{rule}:{entity or 'scope'}:{value:g}",
        "rule": rule,
        "severity": severity,
        "tone": "rose" if severity == "high" else "amber",
        "metric": metric,
        "entity": entity,
        "value": float(value),
        "threshold": float(threshold),
        "text": text,
    }


def _metrics(evidence: list[dict], name: str) -> list[dict]:
    return [
        row
        for row in evidence
        if row.get("name") == name and row.get("value") is not None
    ]


def _lowest(rows: list[dict], limit: int = 5) -> list[dict]:
    return sorted(rows, key=lambda row: float(row["value"]))[:limit]


def build_warnings(role: str, evidence: list[dict], data: dict[str, Any]) -> list[dict]:
    """Warnings that follow from evidence already limited to this role."""
    if role == "student":
        return _student_warnings(evidence, data)
    warnings: list[dict] = []

    for row in _lowest(_metrics(evidence, "pass_rate")):
        value = float(row["value"])
        if value >= PASS_RATE_THRESHOLD:
            continue
        severity = "high" if value < PASS_MARK else "medium"
        entity = row.get("entity")
        warnings.append(
            _warning(
                "pass_rate_below_threshold",
                metric="pass_rate",
                entity=entity,
                value=value,
                threshold=PASS_RATE_THRESHOLD,
                severity=severity,
                text=(
                    f"{entity} pass rate is {value:g}%, below the "
                    f"{PASS_RATE_THRESHOLD:g}% review threshold."
                    if entity
                    else (
                        f"Pass rate is {value:g}%, below the "
                        f"{PASS_RATE_THRESHOLD:g}% review threshold."
                    )
                ),
            )
        )

    for row in _lowest(_metrics(evidence, "attendance_rate")):
        value = float(row["value"])
        if value >= ATTENDANCE_WATCH:
            continue
        severity = "high" if value < ATTENDANCE_THRESHOLD else "medium"
        entity = row.get("entity")
        threshold = ATTENDANCE_THRESHOLD if severity == "high" else ATTENDANCE_WATCH
        warnings.append(
            _warning(
                "attendance_below_threshold",
                metric="attendance_rate",
                entity=entity,
                value=value,
                threshold=threshold,
                severity=severity,
                text=(
                    f"{entity} attendance is {value:g}%, below the {threshold:g}% threshold."
                    if entity
                    else f"Attendance is {value:g}%, below the {threshold:g}% threshold."
                ),
            )
        )

    for row in _lowest(_metrics(evidence, "discrimination_index"), limit=3):
        value = float(row["value"])
        if value >= DISCRIMINATION_THRESHOLD:
            continue
        entity = row.get("entity")
        warnings.append(
            _warning(
                "discrimination_below_threshold",
                metric="discrimination_index",
                entity=entity,
                value=value,
                threshold=DISCRIMINATION_THRESHOLD,
                severity="medium",
                text=(
                    f"{entity} has a discrimination index of {value}, below "
                    f"{DISCRIMINATION_THRESHOLD}."
                    if entity
                    else (
                        f"A question has a discrimination index of {value}, below "
                        f"{DISCRIMINATION_THRESHOLD}."
                    )
                ),
            )
        )

    for row in _metrics(evidence, "students_below_pass"):
        value = float(row["value"])
        if value <= 0:
            continue
        warnings.append(
            _warning(
                "students_below_pass_mark",
                metric="students_below_pass",
                value=value,
                threshold=0,
                severity="high",
                text=(f"{int(value)} student(s) are below the {PASS_MARK}% pass mark."),
            )
        )

    if role in ("senior_management", "it_academic_integrity"):
        for row in _metrics(evidence, "flagged_attempts"):
            value = float(row["value"])
            if value <= 0:
                continue
            total = None
            comparison = row.get("comparison") or {}
            if comparison.get("name") == "monitored_attempts" and comparison.get(
                "scopeAverage"
            ):
                total = float(comparison["scopeAverage"])
            share = (value / total) if total else 0
            warnings.append(
                _warning(
                    "integrity_signal_detected",
                    metric="flagged_attempts",
                    value=value,
                    threshold=0,
                    severity="high" if share > 0.2 else "medium",
                    text=(
                        f"{int(value)} of {int(total)} monitored attempts are flagged."
                        if total
                        else f"{int(value)} monitored attempts are flagged."
                    ),
                )
            )

    if role == "it_academic_integrity":
        for row in (data.get("flagged") or [])[:1]:
            signals = row.get("evidence") or []
            if not signals:
                continue
            warnings.append(
                _warning(
                    "integrity_signal_detected",
                    metric="integrity_signals",
                    entity=row.get("student"),
                    value=float(len(signals)),
                    threshold=1,
                    severity="high" if len(signals) >= 3 else "medium",
                    text=(
                        f"{row.get('student')} on {row.get('exam')} has "
                        f"{len(signals)} integrity signal(s)."
                    ),
                )
            )

    timeline = (data.get("dashboard") or {}).get("scoreTimeline") or []
    if len(timeline) >= 2:
        latest = float(timeline[-1]["score"])
        previous = float(timeline[-2]["score"])
        drop = previous - latest
        if drop >= DECLINE_THRESHOLD:
            warnings.append(
                _warning(
                    "performance_decline",
                    metric="exam_score",
                    entity=timeline[-1].get("exam"),
                    value=latest,
                    threshold=previous - DECLINE_THRESHOLD,
                    severity="high",
                    text=(
                        f"{timeline[-1].get('exam')} score fell by {round(drop, 1)} points, "
                        f"from {previous} to {latest}."
                    ),
                )
            )

    return warnings


def _student_warnings(evidence: list[dict], data: dict[str, Any]) -> list[dict]:
    del evidence
    warnings: list[dict] = []
    dashboard = data.get("dashboard") or {}
    timeline = dashboard.get("scoreTimeline") or []
    average = dashboard.get("average")
    if average is not None and timeline and float(average) < PASS_MARK:
        warnings.append(
            _warning(
                "student_below_pass_mark",
                metric="average",
                entity=dashboard.get("studentName"),
                value=float(average),
                threshold=float(PASS_MARK),
                severity="high",
                text=f"Your average is {average}, below the {PASS_MARK}% pass mark.",
            )
        )
    if len(timeline) >= 2:
        latest = float(timeline[-1]["score"])
        previous = float(timeline[-2]["score"])
        drop = previous - latest
        if drop >= DECLINE_THRESHOLD:
            warnings.append(
                _warning(
                    "performance_decline",
                    metric="exam_score",
                    entity=timeline[-1].get("exam"),
                    value=latest,
                    threshold=previous - DECLINE_THRESHOLD,
                    severity="high",
                    text=(
                        f"{timeline[-1].get('exam')} score fell by {round(drop, 1)} points, "
                        f"from {previous} to {latest}."
                    ),
                )
            )
    return warnings
