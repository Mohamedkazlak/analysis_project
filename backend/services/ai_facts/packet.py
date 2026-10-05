"""Build a scoped fact packet from AI context + SQL side signals."""

from __future__ import annotations

from typing import Any, Optional

import asyncpg

from core.locale import Language, txt
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from services.ai_facts.attribution import attribute_gap, extract_section_topic_signals
from services.ai_facts.detectors import run_detectors
from services.ai_facts.models import (
    FactPacket,
    ForecastStatus,
    ImpactItem,
    Provenance,
    RuleAlert,
    utc_now_iso,
)
from services.ai_facts.narration import template_narrative
from services.ai_thresholds import (
    MIN_FORECAST_OBSERVATIONS,
    PASS_RATE_THRESHOLD,
)
from services.predictions import is_university_landing


def _overview_metrics(data: dict[str, Any]) -> dict[str, Any]:
    overview = data.get("overview") or {}
    totals = overview.get("totals") or {}
    participation = data.get("participation") or {}
    performance = data.get("performance") or {}
    courses = data.get("courses") or {}
    integrity = data.get("integrity") or {}

    attendance = totals.get("attendance")
    if attendance is None:
        attendance = participation.get("attendanceRate")

    students = totals.get("students")
    if students is None:
        students = (performance.get("totals") or {}).get("students")
    if students is None:
        ranked = performance.get("ranked") or []
        if ranked:
            students = len(ranked)

    exams = totals.get("exams")
    if exams is None and integrity.get("totalAttempts") is not None:
        exams = integrity.get("totalAttempts")

    pass_rate = totals.get("passRate")
    if pass_rate is None:
        sections = courses.get("sections") or []
        rates = [
            float(s["passRate"]) for s in sections if s.get("passRate") is not None
        ]
        if rates:
            pass_rate = round(sum(rates) / len(rates), 1)

    return {
        "passRate": pass_rate,
        "attendance": attendance,
        "students": students,
        "exams": exams,
    }


def _rule_alerts_from_warnings(warnings: list[dict]) -> list[RuleAlert]:
    out: list[RuleAlert] = []
    for w in warnings or []:
        out.append(
            RuleAlert(
                id=str(w.get("id") or w.get("rule") or "rule"),
                rule=str(w.get("rule") or "threshold"),
                severity=str(w.get("severity") or "medium"),
                text=str(w.get("text") or ""),
                entity=w.get("entity"),
                value=w.get("value"),
                threshold=w.get("threshold"),
                evidence=[
                    f"value={w.get('value')}",
                    f"threshold={w.get('threshold')}",
                ],
            )
        )

    def _gap(alert: RuleAlert) -> float:
        if alert.value is None or alert.threshold is None:
            return 0.0
        return abs(float(alert.threshold) - float(alert.value))

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(
        key=lambda a: (
            severity_rank.get(a.severity, 9),
            -_gap(a),
        )
    )
    return out


def _impact_from_packet(
    drivers: list,
    rule_alerts: list[RuleAlert],
    anomalies: list,
    students: int,
) -> list[ImpactItem]:
    items: list[ImpactItem] = []
    for i, d in enumerate(drivers[:6], start=1):
        uplift = round(float(d.contribution_points), 2)
        items.append(
            ImpactItem(
                id=f"impact-driver-{i}",
                issue=d.label,
                students_affected=max(1, students // max(6, i * 2)),
                gap_to_threshold=uplift,
                uplift_program=uplift,
                uplift_university=round(uplift * 0.35, 2),
                source="driver",
                rank=i,
            )
        )
    for i, a in enumerate(rule_alerts[:4], start=1):
        gap = 0.0
        if a.value is not None and a.threshold is not None:
            gap = round(abs(float(a.threshold) - float(a.value)), 2)
        items.append(
            ImpactItem(
                id=f"impact-rule-{a.id}",
                issue=a.text,
                students_affected=max(1, students // 10),
                gap_to_threshold=gap,
                uplift_program=gap,
                uplift_university=round(gap * 0.25, 2),
                source="rule",
                rank=100 + i,
            )
        )
    for i, an in enumerate(anomalies[:4], start=1):
        items.append(
            ImpactItem(
                id=f"impact-anomaly-{an.id}",
                issue=an.text,
                students_affected=max(1, students // 12),
                gap_to_threshold=5.0,
                uplift_program=5.0,
                uplift_university=1.5,
                source="anomaly",
                rank=200 + i,
            )
        )
    items.sort(key=lambda x: (-x.uplift_university, x.rank))
    for i, item in enumerate(items, start=1):
        item.rank = i
    return items


def _forecast_status(
    prediction: Optional[dict], language: Language = "en"
) -> ForecastStatus:
    if not prediction:
        return ForecastStatus(
            kind="insufficient",
            message=txt(
                language,
                (
                    f"No reliable forecast is available because fewer than "
                    f"{MIN_FORECAST_OBSERVATIONS} yearly averages are recorded in this scope."
                ),
                (
                    f"لا يتوفر توقّع موثوق لأن عدد المتوسطات السنوية المسجّلة "
                    f"في هذا النطاق أقل من {MIN_FORECAST_OBSERVATIONS}."
                ),
            ),
            needs_years=MIN_FORECAST_OBSERVATIONS,
        )
    kind = prediction.get("kind") or "current_standing"
    if kind == "forecast":
        return ForecastStatus(
            kind="forecast",
            message=str(prediction.get("summary") or ""),
            value=prediction.get("forecastValue"),
            low=prediction.get("intervalLow"),
            high=prediction.get("intervalHigh"),
            observations=int(prediction.get("observations") or 0),
        )
    obs = int(prediction.get("observations") or 0)
    needs = max(0, MIN_FORECAST_OBSERVATIONS - obs)
    return ForecastStatus(
        kind="current_standing" if obs else "insufficient",
        message=str(prediction.get("summary") or ""),
        observations=obs,
        needs_years=needs,
    )


async def _load_detector_signals(
    db: asyncpg.Connection,
    ctx: UserContext,
    filters: AnalyticsFilters,
) -> dict[str, Any]:
    """Best-effort scoped signals for anomaly detectors."""
    signals: dict[str, Any] = {
        "sections": [],
        "questions": [],
        "yoy": [],
        "attempts": [],
    }
    try:
        section_rows = await db.fetch(
            """
            SELECT cs.code AS section,
                   AVG(a.score)::float AS mean,
                   COALESCE(STDDEV(a.score), 0)::float AS sd
            FROM exam_attempts a
            JOIN enrollments e ON e.id = a.enrollment_id
            JOIN course_sections cs ON cs.id = e.section_id
            JOIN exams x ON x.id = a.exam_id
            JOIN course_offerings o ON o.id = x.offering_id
            JOIN courses c ON c.id = o.course_id
            WHERE a.score IS NOT NULL
              AND ($1::text IS NULL OR c.program_id = $1)
              AND ($2::text IS NULL OR c.id = $2)
            GROUP BY cs.code
            HAVING COUNT(*) >= 5
            ORDER BY cs.code
            LIMIT 20
            """,
            filters.college_id,
            filters.curriculum_id,
        )
        signals["sections"] = [dict(r) for r in section_rows]
    except Exception:
        pass
    try:
        q_rows = await db.fetch(
            """
            SELECT q.id, q.topic,
                   AVG(CASE WHEN ans.is_correct THEN 1.0 ELSE 0.0 END)::float AS correct_rate
            FROM questions q
            JOIN attempt_answers ans ON ans.question_id = q.id
            JOIN exams x ON x.id = q.exam_id
            JOIN course_offerings o ON o.id = x.offering_id
            JOIN courses c ON c.id = o.course_id
            WHERE ($1::text IS NULL OR c.program_id = $1)
              AND ($2::text IS NULL OR c.id = $2)
            GROUP BY q.id, q.topic
            HAVING COUNT(*) >= 8
            ORDER BY q.topic, q.id
            LIMIT 80
            """,
            filters.college_id,
            filters.curriculum_id,
        )
        signals["questions"] = [dict(r) for r in q_rows]
    except Exception:
        pass
    try:
        yoy = await db.fetch(
            """
            SELECT c.code AS course,
                   t.academic_year_id AS year,
                   AVG(CASE WHEN t.average < 60 THEN 1.0 ELSE 0.0 END)::float AS fail_rate
            FROM transcript_entries t
            JOIN courses c ON c.id = t.course_id
            WHERE ($1::text IS NULL OR c.program_id = $1)
              AND ($2::text IS NULL OR c.id = $2)
            GROUP BY c.code, t.academic_year_id
            HAVING COUNT(*) >= 10
            ORDER BY c.code, t.academic_year_id
            LIMIT 100
            """,
            filters.college_id,
            filters.curriculum_id,
        )
        signals["yoy"] = [dict(r) for r in yoy]
    except Exception:
        pass
    try:
        attempts = await db.fetch(
            """
            SELECT host(a.ip) AS ip, a.time_taken_min
            FROM exam_attempts a
            JOIN exams x ON x.id = a.exam_id
            JOIN course_offerings o ON o.id = x.offering_id
            JOIN courses c ON c.id = o.course_id
            WHERE a.ip IS NOT NULL
              AND ($1::text IS NULL OR c.program_id = $1)
              AND ($2::text IS NULL OR c.id = $2)
            LIMIT 500
            """,
            filters.college_id,
            filters.curriculum_id,
        )
        signals["attempts"] = [dict(r) for r in attempts]
    except Exception:
        pass
    # Professors: curriculum forced by assignments elsewhere; keep filter.
    if ctx.role == "student":
        signals = {"sections": [], "questions": [], "yoy": [], "attempts": []}
    return signals


async def build_fact_packet(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    data: dict[str, Any],
    *,
    warnings: list[dict],
    prediction: Optional[dict],
    data_version: str,
    card_id: str = "ai-decision",
    language: Language = "en",
) -> FactPacket:
    metrics = _overview_metrics(data)
    overview = data.get("overview") or {}
    courses = overview.get("passRateByCourse") or []
    colleges = overview.get("passRateByCollege") or []
    scope_rate = metrics.get("passRate")
    # Prefer university average as benchmark when available for college slices.
    uni_from_colleges = None
    if colleges and len(colleges) > 1 and is_university_landing(ctx.role, data):
        rates = [
            (float(c["passRate"]), int(c.get("students") or 0))
            for c in colleges
            if c.get("passRate") is not None
        ]
        total_n = sum(n for _, n in rates) or 0
        if total_n:
            uni_from_colleges = sum(r * n for r, n in rates) / total_n
    if (
        not is_university_landing(ctx.role, data)
        and metrics.get("passRate") is not None
    ):
        # College / course scope: gap vs review line unless a wider rate is known.
        benchmark = (
            float(uni_from_colleges)
            if uni_from_colleges is not None
            else PASS_RATE_THRESHOLD
        )
    else:
        benchmark = (
            float(uni_from_colleges)
            if uni_from_colleges is not None
            else PASS_RATE_THRESHOLD
        )
    sections, topics = extract_section_topic_signals(data)
    # Prefer live detector section stats when attribution sections empty.
    signals = await _load_detector_signals(db, ctx, filters)
    if not sections and signals.get("sections"):
        means = [s["mean"] for s in signals["sections"] if s.get("mean") is not None]
        if means:
            overall = sum(means) / len(means)
            sections = [
                {
                    "section": s["section"],
                    "delta": abs(float(s["mean"]) - overall),
                    "mean": s["mean"],
                }
                for s in signals["sections"]
            ]
    if not topics and signals.get("questions"):
        topics = [
            {"topic": q["topic"], "correct_rate": q["correct_rate"]}
            for q in signals["questions"]
        ]

    drivers = attribute_gap(
        scope_pass_rate=float(scope_rate) if scope_rate is not None else None,
        benchmark_pass_rate=float(benchmark),
        courses=courses,
        sections=sections,
        topics=topics,
        yoy=None,
        language=language,
    )
    rule_alerts = _rule_alerts_from_warnings(warnings)
    anomalies = run_detectors(signals, language=language)

    # S5-style: rule alerts exist but no drivers / anomalies about structure.
    no_structural = bool(rule_alerts) and not drivers and not anomalies

    students = int(metrics.get("students") or 0)
    impact = _impact_from_packet(drivers, rule_alerts, anomalies, students)
    forecast = _forecast_status(prediction, language=language)

    packet = FactPacket(
        card_id=card_id,
        role=ctx.role,
        scope_id=ctx.scope_id,
        slice={
            "sectorId": filters.sector_id,
            "collegeId": filters.college_id,
            "curriculumId": filters.curriculum_id,
            "studentId": filters.student_id,
            "professorId": filters.professor_id,
        },
        data_version=data_version,
        headline_metrics=metrics,
        drivers=drivers,
        rule_alerts=rule_alerts,
        anomalies=anomalies,
        impact_items=impact,
        forecast=forecast,
        provenance=Provenance(
            tables=[
                "exam_attempts",
                "transcript_entries",
                "integrity_flags",
                "questions",
                "attempt_answers",
            ],
            row_counts={},
            updated_at=utc_now_iso(),
        ),
        no_structural_cause=no_structural,
    )
    # Fill provenance counts cheaply.
    try:
        for table in packet.provenance.tables:
            packet.provenance.row_counts[table] = int(
                await db.fetchval(f"SELECT COUNT(*)::int FROM {table}") or 0
            )
    except Exception:
        pass

    narr = template_narrative(packet, language=language)
    packet.story_template = narr["story"]
    return packet


def packet_to_decision_fields(
    packet: FactPacket,
    narrative: dict[str, Any],
    language: Language = "en",
) -> dict[str, Any]:
    """Map packet + narrative into fields merged onto AiDecision."""
    from services.evidence_quality import assess_evidence_quality

    students = packet.headline_metrics.get("students")
    sample = int(students) if students is not None else None
    forecast = packet.forecast
    has_historical = bool(
        forecast
        and forecast.kind == "forecast"
        and (forecast.observations or 0) >= MIN_FORECAST_OBSERVATIONS
    )
    evidence_quality = assess_evidence_quality(
        sample_size=sample,
        has_historical=has_historical,
        has_breakdown=bool(packet.drivers),
        has_comparison=bool(packet.drivers)
        or packet.headline_metrics.get("passRate") is not None,
        anomaly_count=len(packet.anomalies),
        rule_alert_count=len(packet.rule_alerts),
        language=language,
    )
    return {
        "factPacket": packet.to_dict(),
        "narrative": narrative,
        "ruleAlerts": [a.__dict__ for a in packet.rule_alerts],
        "anomalies": [a.__dict__ for a in packet.anomalies],
        "impactItems": [i.__dict__ for i in packet.impact_items],
        "provenance": packet.provenance.__dict__ if packet.provenance else None,
        "forecastStatus": packet.forecast.__dict__ if packet.forecast else None,
        "evidenceQuality": evidence_quality,
    }
