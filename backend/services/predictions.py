"""Current standing vs genuine forecast.

Exam offerings in this database are current-term only, so a numerical forecast
is not computed. When two or more academic years of transcript data exist for
the selected student, direction is taken from that real history. No LLM is used.
Year counts are always taken from the authorized / selected scope, never from
global university history.
"""

from __future__ import annotations

from typing import Any, Optional

import asyncpg

from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from services.gpa import standing_from_gpa

SUMMARY_NOTE = (
    "No multi-term exam history is recorded yet to project a trend, so this is "
    "the real current-term standing, not a forecast."
)


def _tone_for(value: float, benchmark: float) -> str:
    if value >= benchmark:
        return "mint"
    if value <= benchmark - 5:
        return "rose"
    return "amber"


def current_standing_from_context(
    role: str, ctx_data: dict[str, Any]
) -> Optional[dict]:
    if role in ("senior_management", "program_director"):
        overview = ctx_data.get("overview") or {}
        colleges = overview.get("passRateByCollege") or []
        if not colleges:
            return None
        overall = sum(c["passRate"] for c in colleges) / len(colleges)
        ranked = sorted(colleges, key=lambda c: c["passRate"])[:3]
        return {
            "kind": "current_standing",
            "title": "Current standing · colleges in scope",
            "direction": "stable",
            "summary": SUMMARY_NOTE,
            "rows": [
                {
                    "label": c["college"],
                    "value": f"{c['passRate']}% pass",
                    "tone": _tone_for(c["passRate"], overall),
                }
                for c in ranked
            ],
            "action": {"label": "Open curriculum view", "to": "/courses"},
        }

    if role == "academic_affairs":
        participation = ctx_data.get("participation") or {}
        curricula = participation.get("attendanceByCurriculum") or []
        if not curricula:
            return None
        overall = participation.get("attendanceRate") or 0
        ranked = sorted(curricula, key=lambda c: c["attendance"])[:3]
        return {
            "kind": "current_standing",
            "title": "Current standing · attendance by curriculum",
            "direction": "stable",
            "summary": SUMMARY_NOTE,
            "rows": [
                {
                    "label": c["course"],
                    "value": f"{c['attendance']}% attendance",
                    "tone": _tone_for(c["attendance"], overall),
                }
                for c in ranked
            ],
            "action": {"label": "Open attendance", "to": "/participation"},
        }

    if role == "professor":
        sections = (ctx_data.get("courses") or {}).get("sections") or []
        if not sections:
            return None
        overall = sum(s["average"] for s in sections) / len(sections)
        ranked = sorted(sections, key=lambda s: s["average"])[:3]
        return {
            "kind": "current_standing",
            "title": "Current standing · your sections",
            "direction": "stable",
            "summary": SUMMARY_NOTE,
            "rows": [
                {
                    "label": s["section"],
                    "value": f"{s['average']} avg · {s['passRate']}% pass",
                    "tone": _tone_for(s["average"], overall),
                }
                for s in ranked
            ],
            "action": {"label": "Open curriculum view", "to": "/courses"},
        }

    if role == "it_academic_integrity":
        summary_rows = (ctx_data.get("integrity") or {}).get("summary") or []
        if not summary_rows:
            return None
        ranked = sorted(
            summary_rows,
            key=lambda s: (s["flagged"] / s["total"]) if s["total"] else 0,
            reverse=True,
        )[:3]
        return {
            "kind": "current_standing",
            "title": "Current standing · flagged share by exam",
            "direction": "stable",
            "summary": SUMMARY_NOTE,
            "rows": [
                {
                    "label": s["exam"],
                    "value": f"{s['flagged']}/{s['total']} flagged",
                    "tone": (
                        "rose"
                        if s["total"] and s["flagged"] / s["total"] > 0.2
                        else "amber"
                    ),
                }
                for s in ranked
            ],
            "action": {"label": "Open live monitoring", "to": "/real-time"},
        }

    if role == "professor":
        sections = (ctx_data.get("courses") or {}).get("sections") or []
        if not sections:
            return None
        weakest = min(sections, key=lambda section: section["average"])
        return {
            "kind": "current_standing",
            "title": "Current standing · assigned sections",
            "direction": "stable",
            "summary": SUMMARY_NOTE,
            "rows": [
                {
                    "label": section["section"],
                    "value": f"{section['average']} avg",
                    "tone": _tone_for(section["average"], weakest["average"]),
                }
                for section in sorted(sections, key=lambda section: section["average"])[
                    :3
                ]
            ],
            "action": {"label": "Open section comparison", "to": "/performance"},
        }

    if role == "student":
        dashboard = ctx_data.get("dashboard") or {}
        average = dashboard.get("average")
        if average is None:
            return None
        class_average = dashboard.get("classAverage")
        rows = [
            {
                "label": "Your average",
                "value": str(average),
                "tone": (
                    _tone_for(float(average), float(class_average))
                    if class_average is not None
                    else "iris"
                ),
            }
        ]
        if class_average is not None:
            rows.append(
                {
                    "label": "Class average",
                    "value": str(class_average),
                    "tone": "iris",
                }
            )
        return {
            "kind": "current_standing",
            "title": "Current standing · your recorded scores",
            "direction": "stable",
            "summary": SUMMARY_NOTE,
            "rows": rows,
            "action": {"label": "Open your record", "to": "/student"},
        }

    return None


async def _scoped_offering_year_count(
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
) -> int:
    clauses = ["TRUE"]
    args: list = []
    i = 1
    if filters.sector_id:
        clauses.append(f"p.parent_id = ${i}")
        args.append(filters.sector_id)
        i += 1
    if filters.college_id:
        clauses.append(f"c.program_id = ${i}")
        args.append(filters.college_id)
        i += 1
    if filters.curriculum_id:
        clauses.append(f"c.id = ${i}")
        args.append(filters.curriculum_id)
        i += 1
    if filters.professor_id:
        clauses.append(
            f"""EXISTS (
                SELECT 1 FROM staff_course_assignments sca
                WHERE sca.course_id = c.id AND sca.staff_person_id = ${i}
            )"""
        )
        args.append(filters.professor_id)
        i += 1
    if filters.student_id:
        clauses.append(
            f"""EXISTS (
                SELECT 1 FROM enrollments e
                WHERE e.offering_id = o.id AND e.student_id = ${i}
            )"""
        )
        args.append(filters.student_id)
        i += 1
    where_sql = " AND ".join(clauses)
    return int(
        await db.fetchval(
            f"""
            SELECT COUNT(DISTINCT o.academic_year_id)
            FROM course_offerings o
            JOIN courses c ON c.id = o.course_id
            JOIN org_units p ON p.id = c.program_id
            WHERE {where_sql}
            """,
            *args,
        )
        or 0
    )


async def get_standing_or_forecast(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    ctx_data: dict[str, Any],
) -> Optional[dict]:
    years = await _scoped_offering_year_count(db, filters)
    result = current_standing_from_context(ctx.role, ctx_data)
    if result is None:
        return None
    if years >= 2:
        result["summary"] = (
            "Multiple offering years exist in this scope, but a forecasting "
            "model is not wired. Showing current-term standing from recorded attempts."
        )
    if filters.student_id:
        year_avgs = await db.fetch(
            """
            SELECT academic_year_id, AVG(average)::float AS avg
            FROM transcript_entries
            WHERE student_id = $1
            GROUP BY academic_year_id
            ORDER BY academic_year_id
            """,
            filters.student_id,
        )
        if len(year_avgs) >= 2:
            delta = year_avgs[-1]["avg"] - year_avgs[0]["avg"]
            result["direction"] = (
                "rising" if delta > 1 else "falling" if delta < -1 else "stable"
            )
            result["summary"] = (
                f"Year-over-year transcript average moved {delta:+.1f} points. "
                "This is historical standing, not a model forecast."
            )
            result["kind"] = "current_standing"
    _ = standing_from_gpa
    return result
