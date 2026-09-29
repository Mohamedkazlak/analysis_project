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
from repositories.sql_filters import course_org_where
from services.ai_rules import ATTENDANCE_WATCH, PASS_RATE_THRESHOLD

SUMMARY_NOTE = (
    "No reliable forecast is available because fewer than 3 yearly averages "
    "are recorded in this scope. This is the real current standing, not a forecast."
)
FORECAST_METHOD = "ols_linear_v1"
MIN_FORECAST_OBSERVATIONS = 3


def _tone_for(value: float, benchmark: float) -> str:
    if value >= benchmark:
        return "mint"
    if value <= benchmark - 5:
        return "rose"
    return "amber"


def _filter_ids(data: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    filters = data.get("filters")
    if filters is None:
        return None, None
    if isinstance(filters, dict):
        sector_id = filters.get("sector_id") or filters.get("sectorId")
        college_id = filters.get("college_id") or filters.get("collegeId")
        return sector_id or None, college_id or None
    return getattr(filters, "sector_id", None), getattr(filters, "college_id", None)


def comparison_place(role: str, data: dict[str, Any]) -> str:
    """Wording for a president view that is already narrowed to a sector."""
    sector_id, college_id = _filter_ids(data)
    if role == "senior_management" and sector_id and not college_id:
        return "this sector"
    return "this view"


def is_university_landing(role: str, data: dict[str, Any]) -> bool:
    """University president with no sector or college selected."""
    if role != "senior_management":
        return False
    if data.get("filters") is None:
        return False
    sector_id, college_id = _filter_ids(data)
    return not sector_id and not college_id


def current_standing_from_context(
    role: str, ctx_data: dict[str, Any]
) -> Optional[dict]:
    if role in ("senior_management", "program_director"):
        overview = ctx_data.get("overview") or {}
        colleges = overview.get("passRateByCollege") or []
        if not colleges:
            return None
        if is_university_landing(role, ctx_data):
            totals = overview.get("totals") or {}
            pass_rate = totals.get("passRate")
            attendance = totals.get("attendance")
            students = totals.get("students")
            if (
                pass_rate is not None
                and attendance is not None
                and students is not None
            ):
                return {
                    "kind": "current_standing",
                    "title": "Current standing · university",
                    "direction": "stable",
                    "summary": SUMMARY_NOTE,
                    "rows": [
                        {
                            "label": "Student pass rate",
                            "value": f"{pass_rate}%",
                            "tone": _tone_for(float(pass_rate), PASS_RATE_THRESHOLD),
                        },
                        {
                            "label": "Attendance",
                            "value": f"{attendance}%",
                            "tone": _tone_for(float(attendance), ATTENDANCE_WATCH),
                        },
                        {
                            "label": "Students",
                            "value": str(int(students)),
                            "tone": "iris",
                        },
                    ],
                    "action": {"label": "Open curriculum view", "to": "/courses"},
                }
        overall = sum(c["passRate"] for c in colleges) / len(colleges)
        ranked = sorted(colleges, key=lambda c: c["passRate"])[:3]
        sector_id, college_id = _filter_ids(ctx_data)
        title = "Current standing · colleges in scope"
        if role == "senior_management" and sector_id and not college_id:
            title = "Current standing · colleges in this sector"
        return {
            "kind": "current_standing",
            "title": title,
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


def linear_forecast(values: list[float]) -> Optional[dict]:
    """Next-period ordinary least squares on equally spaced yearly averages.

    Requires at least three observations. The projected value is clamped to the
    0–100 score scale. The interval is a 1.96 residual-standard-error band at
    the next index, also clamped. This is not an LLM estimate.
    """
    clean = [float(value) for value in values]
    count = len(clean)
    if count < MIN_FORECAST_OBSERVATIONS:
        return None
    xs = list(range(count))
    x_bar = (count - 1) / 2
    y_bar = sum(clean) / count
    var_x = sum((x - x_bar) ** 2 for x in xs)
    if var_x == 0:
        return None
    slope = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, clean)) / var_x
    intercept = y_bar - slope * x_bar
    next_x = float(count)
    raw = intercept + slope * next_x
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, clean)]
    dof = count - 2
    sigma = (
        (sum(residual * residual for residual in residuals) / dof) ** 0.5
        if dof
        else 0.0
    )
    leverage = 1 + (1 / count) + ((next_x - x_bar) ** 2) / var_x
    margin = 1.96 * sigma * (leverage**0.5)
    predicted = max(0.0, min(100.0, raw))
    direction = "rising" if slope > 0.5 else "falling" if slope < -0.5 else "stable"
    return {
        "method": FORECAST_METHOD,
        "observations": count,
        "value": round(predicted, 1),
        "low": round(max(0.0, min(100.0, raw - margin)), 1),
        "high": round(max(0.0, min(100.0, raw + margin)), 1),
        "slope": round(slope, 2),
        "direction": direction,
        "inputs": [round(value, 1) for value in clean],
    }


async def load_scoped_year_averages(
    db: asyncpg.Connection,
    ctx: UserContext,
    filters: AnalyticsFilters,
) -> list[dict]:
    """Yearly transcript averages inside the already-authorized filter scope."""
    where_sql, args, index = course_org_where(filters)
    student_id = (
        ctx.student_id
        if ctx.role == "student" and ctx.student_id
        else filters.student_id
    )
    if student_id:
        where_sql = f"{where_sql} AND t.student_id = ${index}"
        args.append(student_id)
    rows = await db.fetch(
        f"""
        SELECT y.label AS label, AVG(t.average)::float AS avg, COUNT(*)::int AS n
        FROM transcript_entries t
        JOIN academic_years y ON y.id = t.academic_year_id
        JOIN courses c ON c.id = t.course_id
        JOIN org_units p ON p.id = c.program_id
        WHERE {where_sql}
        GROUP BY y.id, y.label, y.start_date
        ORDER BY y.start_date
        """,
        *args,
    )
    return [
        {"label": row["label"], "avg": float(row["avg"]), "n": int(row["n"])}
        for row in rows
        if row["avg"] is not None
    ]


def _apply_history(result: dict, series: list[dict]) -> dict:
    forecast = linear_forecast([row["avg"] for row in series])
    if forecast:
        labels = ", ".join(f"{row['label']} {round(row['avg'], 1)}" for row in series)
        result["kind"] = "forecast"
        result["method"] = forecast["method"]
        result["observations"] = forecast["observations"]
        result["forecastValue"] = forecast["value"]
        result["intervalLow"] = forecast["low"]
        result["intervalHigh"] = forecast["high"]
        result["direction"] = forecast["direction"]
        result["title"] = "Forecast · next period average"
        result["summary"] = (
            f"Recorded yearly averages in this scope are {labels}. "
            f"A linear projection ({forecast['method']}, {forecast['observations']} observations) "
            f"estimates the next period at {forecast['value']} "
            f"(interval {forecast['low']} to {forecast['high']})."
        )
        result["rows"] = [
            {
                "label": row["label"],
                "value": f"{round(row['avg'], 1)} avg",
                "tone": "iris",
            }
            for row in series
        ] + [
            {
                "label": "Projected next period",
                "value": str(forecast["value"]),
                "tone": "rose" if forecast["direction"] == "falling" else "amber",
            }
        ]
        return result
    if len(series) >= 2:
        delta = series[-1]["avg"] - series[0]["avg"]
        result["direction"] = (
            "rising" if delta > 1 else "falling" if delta < -1 else "stable"
        )
        result["kind"] = "current_standing"
        result["summary"] = (
            f"Year-over-year average moved {delta:+.1f} points across {len(series)} recorded years. "
            "Fewer than 3 yearly averages are available, so this is historical standing, not a forecast."
        )
    return result


async def get_standing_or_forecast(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    ctx_data: dict[str, Any],
) -> Optional[dict]:
    result = current_standing_from_context(ctx.role, ctx_data)
    if result is None:
        return None
    series = await load_scoped_year_averages(db, ctx, filters)
    return _apply_history(result, series)
