import asyncpg

from core.utils import PASS_MARK, round1
from repositories.sql_filters import attempt_where, course_org_where
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters


async def get_course_performance(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
):
    filters = filters or AnalyticsFilters()
    where_sql, args, _ = attempt_where(filters)
    participated = f"{where_sql} AND a.participated AND a.score IS NOT NULL"

    course_rows = await db.fetch(
        f"""
        SELECT
            a.course_id,
            a.course_code,
            c.name AS course_name,
            p.name AS college,
            AVG(a.score)::float AS average,
            COUNT(*) FILTER (WHERE a.score >= {PASS_MARK}) AS passed,
            COUNT(*) AS scored
        FROM v_exam_attempts a
        JOIN courses c ON c.id = a.course_id
        JOIN org_units p ON p.id = c.program_id
        WHERE {participated}
        GROUP BY a.course_id, a.course_code, c.name, p.name
        ORDER BY p.name, c.name
        """,
        *args,
    )
    if not course_rows:
        return {
            "averageByCourse": [],
            "sections": [],
            "assignedCourses": [],
            "insight": "No course rows in this scope yet.",
        }

    enroll_sql, enroll_args, _ = course_org_where(filters)
    enroll_rows = await db.fetch(
        f"""
        SELECT
            c.id AS course_id,
            COUNT(e.id)::int AS enrolled
        FROM courses c
        JOIN org_units p ON p.id = c.program_id
        JOIN course_offerings o ON o.course_id = c.id
        JOIN enrollments e ON e.offering_id = o.id
        WHERE {enroll_sql}
        GROUP BY c.id
        """,
        *enroll_args,
    )
    enrolled_by_course = {r["course_id"]: r["enrolled"] for r in enroll_rows}

    average_by_course = []
    sections = []
    for r in course_rows:
        mean = float(r["average"])
        scored = r["scored"] or 0
        pass_rate = (r["passed"] / scored * 100) if scored else 0
        course_name = r["course_name"]
        average_by_course.append(
            {
                "course": course_name,
                "courseCode": r["course_code"],
                "average": round1(mean),
                "quality": round(min(10, max(1, mean / 10 + 0.6)), 1),
            }
        )
        sections.append(
            {
                "section": course_name,
                "course": course_name,
                "courseCode": r["course_code"],
                "college": r["college"] or "Unknown",
                "average": round1(mean),
                "passRate": round1(pass_rate),
                "enrolled": enrolled_by_course.get(r["course_id"], 0),
            }
        )

    assigned = []
    if ctx.role == "professor" and ctx.person_id:
        assigned_rows = await db.fetch(
            """
            SELECT
                c.id,
                c.code,
                c.name,
                (
                    SELECT COUNT(*)::int
                    FROM enrollments e
                    JOIN course_offerings o ON o.id = e.offering_id
                    WHERE o.course_id = c.id
                ) AS enrolled,
                ARRAY(
                    SELECT DISTINCT cs.code
                    FROM course_sections cs
                    JOIN course_offerings o ON o.id = cs.offering_id
                    WHERE o.course_id = c.id
                    ORDER BY cs.code
                ) AS sections
            FROM courses c
            JOIN staff_course_assignments sca
              ON sca.course_id = c.id AND sca.staff_person_id = $1
            ORDER BY c.code
            """,
            ctx.person_id,
        )
        assigned = [
            {
                "id": r["id"],
                "code": r["code"],
                "name": r["name"],
                "enrolled": r["enrolled"],
                "sections": list(r["sections"] or []),
            }
            for r in assigned_rows
        ]

    weakest = sorted(sections, key=lambda x: x["average"])[0] if sections else None
    insight = (
        f"{weakest['course']} has the lowest average in this scope at {weakest['average']}."
        if weakest
        else "No course rows in this scope yet."
    )

    return {
        "averageByCourse": average_by_course,
        "sections": sections,
        "assignedCourses": assigned,
        "insight": insight,
    }
