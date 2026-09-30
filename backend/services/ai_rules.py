"""Deterministic warning rules.

The model may later reword `text`. It cannot add, remove, or re-rank these
warnings. Thresholds are configuration, not model output.
"""

from __future__ import annotations

from typing import Any, Optional

from core.locale import Language, entity as localize_entity, txt
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


def build_warnings(
    role: str,
    evidence: list[dict],
    data: dict[str, Any],
    language: Language = "en",
) -> list[dict]:
    """Warnings that follow from evidence already limited to this role."""
    if role == "student":
        return _student_warnings(evidence, data, language=language)
    warnings: list[dict] = []

    for row in _lowest(_metrics(evidence, "pass_rate")):
        value = float(row["value"])
        if value >= PASS_RATE_THRESHOLD:
            continue
        severity = "high" if value < PASS_MARK else "medium"
        raw_entity = row.get("entity")
        label = localize_entity(language, raw_entity) if raw_entity else None
        warnings.append(
            _warning(
                "pass_rate_below_threshold",
                metric="pass_rate",
                entity=raw_entity,
                value=value,
                threshold=PASS_RATE_THRESHOLD,
                severity=severity,
                text=(
                    txt(
                        language,
                        f"{label} pass rate is {value:g}%, below the "
                        f"{PASS_RATE_THRESHOLD:g}% review threshold.",
                        f"معدل نجاح {label} هو {value:g}%، دون عتبة المراجعة "
                        f"{PASS_RATE_THRESHOLD:g}%.",
                    )
                    if label
                    else txt(
                        language,
                        f"Pass rate is {value:g}%, below the "
                        f"{PASS_RATE_THRESHOLD:g}% review threshold.",
                        f"معدل النجاح هو {value:g}%، دون عتبة المراجعة "
                        f"{PASS_RATE_THRESHOLD:g}%.",
                    )
                ),
            )
        )

    for row in _lowest(_metrics(evidence, "attendance_rate")):
        value = float(row["value"])
        if value >= ATTENDANCE_WATCH:
            continue
        severity = "high" if value < ATTENDANCE_THRESHOLD else "medium"
        raw_entity = row.get("entity")
        label = localize_entity(language, raw_entity) if raw_entity else None
        threshold = ATTENDANCE_THRESHOLD if severity == "high" else ATTENDANCE_WATCH
        warnings.append(
            _warning(
                "attendance_below_threshold",
                metric="attendance_rate",
                entity=raw_entity,
                value=value,
                threshold=threshold,
                severity=severity,
                text=(
                    txt(
                        language,
                        f"{label} attendance is {value:g}%, below the {threshold:g}% threshold.",
                        f"حضور {label} هو {value:g}%، دون العتبة {threshold:g}%.",
                    )
                    if label
                    else txt(
                        language,
                        f"Attendance is {value:g}%, below the {threshold:g}% threshold.",
                        f"الحضور هو {value:g}%، دون العتبة {threshold:g}%.",
                    )
                ),
            )
        )

    for row in _lowest(_metrics(evidence, "discrimination_index"), limit=3):
        value = float(row["value"])
        if value >= DISCRIMINATION_THRESHOLD:
            continue
        raw_entity = row.get("entity")
        label = localize_entity(language, raw_entity) if raw_entity else None
        warnings.append(
            _warning(
                "discrimination_below_threshold",
                metric="discrimination_index",
                entity=raw_entity,
                value=value,
                threshold=DISCRIMINATION_THRESHOLD,
                severity="medium",
                text=(
                    txt(
                        language,
                        f"{label} has a discrimination index of {value}, below "
                        f"{DISCRIMINATION_THRESHOLD}.",
                        f"{label} بمؤشر تمييز {value}، دون "
                        f"{DISCRIMINATION_THRESHOLD}.",
                    )
                    if label
                    else txt(
                        language,
                        f"A question has a discrimination index of {value}, below "
                        f"{DISCRIMINATION_THRESHOLD}.",
                        f"سؤال بمؤشر تمييز {value}، دون "
                        f"{DISCRIMINATION_THRESHOLD}.",
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
                text=txt(
                    language,
                    f"{int(value)} student(s) are below the {PASS_MARK}% pass mark.",
                    f"{int(value)} طالبًا دون درجة النجاح {PASS_MARK}%.",
                ),
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
                        txt(
                            language,
                            f"{int(value)} of {int(total)} monitored attempts are flagged.",
                            f"{int(value)} من {int(total)} محاولة مراقَبة معلّمة.",
                        )
                        if total
                        else txt(
                            language,
                            f"{int(value)} monitored attempts are flagged.",
                            f"{int(value)} محاولة مراقَبة معلّمة.",
                        )
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
                    text=txt(
                        language,
                        (
                            f"{row.get('student')} on {row.get('exam')} has "
                            f"{len(signals)} integrity signal(s)."
                        ),
                        (
                            f"{row.get('student')} في {row.get('exam')} لديه "
                            f"{len(signals)} إشارة نزاهة."
                        ),
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
                    text=txt(
                        language,
                        (
                            f"{timeline[-1].get('exam')} score fell by {round(drop, 1)} points, "
                            f"from {previous} to {latest}."
                        ),
                        (
                            f"درجة {timeline[-1].get('exam')} انخفضت بمقدار {round(drop, 1)} نقطة، "
                            f"من {previous} إلى {latest}."
                        ),
                    ),
                )
            )

    return warnings


def _student_warnings(
    evidence: list[dict], data: dict[str, Any], language: Language = "en"
) -> list[dict]:
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
                text=txt(
                    language,
                    f"Your average is {average}, below the {PASS_MARK}% pass mark.",
                    f"متوسطك هو {average}، دون درجة النجاح {PASS_MARK}%.",
                ),
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
                    text=txt(
                        language,
                        (
                            f"{timeline[-1].get('exam')} score fell by {round(drop, 1)} points, "
                            f"from {previous} to {latest}."
                        ),
                        (
                            f"درجة {timeline[-1].get('exam')} انخفضت بمقدار {round(drop, 1)} نقطة، "
                            f"من {previous} إلى {latest}."
                        ),
                    ),
                )
            )
    return warnings
