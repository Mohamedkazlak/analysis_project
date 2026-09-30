from typing import Literal

import asyncpg

from core.locale import Language, entity, txt
from core.utils import avg, round1
from repositories.sql_filters import attempt_where
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters


def chart_grain(filters: AnalyticsFilters) -> Literal["college", "curriculum", "exam"]:
    """Widen chart categories so university/college views stay readable."""
    if filters.curriculum_id:
        return "exam"
    if filters.college_id:
        return "curriculum"
    return "college"


async def get_participation_report(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language = "en",
):
    filters = filters or AnalyticsFilters()
    where_sql, args, _ = attempt_where(filters)
    grain = chart_grain(filters)

    if grain == "college":
        exam_rows = await db.fetch(
            f"""
            SELECT
                a.program AS exam,
                COUNT(*) FILTER (WHERE a.participated) AS attempts,
                COUNT(*) AS expected,
                COALESCE(
                    AVG(a.time_taken_min)
                      FILTER (WHERE a.participated AND a.time_taken_min IS NOT NULL),
                    0
                ) AS minutes
            FROM v_exam_attempts a
            WHERE {where_sql}
            GROUP BY a.program
            ORDER BY a.program
            """,
            *args,
        )
    elif grain == "curriculum":
        exam_rows = await db.fetch(
            f"""
            SELECT
                a.course_code AS exam,
                COUNT(*) FILTER (WHERE a.participated) AS attempts,
                COUNT(*) AS expected,
                COALESCE(
                    AVG(a.time_taken_min)
                      FILTER (WHERE a.participated AND a.time_taken_min IS NOT NULL),
                    0
                ) AS minutes
            FROM v_exam_attempts a
            WHERE {where_sql}
            GROUP BY a.course_code
            ORDER BY a.course_code
            """,
            *args,
        )
    else:
        exam_rows = await db.fetch(
            f"""
            SELECT
                a.course_code || ' · ' || trim(split_part(a.exam_title, '—', 1)) AS exam,
                COUNT(*) FILTER (WHERE a.participated) AS attempts,
                COUNT(*) AS expected,
                COALESCE(
                    AVG(a.time_taken_min)
                      FILTER (WHERE a.participated AND a.time_taken_min IS NOT NULL),
                    0
                ) AS minutes
            FROM v_exam_attempts a
            WHERE {where_sql}
            GROUP BY a.exam_id, a.course_code, a.exam_title
            ORDER BY a.course_code, a.exam_title
            """,
            *args,
        )

    if not exam_rows:
        return {
            "grain": grain,
            "attemptsPerExam": [],
            "completionRate": 0,
            "attendanceRate": 0,
            "attendanceByCurriculum": [],
            "avgTimePerExam": [],
            "absentees": [],
            "insight": txt(
                language,
                "No attendance rows in this scope yet.",
                "لا صفوف حضور في هذا النطاق بعد.",
            ),
        }

    attempts_per_exam = [
        {
            "exam": (r["exam"] or "").strip(),
            "attempts": int(r["attempts"]),
            "expected": int(r["expected"]),
        }
        for r in exam_rows
    ]
    avg_time_per_exam = [
        {"exam": (r["exam"] or "").strip(), "minutes": round(float(r["minutes"]))}
        for r in exam_rows
    ]

    totals = await db.fetchrow(
        f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE a.participated) AS taken
        FROM v_exam_attempts a
        WHERE {where_sql}
        """,
        *args,
    )
    completion_rate = round1(
        (totals["taken"] / totals["total"] * 100) if totals["total"] else 0
    )

    if grain == "college":
        course_rows = await db.fetch(
            f"""
            SELECT
                a.program AS course,
                COUNT(DISTINCT a.student_id)::int AS students,
                COUNT(DISTINCT a.student_id)
                  FILTER (WHERE a.participated)::int AS participated,
                COUNT(DISTINCT a.student_id)
                  FILTER (WHERE NOT a.participated)::int AS absentees,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE a.participated AND NOT a.late_start) AS present
            FROM v_exam_attempts a
            WHERE {where_sql}
            GROUP BY a.program
            ORDER BY a.program
            """,
            *args,
        )
    else:
        course_rows = await db.fetch(
            f"""
            SELECT
                a.course_code AS course,
                COUNT(DISTINCT a.student_id)::int AS students,
                COUNT(DISTINCT a.student_id)
                  FILTER (WHERE a.participated)::int AS participated,
                COUNT(DISTINCT a.student_id)
                  FILTER (WHERE NOT a.participated)::int AS absentees,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE a.participated AND NOT a.late_start) AS present
            FROM v_exam_attempts a
            WHERE {where_sql}
            GROUP BY a.course_code
            ORDER BY a.course_code
            """,
            *args,
        )

    attendance_by_curriculum = [
        {
            "course": r["course"],
            "students": int(r["students"]),
            "participated": int(r["participated"]),
            "absentees": int(r["absentees"]),
            "attendance": round1(
                (r["present"] / r["total"] * 100) if r["total"] else 0
            ),
        }
        for r in course_rows
    ]
    attendance_rate = round1(avg([r["attendance"] for r in attendance_by_curriculum]))

    absentee_rows = await db.fetch(
        f"""
        SELECT
            a.student_name AS student,
            a.program AS college,
            a.course_code || ' · ' || trim(split_part(a.exam_title, '—', 1)) AS exam,
            CASE WHEN a.participated THEN 'Late start' ELSE 'No attempt' END AS reason
        FROM v_exam_attempts a
        WHERE {where_sql}
          AND (NOT a.participated OR a.late_start)
        ORDER BY a.program, a.student_name
        LIMIT 12
        """,
        *args,
    )
    absentees = [
        {
            "student": r["student"],
            "college": (r["college"] or "").strip() or "Unknown",
            "exam": (r["exam"] or "").strip(),
            "reason": r["reason"],
            "minutesLate": 0,
        }
        for r in absentee_rows
    ]

    weakest = (
        sorted(attendance_by_curriculum, key=lambda x: x["attendance"])[0]
        if attendance_by_curriculum
        else None
    )
    entity_key = {
        "college": "college",
        "curriculum": "curriculum",
        "exam": "curriculum",
    }[grain]
    entity_en = f"{entity_key}s"
    entity_ar = {"college": "الكليات", "curriculum": "المقررات"}[entity_key]
    insight = (
        txt(
            language,
            f"{entity(language, weakest['course'])} has the weakest attendance among "
            f"{entity_en} in this view at {weakest['attendance']}%.",
            f"{entity(language, weakest['course'])} لديها أضعف حضور بين "
            f"{entity_ar} في هذا العرض بنسبة {weakest['attendance']}%.",
        )
        if weakest
        else txt(
            language,
            "No attendance rows in this scope yet.",
            "لا صفوف حضور في هذا النطاق بعد.",
        )
    )

    return {
        "grain": grain,
        "attemptsPerExam": attempts_per_exam,
        "completionRate": completion_rate,
        "attendanceRate": attendance_rate,
        "attendanceByCurriculum": attendance_by_curriculum,
        "avgTimePerExam": avg_time_per_exam,
        "absentees": absentees,
        "insight": insight,
    }
