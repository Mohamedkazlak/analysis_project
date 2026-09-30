import datetime

import asyncpg

from core.locale import Language, txt
from core.utils import PASS_MARK, round1
from repositories.sql_filters import attempt_where
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters


async def get_real_time_struggling(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language = "en",
):
    filters = filters or AnalyticsFilters()
    where_sql, args, _ = attempt_where(filters)

    students = await db.fetch(
        f"""
        SELECT
            a.student_id,
            a.student_name AS name,
            MAX(a.program) AS college,
            (ARRAY_AGG(a.course_code ORDER BY a.started_at DESC NULLS LAST))[1] AS course,
            (ARRAY_AGG(a.score ORDER BY a.started_at DESC NULLS LAST))[1]::float AS last_score,
            AVG(a.score)::float AS average
        FROM v_exam_attempts a
        WHERE a.participated AND a.score IS NOT NULL AND {where_sql}
        GROUP BY a.student_id, a.student_name
        ORDER BY (ARRAY_AGG(a.score ORDER BY a.started_at DESC NULLS LAST))[1]
        LIMIT 12
        """,
        *args,
    )
    students_ranked = [
        {
            "studentId": r["student_id"],
            "name": r["name"],
            "college": (r["college"] or "").strip() or "Unknown",
            "course": r["course"],
            "lastScore": float(r["last_score"]),
            "average": round1(r["average"]),
            "trend": round(float(r["last_score"]) - float(r["average"])),
            "lastActivity": "recently",
        }
        for r in students
    ]

    live = await db.fetch(
        f"""
        SELECT
            a.exam_id,
            a.exam_title,
            a.course_code,
            a.program,
            a.sector,
            x.status AS exam_status,
            COUNT(*) FILTER (WHERE a.status = 'in_progress') AS active_now,
            COUNT(*) FILTER (WHERE a.status = 'submitted') AS submitted,
            COUNT(*) AS expected,
            COUNT(*) FILTER (
                WHERE a.attempt_count > 1
                   OR a.late_start
                   OR (a.time_taken_min IS NOT NULL AND a.time_taken_min < 25)
            ) AS flagged
        FROM v_exam_attempts a
        JOIN exams x ON x.id = a.exam_id
        WHERE x.status IN ('in_progress', 'closing')
          AND {where_sql}
        GROUP BY a.exam_id, a.exam_title, a.course_code, a.program, a.sector, x.status
        """,
        *args,
    )
    live_exams = [
        {
            "examId": r["exam_id"],
            "exam": f"{r['course_code']} · {(r['exam_title'] or '').split('—')[0].strip()}",
            "program": r["program"],
            "sector": r["sector"],
            "activeNow": int(r["active_now"]),
            "submitted": int(r["submitted"]),
            "expected": int(r["expected"]),
            "flagged": int(r["flagged"]),
            "status": "Closing" if r["exam_status"] == "closing" else "In progress",
        }
        for r in live
    ]
    active_now = sum(e["activeNow"] for e in live_exams)
    insight = (
        txt(
            language,
            f"Live monitoring covers {len(live_exams)} sittings right now.",
            f"المراقبة الحية تغطي {len(live_exams)} جلسة الآن.",
        )
        if live_exams
        else txt(
            language,
            "No exams currently in progress in this scope.",
            "لا امتحانات جارية حاليًا في هذا النطاق.",
        )
    )
    return {
        "students": students_ranked,
        "liveExams": live_exams,
        "updatedAt": datetime.datetime.utcnow().isoformat(),
        "activeNow": active_now,
        "insight": insight,
    }
