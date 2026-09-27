from typing import Optional

import asyncpg
from fastapi import HTTPException

from core.authorization import AuthScope, apply_scope_defaults, assert_filters_in_scope
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters


async def load_auth_scope(db: asyncpg.Connection, user_id: str) -> AuthScope:
    row = await db.fetchrow(
        """
        SELECT
          u.id AS user_id,
          u.role::text AS role,
          u.person_id,
          u.scope_id,
          u.student_id,
          u.is_active,
          p.full_name AS name,
          st.title AS staff_title,
          o.level::text AS scope_level,
          o.name AS scope_name,
          o.title_for_role,
          o.parent_id AS scope_parent_id,
          parent.name AS parent_name,
          parent.level::text AS parent_level,
          parent.parent_id AS parent_parent_id,
          uni.name AS university_name
        FROM user_accounts u
        JOIN people p ON p.id = u.person_id
        LEFT JOIN staff st ON st.person_id = u.person_id
        LEFT JOIN org_units o ON o.id = u.scope_id
        LEFT JOIN org_units parent ON parent.id = o.parent_id
        LEFT JOIN org_units uni ON uni.level = 'university'
        WHERE u.id = $1
        """,
        user_id,
    )
    if not row or row["is_active"] is not True:
        raise HTTPException(status_code=401, detail="Account not found")

    role = row["role"]
    scope_level = row["scope_level"]
    sector_id = None
    college_id = None
    sector_name = None
    college_name = None

    if scope_level == "university":
        pass
    elif scope_level == "sector":
        sector_id = row["scope_id"]
        sector_name = row["scope_name"]
    elif scope_level == "program":
        college_id = row["scope_id"]
        college_name = row["scope_name"]
        if row["parent_level"] == "sector":
            sector_id = row["scope_parent_id"]
            sector_name = row["parent_name"]

    course_ids: list[str] = []
    if role == "professor":
        courses = await db.fetch(
            """
            SELECT course_id
            FROM staff_course_assignments
            WHERE staff_person_id = $1
            """,
            row["person_id"],
        )
        course_ids = [c["course_id"] for c in courses]

    display_role = _display_role(
        role, scope_level, row["title_for_role"], row["staff_title"]
    )
    scope_label = _scope_label(
        role=role,
        scope_level=scope_level,
        university=row["university_name"] or "Benha National University",
        sector_name=sector_name,
        college_name=college_name,
        course_ids=course_ids,
    )
    title = row["staff_title"] or display_role

    return AuthScope(
        user_id=row["user_id"],
        role=role,
        person_id=row["person_id"],
        scope_id=row["scope_id"],
        scope_level=scope_level,
        student_id=row["student_id"],
        sector_id=sector_id,
        college_id=college_id,
        name=row["name"],
        title=title,
        display_role=display_role,
        university_name=row["university_name"] or "Benha National University",
        sector_name=sector_name,
        college_name=college_name,
        scope_label=scope_label,
        course_ids=course_ids,
    )


def user_context_from_scope(scope: AuthScope) -> UserContext:
    return UserContext(
        user_id=scope.user_id,
        role=scope.role,
        scope_id=scope.scope_id,
        person_id=scope.person_id,
        student_id=scope.student_id,
        name=scope.name,
        title=scope.title,
        display_role=scope.display_role,
        scope_level=scope.scope_level,
        sector_id=scope.sector_id,
        college_id=scope.college_id,
        sector_name=scope.sector_name,
        college_name=scope.college_name,
        university_name=scope.university_name,
        scope_label=scope.scope_label,
        course_ids=scope.course_ids,
    )


def _display_role(
    role: str,
    scope_level: Optional[str],
    title_for_role: Optional[str],
    staff_title: Optional[str],
) -> str:
    if role == "senior_management":
        if scope_level == "sector":
            return "Sector Dean"
        if staff_title:
            return staff_title
        return title_for_role or "Senior Management"
    if role == "program_director":
        return "Program Director"
    if role == "academic_affairs":
        return "Academic Affairs"
    if role == "professor":
        if staff_title and "professor" in staff_title.lower():
            return staff_title
        return "Professor"
    if role == "it_academic_integrity":
        return "Academic Integrity"
    if role == "student":
        return "Student"
    return role


def _scope_label(
    *,
    role: str,
    scope_level: Optional[str],
    university: str,
    sector_name: Optional[str],
    college_name: Optional[str],
    course_ids: list[str],
) -> str:
    if role == "it_academic_integrity":
        return "University-wide · live exam monitoring"
    if role == "professor":
        return "Assigned curriculum" if course_ids else "Assigned curriculum (none)"
    if scope_level == "sector" and sector_name:
        return f"{sector_name} · sector"
    if scope_level == "program" and college_name:
        return f"{college_name} · college"
    return f"{university} · university-wide"


async def validate_analytics_filters(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    require_complete: bool = True,
) -> AnalyticsFilters:
    """Authorize requested filters against the live account, then verify hierarchy in SQL."""
    scope = await load_auth_scope(db, ctx.user_id)
    narrowed = apply_scope_defaults(scope, filters)
    assert_filters_in_scope(scope, narrowed, require_complete=require_complete)
    await _assert_hierarchy(db, scope, narrowed)
    return narrowed


async def _assert_hierarchy(
    db: asyncpg.Connection,
    scope: AuthScope,
    filters: AnalyticsFilters,
) -> None:
    if filters.sector_id:
        row = await db.fetchrow(
            "SELECT id, level::text AS level FROM org_units WHERE id = $1",
            filters.sector_id,
        )
        if not row or row["level"] != "sector":
            raise HTTPException(status_code=400, detail="Invalid sectorId")

    if filters.college_id:
        row = await db.fetchrow(
            "SELECT id, level::text AS level, parent_id FROM org_units WHERE id = $1",
            filters.college_id,
        )
        if not row or row["level"] != "program":
            raise HTTPException(status_code=400, detail="Invalid collegeId")
        if filters.sector_id and row["parent_id"] != filters.sector_id:
            raise HTTPException(
                status_code=400, detail="College does not belong to the selected sector"
            )
        if scope.role == "senior_management" and scope.scope_level == "sector":
            if scope.sector_id and row["parent_id"] != scope.sector_id:
                raise HTTPException(
                    status_code=403, detail="College is outside your authorized sector"
                )

    if filters.curriculum_id:
        row = await db.fetchrow(
            "SELECT id, program_id FROM courses WHERE id = $1",
            filters.curriculum_id,
        )
        if not row:
            raise HTTPException(status_code=403, detail="Curriculum is not accessible")
        if filters.college_id and row["program_id"] != filters.college_id:
            raise HTTPException(
                status_code=400,
                detail="Curriculum does not belong to the selected college",
            )
        if scope.role == "professor" and row["id"] not in scope.course_ids:
            raise HTTPException(
                status_code=403,
                detail="Curriculum is not in your assigned teaching scope",
            )

    if filters.student_id:
        row = await db.fetchrow(
            "SELECT id, program_id FROM students WHERE id = $1",
            filters.student_id,
        )
        if not row:
            raise HTTPException(status_code=403, detail="Student is not accessible")
        if filters.college_id and row["program_id"] != filters.college_id:
            raise HTTPException(
                status_code=403, detail="Student is not in the selected college"
            )
        if scope.role == "professor":
            assigned = await db.fetchrow(
                """
                SELECT 1
                FROM enrollments e
                JOIN course_offerings o ON o.id = e.offering_id
                JOIN staff_course_assignments sca
                  ON sca.course_id = o.course_id
                 AND sca.staff_person_id = $2
                WHERE e.student_id = $1
                  AND ($3::text IS NULL OR o.course_id = $3)
                LIMIT 1
                """,
                filters.student_id,
                scope.person_id,
                filters.curriculum_id,
            )
            if not assigned:
                raise HTTPException(
                    status_code=403,
                    detail="Student is not in your assigned teaching scope",
                )

    if filters.professor_id:
        person = await db.fetchrow(
            "SELECT id FROM people WHERE id = $1",
            filters.professor_id,
        )
        if not person:
            raise HTTPException(status_code=400, detail="Invalid professorId")
        taught = await db.fetchrow(
            """
            SELECT 1
            FROM staff_course_assignments sca
            JOIN courses c ON c.id = sca.course_id
            JOIN org_units p ON p.id = c.program_id
            WHERE sca.staff_person_id = $1
              AND ($2::text IS NULL OR p.parent_id = $2)
              AND ($3::text IS NULL OR c.program_id = $3)
              AND ($4::text IS NULL OR c.id = $4)
            LIMIT 1
            """,
            filters.professor_id,
            filters.sector_id,
            filters.college_id,
            filters.curriculum_id,
        )
        if not taught:
            raise HTTPException(
                status_code=403, detail="Professor is outside the selected scope"
            )
        if scope.role == "professor" and filters.professor_id != scope.person_id:
            raise HTTPException(
                status_code=403,
                detail="Professor filter is outside your teaching scope",
            )
        if filters.student_id:
            enrolled = await db.fetchrow(
                """
                SELECT 1
                FROM enrollments e
                JOIN course_offerings o ON o.id = e.offering_id
                JOIN staff_course_assignments sca
                  ON sca.course_id = o.course_id
                 AND sca.staff_person_id = $2
                WHERE e.student_id = $1
                  AND ($3::text IS NULL OR o.course_id = $3)
                LIMIT 1
                """,
                filters.student_id,
                filters.professor_id,
                filters.curriculum_id,
            )
            if not enrolled:
                raise HTTPException(
                    status_code=403,
                    detail="Student is not in the selected professor's teaching scope",
                )
