import asyncpg

from core.locale import Language, entity, txt
from core.utils import PASS_MARK
from repositories.sql_filters import attempt_where, student_where
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters


async def get_management_overview(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language = "en",
) -> dict:
    filters = filters or AnalyticsFilters()
    where_sql, args, _ = attempt_where(filters)
    stu_where, stu_args, _ = student_where(filters)

    enrolled_rows = await db.fetch(
        f"""
        SELECT
            grouping(s.program) AS g_college,
            s.program AS college,
            COUNT(*)::int AS enrolled
        FROM v_students s
        WHERE {stu_where}
        GROUP BY GROUPING SETS ((s.program), ())
        """,
        *stu_args,
    )
    enrolled_total = int(
        next((r["enrolled"] for r in enrolled_rows if r["g_college"] == 1), 0) or 0
    )
    enrolled_by_college = {
        r["college"]: int(r["enrolled"] or 0)
        for r in enrolled_rows
        if r["g_college"] == 0
    }

    grain_rows = await db.fetch(
        f"""
        SELECT
            grouping(a.course_code) AS g_course,
            grouping(a.program) AS g_program,
            a.course_code AS course,
            a.program AS college,
            COUNT(*) AS total_attempts,
            COUNT(*) FILTER (WHERE a.status <> 'absent') AS taken_attempts,
            COUNT(*) FILTER (WHERE a.status <> 'absent' AND NOT a.late_start) AS on_time_attempts,
            COUNT(*) FILTER (WHERE a.status <> 'absent' AND a.score >= {PASS_MARK}) AS passed_attempts,
            COUNT(DISTINCT a.exam_id) AS total_exams,
            COUNT(DISTINCT a.course_id) AS courses
        FROM v_exam_attempts a
        WHERE {where_sql}
        GROUP BY GROUPING SETS ((a.course_code), (a.program), ())
        """,
        *args,
    )

    stats = next(
        (r for r in grain_rows if r["g_course"] == 1 and r["g_program"] == 1),
        None,
    )
    total_exams = (stats["total_exams"] if stats else 0) or 0
    courses_by_college = {
        r["college"]: int(r["courses"] or 0) for r in grain_rows if r["g_program"] == 0
    }

    standing_rows = await db.fetch(
        f"""
        SELECT
            grouping(s.college) AS g_college,
            s.college,
            COUNT(*) AS students,
            COUNT(*) FILTER (WHERE s.sat > 0) AS sat,
            COUNT(*) FILTER (
                WHERE s.sat > 0 AND s.avg_score >= {PASS_MARK}
            ) AS passed,
            COUNT(*) FILTER (
                WHERE s.sat > 0
                  AND (s.avg_score IS NULL OR s.avg_score < {PASS_MARK})
            ) AS failed,
            COUNT(*) FILTER (
                WHERE s.sat > 0 AND s.late = 0 AND s.absent = 0
            ) AS on_time,
            COUNT(*) FILTER (WHERE s.late > 0) AS late,
            COUNT(*) FILTER (WHERE s.absent > 0) AS absent,
            COUNT(*) FILTER (WHERE s.sat = s.expected) AS sat_all
        FROM (
            SELECT
                a.program AS college,
                a.student_id,
                COUNT(*) AS expected,
                COUNT(*) FILTER (WHERE a.status <> 'absent') AS sat,
                COUNT(*) FILTER (
                    WHERE a.status <> 'absent' AND a.late_start
                ) AS late,
                COUNT(*) FILTER (WHERE a.status = 'absent') AS absent,
                AVG(a.score) FILTER (WHERE a.status <> 'absent') AS avg_score
            FROM v_exam_attempts a
            WHERE {where_sql}
            GROUP BY a.program, a.student_id
        ) s
        GROUP BY GROUPING SETS ((s.college), ())
        """,
        *args,
    )

    university = next((r for r in standing_rows if r["g_college"] == 1), None)
    sitters = int((university["sat"] if university else 0) or 0)
    expected_students = int((university["students"] if university else 0) or 0)
    passed_students = int((university["passed"] if university else 0) or 0)
    on_time_students = int((university["on_time"] if university else 0) or 0)
    # KPI / totals "students" is roster headcount for the filtered scope.
    students = enrolled_total
    pass_rate = (passed_students / sitters * 100) if sitters else 0
    attendance = (
        (on_time_students / expected_students * 100) if expected_students else 0
    )

    pass_rate_value = round(pass_rate, 1)
    attendance_value = round(attendance, 1)
    totals = {
        "exams": int(total_exams or 0),
        "students": students,
        "sitters": sitters,
        "passRate": pass_rate_value,
        "attendance": attendance_value,
        "colleges": 0,
    }

    kpis = [
        {
            "label": txt(language, "Exams administered", "الامتحانات المُدارة"),
            "value": str(totals["exams"]),
        },
        {
            "label": txt(language, "Students", "الطلاب"),
            "value": str(students),
        },
        {
            "label": txt(language, "Student pass rate", "معدل نجاح الطلاب"),
            "value": f"{pass_rate_value:.1f}%",
        },
        {
            "label": txt(language, "Attendance", "الحضور"),
            "value": f"{attendance_value:.1f}%",
        },
    ]

    pass_rate_by_course = [
        {
            "course": r["course"],
            "passRate": round(
                (
                    (r["passed_attempts"] / r["taken_attempts"] * 100)
                    if r["taken_attempts"]
                    else 0
                ),
                1,
            ),
            "participants": r["taken_attempts"],
        }
        for r in grain_rows
        if r["g_course"] == 0
    ]
    pass_rate_by_college = []
    for r in standing_rows:
        if r["g_college"] != 0:
            continue
        expected = int(r["students"] or 0)
        sat = int(r["sat"] or 0)
        passed = int(r["passed"] or 0)
        on_time = int(r["on_time"] or 0)
        sat_all_college = int(r["sat_all"] or 0)
        pass_rate_by_college.append(
            {
                "college": r["college"],
                "passRate": round((passed / sat * 100) if sat else 0, 1),
                "participants": sat,
                "students": enrolled_by_college.get(r["college"], 0),
                "courses": courses_by_college.get(r["college"], 0),
                "attendance": round((on_time / expected * 100) if expected else 0, 1),
                "participation": round(
                    (sat_all_college / expected * 100) if expected else 0, 1
                ),
                "expected": expected,
                "onTime": on_time,
                "late": int(r["late"] or 0),
                "absent": int(r["absent"] or 0),
                "passed": passed,
                "failed": int(r["failed"] or 0),
            }
        )

    timeline_rows = await db.fetch(
        """
        SELECT
            to_char(date_trunc('month', x.scheduled_at), 'Mon') AS month,
            extract(year FROM x.scheduled_at)::int AS year,
            extract(month FROM x.scheduled_at)::int AS month_num,
            t.id AS term_id,
            t.name AS term_name,
            count(DISTINCT x.id) AS exams,
            count(DISTINCT a.student_id) FILTER (WHERE a.status <> 'absent') AS participants
        FROM exams x
        JOIN course_offerings o ON o.id = x.offering_id
        JOIN terms t ON t.id = o.term_id
        JOIN courses c ON c.id = o.course_id
        JOIN org_units p ON p.id = c.program_id
        JOIN org_units sec ON sec.id = p.parent_id
        LEFT JOIN exam_attempts a ON a.exam_id = x.id
        WHERE ($1::text IS NULL OR sec.id = $1)
          AND ($2::text IS NULL OR p.id = $2)
          AND ($3::text IS NULL OR c.id = $3)
          AND ($4::text IS NULL OR a.student_id = $4)
          AND (
            $5::text IS NULL
            OR EXISTS (
              SELECT 1 FROM staff_course_assignments sca
              WHERE sca.staff_person_id = $5 AND sca.course_id = c.id
            )
          )
        GROUP BY 1, 2, 3, 4, 5
        ORDER BY 2, 3
        """,
        filters.sector_id,
        filters.college_id,
        filters.curriculum_id,
        filters.student_id,
        filters.professor_id,
    )
    timeline = [
        {
            "month": r["month"],
            "exams": r["exams"],
            "participants": r["participants"],
            "year": r["year"],
            "monthNum": r["month_num"],
            "termId": r["term_id"],
            "termName": r["term_name"],
        }
        for r in timeline_rows
    ]

    exam_rows = await db.fetch(
        f"""
        SELECT
            a.exam_id,
            a.exam_title,
            a.course_code,
            a.program AS college,
            t.id AS term_id,
            t.name AS term_name,
            to_char(date_trunc('month', a.scheduled_at), 'Mon') AS month,
            extract(year FROM a.scheduled_at)::int AS year,
            extract(month FROM a.scheduled_at)::int AS month_num,
            COUNT(*) FILTER (WHERE a.status <> 'absent') AS sittings,
            COUNT(*) FILTER (
                WHERE a.status <> 'absent' AND a.score >= {PASS_MARK}
            ) AS passed,
            COUNT(*) FILTER (
                WHERE a.status <> 'absent'
                  AND (a.score IS NULL OR a.score < {PASS_MARK})
            ) AS failed,
            COUNT(*) FILTER (WHERE a.status = 'absent') AS absent,
            COUNT(*) FILTER (
                WHERE a.status <> 'absent' AND a.late_start
            ) AS late,
            ROUND(
                AVG(a.score) FILTER (WHERE a.status <> 'absent')::numeric,
                1
            ) AS avg_score
        FROM v_exam_attempts a
        JOIN exams x ON x.id = a.exam_id
        JOIN course_offerings o ON o.id = x.offering_id
        JOIN terms t ON t.id = o.term_id
        WHERE {where_sql}
        GROUP BY
            a.exam_id,
            a.exam_title,
            a.course_code,
            a.program,
            t.id,
            t.name,
            extract(year FROM a.scheduled_at),
            extract(month FROM a.scheduled_at),
            to_char(date_trunc('month', a.scheduled_at), 'Mon')
        ORDER BY MIN(a.scheduled_at), a.course_code
        """,
        *args,
    )
    exam_summaries = [
        {
            "examId": r["exam_id"],
            "title": r["exam_title"],
            "course": r["course_code"],
            "college": r["college"],
            "termId": r["term_id"],
            "termName": r["term_name"],
            "month": r["month"],
            "year": r["year"],
            "monthNum": r["month_num"],
            "sittings": int(r["sittings"] or 0),
            "passed": int(r["passed"] or 0),
            "failed": int(r["failed"] or 0),
            "absent": int(r["absent"] or 0),
            "late": int(r["late"] or 0),
            "avgScore": float(r["avg_score"] or 0),
        }
        for r in exam_rows
    ]

    totals["colleges"] = len(pass_rate_by_college)
    if not pass_rate_by_college:
        insight = txt(
            language,
            "No exam attempts in this scope yet.",
            "لا توجد محاولات امتحان في هذا النطاق بعد.",
        )
    elif (
        not filters.sector_id
        and not filters.college_id
        and len(pass_rate_by_college) > 1
    ):
        insight = txt(
            language,
            (
                f"University student pass rate is {pass_rate_value:.1f}% across "
                f"{len(pass_rate_by_college)} colleges and {students} enrolled students. "
                f"Attendance is {attendance_value:.1f}%."
            ),
            (
                f"معدل نجاح طلاب الجامعة هو {pass_rate_value:.1f}% عبر "
                f"{len(pass_rate_by_college)} كليات و{students} طالبًا مسجّلًا. "
                f"الحضور {attendance_value:.1f}%."
            ),
        )
    elif len(pass_rate_by_college) == 1:
        only = pass_rate_by_college[0]
        college = entity(language, only["college"])
        enrolled = only["students"] or only["participants"]
        insight = txt(
            language,
            (
                f"{college} student pass rate is {only['passRate']}% across "
                f"{enrolled} enrolled students in this view."
            ),
            (
                f"معدل نجاح طلاب {college} هو {only['passRate']}% عبر "
                f"{enrolled} طالبًا مسجّلًا في هذا العرض."
            ),
        )
    else:
        weakest = min(pass_rate_by_college, key=lambda r: r["passRate"])
        strongest = max(pass_rate_by_college, key=lambda r: r["passRate"])
        place = txt(
            language,
            (
                "this sector"
                if filters.sector_id and not filters.college_id
                else "this view"
            ),
            (
                "هذا القطاع"
                if filters.sector_id and not filters.college_id
                else "هذا العرض"
            ),
        )
        weak_name = entity(language, weakest["college"])
        strong_name = entity(language, strongest["college"])
        insight = txt(
            language,
            (
                f"{weak_name} has the lowest student pass rate in {place} "
                f"at {weakest['passRate']}%, while {strong_name} leads at "
                f"{strongest['passRate']}%."
            ),
            (
                f"{weak_name} لديها أدنى معدل نجاح طلابي في {place} "
                f"بنسبة {weakest['passRate']}%، بينما تتصدر {strong_name} بنسبة "
                f"{strongest['passRate']}%."
            ),
        )

    contains_synthetic = bool(
        await db.fetchval(
            f"""
            SELECT EXISTS (
              SELECT 1
              FROM v_exam_attempts a
              JOIN exams x ON x.id = a.exam_id
              WHERE ({where_sql}) AND x.is_synthetic
            )
            """,
            *args,
        )
    )

    return {
        "kpis": kpis,
        "passRateByCourse": pass_rate_by_course,
        "passRateByCollege": pass_rate_by_college,
        "activityTrend": timeline,
        "examSummaries": exam_summaries,
        "insight": insight,
        "totals": totals,
        "containsSynthetic": contains_synthetic,
    }
