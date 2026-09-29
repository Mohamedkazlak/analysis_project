"""Template AI layer over shared, filter-scoped analytics.

Insights, standings, warnings, and recommendations are all computed from
repository numbers, deterministically. An LLM is never the source of any of
those numbers. When configured, an LLM may reword the sentences afterward —
see the "Narration" note below — but every fact still comes from SQL.

Narration: the configured model is slow (a shared, remote, always-reasoning
instance), too slow to sit in the request/response path without either
blocking every card load or silently failing under a tight timeout. So the
fast, deterministic decision is computed and cached first and returned right
away, and narration (`rag.narrative`) runs afterward as a background task
that rewords the cached copy in place once it finishes. The frontend polls
briefly while `narrationStatus` is `"pending"`.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

from core.config import settings
from core.utils import PASS_MARK
from repositories.sql_filters import attempt_where
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from services import ai_cache
from services.ai_context import load_ai_context
from services.ai_evidence import build_evidence
from services.ai_rules import build_warnings
from rag.narrative import apply_llm_narratives, has_narratable_text, narration_enabled
from services.predictions import (
    comparison_place,
    get_standing_or_forecast,
    is_university_landing,
)

logger = logging.getLogger(__name__)

# Cache keys with a narration task currently running. Guards against
# scheduling a second background rewrite for the same decision while the
# first one is still in flight (e.g. two tabs polling the same scope).
_NARRATION_INFLIGHT: set[str] = set()


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
        "confirmationRequired": action is not None,
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
        totals = overview.get("totals") or {}
        if (
            is_university_landing(role, data)
            and totals.get("passRate") is not None
            and totals.get("students") is not None
            and totals.get("attendance") is not None
        ):
            headline = f"University student pass rate is {totals['passRate']}%"
            body = f"Across {len(colleges)} colleges, {int(totals['students'])} students sat exams"
            if totals.get("exams") is not None:
                body += f" and {int(totals['exams'])} exams were administered"
            body += (
                f". The university student pass rate is {totals['passRate']}% "
                f"and attendance is {totals['attendance']}%."
            )
            if len(colleges) > 1:
                body += (
                    f" {weakest['college']} is the lowest college at "
                    f"{weakest['passRate']}%."
                )
            return {
                "headline": headline,
                "body": body,
                "action": {"label": "Drill into curriculum", "to": "/courses"},
            }
        if len(colleges) == 1:
            headline = f"{weakest['college']} pass rate is {weakest['passRate']}%"
            body = (
                f"{weakest['college']} spans {weakest['courses']} curriculum with "
                f"{weakest['participants']} students who sat exams this term, at a "
                f"{weakest['passRate']}% student pass rate."
            )
        else:
            place = comparison_place(role, data)
            headline = f"{weakest['college']} has the lowest pass rate in {place}"
            body = (
                f"Across the {len(colleges)} colleges in {place}, {weakest['college']} sits at "
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
            "action": {"label": "Drill into curriculum", "to": "/courses"},
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
        return {
            "headline": headline,
            "body": body,
            "action": {"label": "Open student performance", "to": "/performance"},
        }

    if role == "professor":
        sections = (data.get("courses") or {}).get("sections") or []
        items = data.get("items") or {}
        if not sections:
            return {
                "headline": "No exam data in this scope yet",
                "body": "There are no recorded attempts in your assigned curriculum yet.",
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
            body = f"{weakest_section['section']} averages {weakest_section['average']} across your curriculum."
            headline = f"{weakest_section['section']} is your current baseline section"
        needs_review = items.get("needsReview") or []
        if needs_review:
            top = needs_review[0]
            body += (
                f" {top['exam']} question {top['number']} has a discrimination index of "
                f"{top['discriminationIndex']}, the weakest in your curriculum."
            )
        else:
            body += " No graded item-level answers are recorded yet, so item analysis has nothing to flag."
        return {
            "headline": headline,
            "body": body,
            "action": {"label": "Compare sections", "to": "/performance"},
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
                        "confirmBody": "This opens section performance for your curriculum. No message is sent to students.",
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
        "warnings": None,
        "evidence": None,
        "metadata": None,
        "validation": {"status": "not_run", "failures": 0},
        "dataStatus": "insufficient",
        "status": status,
        "message": message,
        "narrationStatus": "skipped",
    }


async def _data_version(db: asyncpg.Connection, filters: AnalyticsFilters) -> str:
    """Changes when attempts in this authorized scope change."""
    try:
        where_sql, args, _ = attempt_where(filters)
        value = await db.fetchval(
            f"""
            SELECT COALESCE(MAX(a.ended_at)::text, 'none') || ':' || COUNT(*)::text
            FROM v_exam_attempts a
            WHERE {where_sql}
            """,
            *args,
        )
        return str(value or "none")
    except Exception:
        logger.warning("AI data version lookup failed", exc_info=True)
        return "unknown"


def _attach_warnings(insight: Optional[dict], warnings: list[dict]) -> Optional[dict]:
    if insight is None:
        return None
    insight["warnings"] = [
        {"id": row["id"], "text": row["text"], "tone": row["tone"]} for row in warnings
    ] or None
    return insight


async def _compute_decision(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    insight_id: str,
    data_version: str,
) -> dict:
    data = await load_ai_context(ctx, db, filters)
    evidence = build_evidence(ctx.role, data)
    warnings = build_warnings(ctx.role, evidence, data)
    insight = _attach_warnings(_insight_from_context(ctx.role, data), warnings)
    prediction = await get_standing_or_forecast(ctx, db, filters, data)
    recommendations = _recommendations_from_context(ctx.role, data, insight_id)
    return {
        "insight": insight,
        "prediction": prediction,
        "recommendations": recommendations,
        "warnings": warnings or None,
        "evidence": evidence or None,
        "metadata": {
            "role": ctx.role,
            "scopeId": ctx.scope_id,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "dataVersion": data_version,
            "filters": filters.model_dump(),
        },
        "validation": {"status": "not_run", "failures": 0},
        "dataStatus": "ready" if evidence else "insufficient",
        "status": "ok",
        "message": None,
        "narrationStatus": "skipped",
    }


async def _narrate_and_recache(key: str, snapshot: dict) -> None:
    """Reword `snapshot` in place, in the background, then recache it.

    Runs after the deterministic result was already returned to the caller,
    so it can take as long as `AI_NARRATIVE_BACKGROUND_BUDGET_SECONDS` allows
    without any card waiting on it. Whatever sentences the model manages to
    reword before that budget runs out are kept; anything left over simply
    stays as the original, already-correct SQL sentence — never blank, never
    wrong, always grounded.
    """
    try:
        await asyncio.wait_for(
            apply_llm_narratives(snapshot),
            timeout=settings.AI_NARRATIVE_BACKGROUND_BUDGET_SECONDS,
        )
    except Exception:
        logger.warning("background AI narration did not finish in time", exc_info=True)
    finally:
        snapshot["narrationStatus"] = "done"
        ai_cache.set(key, snapshot)
        _NARRATION_INFLIGHT.discard(key)


def _schedule_narration(key: str, result: dict) -> None:
    if key in _NARRATION_INFLIGHT:
        return
    _NARRATION_INFLIGHT.add(key)
    # A private, mutated-in-place copy for the background task. `result`
    # itself is what gets returned to this caller and must stay untouched.
    asyncio.create_task(_narrate_and_recache(key, copy.deepcopy(result)))


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
    data_version = await _data_version(db, filters)
    key = ai_cache.make_cache_key(
        ctx,
        filters,
        academic_year_id=year_id,
        term_id=term_id,
        data_version=data_version,
    )
    cached = ai_cache.get(key)
    if cached is not None:
        return cached
    try:
        result = await asyncio.wait_for(
            _compute_decision(ctx, db, filters, insight_id, data_version),
            timeout=settings.AI_BUDGET_SECONDS,
        )
    except asyncio.TimeoutError:
        return _unavailable(
            "AI analysis is taking longer than expected.",
            status="timeout",
        )
    except Exception:
        return _unavailable("AI analysis is temporarily unavailable.")

    if narration_enabled() and has_narratable_text(result):
        result["narrationStatus"] = "pending"
        # The "pending" placeholder must outlive the narration budget, or a
        # normal-TTL cache eviction would make a second request in the same
        # window recompute the decision and schedule a duplicate rewrite.
        ai_cache.set(
            key,
            result,
            ttl=max(
                settings.AI_CACHE_TTL_SECONDS,
                int(settings.AI_NARRATIVE_BACKGROUND_BUDGET_SECONDS) + 5,
            ),
        )
        _schedule_narration(key, result)
    else:
        result["narrationStatus"] = "skipped"
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
