"""Template AI layer over shared, filter-scoped analytics.

Narratives are generated from repository numbers only. No LLM is called.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import asyncpg

from core.config import settings
from core.utils import PASS_MARK
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from services import ai_cache
from services.ai_context import load_ai_context
from rag.narrative import apply_llm_narratives
from services.predictions import get_standing_or_forecast


def _structured_recommendation(
    rec_id: str,
    kind: str,
    metric: str,
    value: Any,
    threshold: Any,
    text: str,
    source: str,
    evidence: list[dict],
    action: Optional[dict],
) -> dict:
    return {
        "id": rec_id,
        "kind": kind,
        "text": text,
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "basedOn": {"source": source, "evidence": evidence},
        "action": action,
    }


def _insight_from_context(role: str, data: dict[str, Any]) -> Optional[dict]:
    if role == "student":
        return None

    if role in ("senior_management", "program_director"):
        overview = data.get("overview") or {}
        colleges = overview.get("passRateByCollege") or []
        courses = overview.get("passRateByCourse") or []
        if not colleges:
            return {
                "headline": "No exam data in this scope yet",
                "body": "There are no recorded attempts in this scope yet, so there is nothing to report on.",
                "action": None,
            }
        weakest = min(colleges, key=lambda c: c["passRate"])
        weakest_course = min(courses, key=lambda c: c["passRate"]) if courses else None
        if len(colleges) == 1:
            headline = f"{weakest['college']} pass rate is {weakest['passRate']}%"
            body = (
                f"{weakest['college']} spans {weakest['courses']} curricula with "
                f"{weakest['participants']} students who sat exams this term, at a "
                f"{weakest['passRate']}% student pass rate."
            )
        else:
            headline = f"{weakest['college']} has the lowest pass rate in this view"
            body = (
                f"Across the {len(colleges)} colleges in this view, {weakest['college']} sits at "
                f"{weakest['passRate']}% student pass — the lowest here, from "
                f"{weakest['participants']} students."
            )
        if weakest_course:
            body += (
                f" The weakest curriculum overall is {weakest_course['course']} at "
                f"{weakest_course['passRate']}% pass."
            )
        return {
            "headline": headline,
            "body": body,
            "action": {"label": "Drill into curricula", "to": "/courses"},
        }

    if role == "academic_affairs":
        participation = data.get("participation") or {}
        performance = data.get("performance") or {}
        curricula = participation.get("attendanceByCurriculum") or []
        weakest_att = (
            min(curricula, key=lambda c: c["attendance"]) if curricula else None
        )
        below_pass = [
            r for r in performance.get("ranked") or [] if r["status"] == "Fail"
        ]
        if not weakest_att and not below_pass:
            return {
                "headline": "No performance data in this scope yet",
                "body": "There are no recorded attempts in this college yet.",
                "action": None,
            }
        parts = []
        if below_pass:
            parts.append(
                f"{len(below_pass)} student(s) are currently below the {PASS_MARK}% pass mark"
            )
        if weakest_att:
            parts.append(
                f"{weakest_att['course']} has the weakest attendance in the college at "
                f"{weakest_att['attendance']}%"
            )
        body = ". ".join(p[0].upper() + p[1:] for p in parts) + "."
        headline = (
            f"{len(below_pass)} students below the pass mark this term"
            if below_pass
            else f"{weakest_att['course']} attendance needs attention"
        )
        warnings = []
        if below_pass:
            warnings.append(
                {
                    "id": "w1",
                    "text": f"{len(below_pass)} students below pass mark — follow up this week",
                    "tone": "rose",
                }
            )
        if weakest_att:
            warnings.append(
                {
                    "id": "w2",
                    "text": f"{weakest_att['course']} attendance {weakest_att['attendance']}%",
                    "tone": "amber",
                }
            )
        return {
            "headline": headline,
            "body": body,
            "action": {"label": "Open student performance", "to": "/performance"},
            "warnings": warnings or None,
        }

    if role == "professor":
        sections = (data.get("courses") or {}).get("sections") or []
        participation = data.get("participation") or {}
        items = data.get("items") or {}
        if not sections:
            return {
                "headline": "No exam data in this scope yet",
                "body": "There are no recorded attempts in your assigned curricula yet.",
                "action": None,
            }
        weakest_section = min(sections, key=lambda s: s["average"])
        strongest_section = max(sections, key=lambda s: s["average"])
        gap = round(strongest_section["average"] - weakest_section["average"], 1)
        if gap > 0 and weakest_section["section"] != strongest_section["section"]:
            body = (
                f"{weakest_section['section']} averages {weakest_section['average']}, "
                f"{gap} points behind {strongest_section['section']} at "
                f"{strongest_section['average']} on the same curriculum."
            )
            headline = f"{weakest_section['section']} trails {strongest_section['section']} by {gap} points"
        else:
            body = f"{weakest_section['section']} averages {weakest_section['average']} across your curricula."
            headline = f"{weakest_section['section']} is your current baseline section"
        needs_review = items.get("needsReview") or []
        if needs_review:
            top = needs_review[0]
            body += (
                f" {top['exam']} question {top['number']} has a discrimination index of "
                f"{top['discriminationIndex']}, the weakest in your curricula."
            )
        else:
            body += " No graded item-level answers are recorded yet, so item analysis has nothing to flag."
        warnings = []
        curricula = participation.get("attendanceByCurriculum") or []
        weakest_att = (
            min(curricula, key=lambda c: c["attendance"]) if curricula else None
        )
        if weakest_att and weakest_att["attendance"] < 90:
            warnings.append(
                {
                    "id": "w1",
                    "text": f"{weakest_att['course']} attendance is {weakest_att['attendance']}%",
                    "tone": "amber",
                }
            )
        return {
            "headline": headline,
            "body": body,
            "action": {"label": "Compare sections", "to": "/performance"},
            "warnings": warnings or None,
        }

    if role == "it_academic_integrity":
        report = data.get("integrity") or {}
        cases_raw = data.get("flagged") or []
        if not cases_raw:
            return {
                "headline": "No flagged attempts right now",
                "body": "No monitored attempts in this scope currently show anomalies.",
                "action": None,
            }
        cases = []
        for i, c in enumerate(cases_raw):
            n = len(c["evidence"])
            share = round(100 / n) if n else 0
            evidence = [{**e, "weight": share} for e in c["evidence"]]
            score = min(100, share * n)
            level = "High" if n >= 3 else "Medium" if n == 2 else "Low"
            cases.append(
                {
                    "id": f"case-{i + 1}",
                    "subject": c["student"],
                    "exam": c["exam"],
                    "level": level,
                    "score": score,
                    "evidence": evidence,
                }
            )
        top = cases_raw[0]
        top_flags = ", ".join(e["label"] for e in top["evidence"]).lower()
        return {
            "headline": f"{report.get('flaggedCount', 0)} of {report.get('totalAttempts', 0)} monitored attempts flagged",
            "body": (
                f"{report.get('flaggedCount', 0)} attempts in this scope show at least one anomaly. "
                f"The highest-signal case is {top['student']} on {top['exam']}, flagged for {top_flags}."
            ),
            "action": {"label": "Open case detail", "to": "/integrity"},
            "cases": cases,
        }

    return None


def _recommendations_from_context(
    role: str, data: dict[str, Any], insight_id: str
) -> Optional[dict]:
    items: list[dict] = []

    if role == "student":
        dashboard = data.get("dashboard") or {}
        timeline = dashboard.get("scoreTimeline") or []
        if timeline:
            worst = min(timeline, key=lambda r: r["score"])
            delta = round(dashboard["average"] - dashboard["classAverage"], 1)
            items.append(
                _structured_recommendation(
                    "s1",
                    "guidance" if delta >= 0 else "action",
                    "average_vs_class",
                    dashboard["average"],
                    dashboard["classAverage"],
                    (
                        f"Your average is {dashboard['average']}, "
                        f"{'above' if delta >= 0 else 'below'} the class average of "
                        f"{dashboard['classAverage']} by {abs(delta)} points"
                    ),
                    "Your real score history",
                    [
                        {"label": "Your average", "detail": f"{dashboard['average']}"},
                        {
                            "label": "Class average",
                            "detail": f"{dashboard['classAverage']}",
                        },
                    ],
                    None,
                )
            )
            items.append(
                _structured_recommendation(
                    "s2",
                    "guidance",
                    "weakest_exam",
                    worst["score"],
                    PASS_MARK,
                    f"Your weakest recorded exam is {worst['exam']} at {worst['score']}",
                    "Your real score timeline",
                    [
                        {
                            "label": worst["exam"],
                            "detail": f"Score {worst['score']} vs class {worst['classAverage']}",
                        }
                    ],
                    {
                        "label": "Open my progress",
                        "to": "/my-progress",
                        "confirmTitle": "Open your progress page?",
                        "confirmBody": "Opens your personal dashboard for this exam.",
                        "confirmLabel": "Open",
                    },
                )
            )
        return {"insightId": insight_id, "items": items} if items else None

    if role in ("senior_management", "program_director"):
        overview = data.get("overview") or {}
        colleges = overview.get("passRateByCollege") or []
        if colleges:
            weakest = min(colleges, key=lambda c: c["passRate"])
            items.append(
                _structured_recommendation(
                    "m1",
                    "action",
                    "college_pass_rate",
                    weakest["passRate"],
                    PASS_MARK,
                    f"{weakest['college']} pass rate is {weakest['passRate']}% — review curriculum calibration",
                    "Current pass rate by college",
                    [
                        {
                            "label": weakest["college"],
                            "detail": f"{weakest['passRate']}% pass, {weakest['participants']} participants",
                        }
                    ],
                    {
                        "label": "Open curriculum drill-down",
                        "to": "/courses",
                        "confirmTitle": f"Open the {weakest['college']} drill-down?",
                        "confirmBody": "Opens the curriculum performance view filtered to this college. Nothing is shared externally.",
                        "confirmLabel": "Open drill-down",
                    },
                )
            )
        if role == "senior_management":
            integrity = data.get("integrity") or {}
            if integrity.get("totalAttempts"):
                items.append(
                    _structured_recommendation(
                        "m2",
                        "action" if integrity["flaggedCount"] else "guidance",
                        "flagged_attempts",
                        integrity["flaggedCount"],
                        0,
                        f"{integrity['flaggedCount']} of {integrity['totalAttempts']} monitored attempts are flagged",
                        "Current integrity monitoring",
                        [
                            {
                                "label": "Flagged",
                                "detail": f"{integrity['flaggedCount']} of {integrity['totalAttempts']} attempts",
                            }
                        ],
                        (
                            {
                                "label": "Open case list",
                                "to": "/integrity",
                                "confirmTitle": "Open the case list?",
                                "confirmBody": "Opens the monitoring log. No case status changes.",
                                "confirmLabel": "Open case list",
                            }
                            if integrity["flaggedCount"]
                            else None
                        ),
                    )
                )
        else:
            items_report = data.get("items") or {}
            if items_report.get("needsReview"):
                top = items_report["needsReview"][0]
                items.append(
                    _structured_recommendation(
                        "p2",
                        "action",
                        "discrimination_index",
                        top["discriminationIndex"],
                        0.2,
                        f"{top['exam']} question {top['number']} flagged — schedule an item review with faculty",
                        "Current item analysis",
                        [
                            {
                                "label": f"Q{top['number']}",
                                "detail": f"Discrimination {top['discriminationIndex']}",
                            }
                        ],
                        {
                            "label": "Open item analysis",
                            "to": "/item-analysis",
                            "confirmTitle": "Open item analysis?",
                            "confirmBody": "Opens item analysis for flagged questions. No items are published or retired.",
                            "confirmLabel": "Open",
                        },
                    )
                )
        return {"insightId": insight_id, "items": items} if items else None

    if role == "academic_affairs":
        performance = data.get("performance") or {}
        participation = data.get("participation") or {}
        below_pass = [
            r for r in performance.get("ranked") or [] if r["status"] == "Fail"
        ]
        if below_pass:
            items.append(
                _structured_recommendation(
                    "a1",
                    "action",
                    "students_below_pass",
                    len(below_pass),
                    0,
                    f"Follow up with {len(below_pass)} student(s) below the pass mark",
                    "Current student performance",
                    [
                        {
                            "label": "Below pass",
                            "detail": f"{len(below_pass)} students this term",
                        }
                    ],
                    {
                        "label": "Open student performance",
                        "to": "/performance",
                        "confirmTitle": "Open student performance?",
                        "confirmBody": "Opens the college performance view. No messages are sent to students.",
                        "confirmLabel": "Open",
                    },
                )
            )
        curricula = participation.get("attendanceByCurriculum") or []
        if curricula:
            weakest_att = min(curricula, key=lambda c: c["attendance"])
            items.append(
                _structured_recommendation(
                    "a2",
                    "action",
                    "curriculum_attendance",
                    weakest_att["attendance"],
                    90,
                    f"Review {weakest_att['course']} attendance ({weakest_att['attendance']}%)",
                    "Current attendance by curriculum",
                    [
                        {
                            "label": weakest_att["course"],
                            "detail": f"{weakest_att['attendance']}% attendance",
                        }
                    ],
                    {
                        "label": "Open attendance",
                        "to": "/participation",
                        "confirmTitle": "Open attendance?",
                        "confirmBody": "Opens participation and attendance for every curriculum in the college.",
                        "confirmLabel": "Open",
                    },
                )
            )
        return {"insightId": insight_id, "items": items} if items else None

    if role == "professor":
        sections = (data.get("courses") or {}).get("sections") or []
        items_report = data.get("items") or {}
        if sections:
            weakest_section = min(sections, key=lambda s: s["average"])
            items.append(
                _structured_recommendation(
                    "f1",
                    "action",
                    "section_average",
                    weakest_section["average"],
                    PASS_MARK,
                    f"{weakest_section['section']} averages {weakest_section['average']} — consider a review session",
                    "Current section performance",
                    [
                        {
                            "label": weakest_section["section"],
                            "detail": f"{weakest_section['average']} avg, {weakest_section['passRate']}% pass",
                        }
                    ],
                    {
                        "label": "Compare sections",
                        "to": "/performance",
                        "confirmTitle": "Open the section comparison?",
                        "confirmBody": "This opens section performance for your curricula. No message is sent to students.",
                        "confirmLabel": "Open comparison",
                    },
                )
            )
        if items_report.get("needsReview"):
            top = items_report["needsReview"][0]
            items.append(
                _structured_recommendation(
                    "f2",
                    "action",
                    "discrimination_index",
                    top["discriminationIndex"],
                    0.2,
                    f"Question {top['number']} on {top['exam']} flagged for review — low discrimination index",
                    "Current item analysis",
                    [
                        {
                            "label": f"Q{top['number']}",
                            "detail": f"Discrimination {top['discriminationIndex']}",
                        }
                    ],
                    {
                        "label": "Open in Item Analysis",
                        "to": "/item-analysis",
                        "confirmTitle": "Open the flagged question?",
                        "confirmBody": "Item Analysis opens filtered to this question. Nothing is changed or published.",
                        "confirmLabel": "Open question",
                    },
                )
            )
        return {"insightId": insight_id, "items": items} if items else None

    if role == "it_academic_integrity":
        report = data.get("integrity") or {}
        cases_raw = data.get("flagged") or []
        if cases_raw:
            top = cases_raw[0]
            items.append(
                _structured_recommendation(
                    "i1",
                    "action",
                    "integrity_signals",
                    len(top["evidence"]),
                    1,
                    f"Recommended for review: {top['student']} / {top['exam']}",
                    f"Fused from {len(top['evidence'])} real signal(s)",
                    top["evidence"],
                    {
                        "label": "Create case",
                        "to": "/integrity",
                        "confirmTitle": "Create an investigation case?",
                        "confirmBody": "Opens the case with the evidence above pre-attached and marked recommended for review. No finding is recorded and no one is notified.",
                        "confirmLabel": "Create case",
                    },
                )
            )
        if report.get("totalAttempts"):
            items.append(
                _structured_recommendation(
                    "i2",
                    "guidance",
                    "flagged_attempts",
                    report["flaggedCount"],
                    0,
                    f"{report['flaggedCount']} of {report['totalAttempts']} monitored attempts are currently flagged",
                    "Current integrity monitoring",
                    [
                        {
                            "label": "Flagged",
                            "detail": f"{report['flaggedCount']} of {report['totalAttempts']}",
                        }
                    ],
                    None,
                )
            )
        return {"insightId": insight_id, "items": items} if items else None

    return None


def _unavailable(message: str, status: str = "unavailable") -> dict:
    return {
        "insight": None,
        "prediction": None,
        "recommendations": None,
        "status": status,
        "message": message,
    }


async def _compute_decision(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    insight_id: str,
) -> dict:
    data = await load_ai_context(ctx, db, filters)
    insight = _insight_from_context(ctx.role, data)
    prediction = await get_standing_or_forecast(ctx, db, filters, data)
    recommendations = _recommendations_from_context(ctx.role, data, insight_id)
    return await apply_llm_narratives(
        {
            "insight": insight,
            "prediction": prediction,
            "recommendations": recommendations,
            "status": "ok",
            "message": None,
        }
    )


async def get_ai_decision(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    insight_id: str = "insight",
) -> dict:
    year_id = (
        await db.fetchval("SELECT id FROM academic_years WHERE is_current LIMIT 1")
        or ""
    )
    term_id = ""
    if year_id:
        term_id = (
            await db.fetchval(
                """
                SELECT id FROM terms
                WHERE academic_year_id = $1
                ORDER BY start_date DESC
                LIMIT 1
                """,
                year_id,
            )
            or ""
        )
    key = ai_cache.make_cache_key(
        ctx, filters, academic_year_id=year_id, term_id=term_id
    )
    cached = ai_cache.get(key)
    if cached is not None:
        return cached
    try:
        result = await asyncio.wait_for(
            _compute_decision(ctx, db, filters, insight_id),
            timeout=settings.AI_BUDGET_SECONDS,
        )
    except asyncio.TimeoutError:
        return _unavailable(
            "AI analysis is taking longer than expected.",
            status="timeout",
        )
    except Exception:
        return _unavailable("AI analysis is temporarily unavailable.")
    ai_cache.set(key, result)
    return result


async def get_insight(
    ctx: UserContext, db: asyncpg.Connection, filters: AnalyticsFilters | None = None
):
    decision = await get_ai_decision(ctx, db, filters or AnalyticsFilters())
    return decision.get("insight")


async def get_prediction(
    ctx: UserContext, db: asyncpg.Connection, filters: AnalyticsFilters | None = None
):
    decision = await get_ai_decision(ctx, db, filters or AnalyticsFilters())
    return decision.get("prediction")


async def get_recommendations(
    ctx: UserContext,
    db: asyncpg.Connection,
    insight_id: str,
    filters: AnalyticsFilters | None = None,
):
    decision = await get_ai_decision(ctx, db, filters or AnalyticsFilters(), insight_id)
    return decision.get("recommendations")
