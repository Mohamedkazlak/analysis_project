"""Role-aware table lists and row filters for generated SQL.

Role chooses the tables. Scope chooses the rows. Assignment chooses a
professor's rows. The model is not consulted.
"""

from dataclasses import dataclass
from typing import Any

from rag.errors import QueryRejected
from schemas.auth import UserContext

CALENDAR = frozenset({"academic_years", "terms"})

UNIVERSITY_TABLES = frozenset(
    {
        "org_units",
        "academic_years",
        "terms",
        "people",
        "staff",
        "students",
        "courses",
        "course_offerings",
        "course_sections",
        "staff_course_assignments",
        "enrollments",
        "exams",
        "questions",
        "exam_attempts",
        "attempt_answers",
        "integrity_flags",
        "transcript_entries",
    }
)

FACULTY_TABLES = frozenset(
    {
        "org_units",
        "academic_years",
        "terms",
        "people",
        "staff",
        "students",
        "courses",
        "course_offerings",
        "course_sections",
        "staff_course_assignments",
        "enrollments",
        "exams",
        "exam_attempts",
        "transcript_entries",
    }
)

PROFESSOR_TABLES = frozenset(
    {
        "courses",
        "course_offerings",
        "course_sections",
        "exams",
        "questions",
        "exam_attempts",
        "attempt_answers",
        "enrollments",
        "students",
        "people",
    }
)

INTEGRITY_TABLES = frozenset(
    {
        "exam_attempts",
        "integrity_flags",
        "exams",
        "enrollments",
        "courses",
        "course_offerings",
        "students",
        "people",
    }
)

STUDENT_TABLES = frozenset(
    {
        "transcript_entries",
        "enrollments",
        "exam_attempts",
        "courses",
        "course_offerings",
        "students",
        "people",
    }
)

# Never expose these through generated SQL, even if a role list is edited later.
DENIED_TABLES = frozenset(
    {
        "api_keys",
        "user_accounts",
        "chat_query_log",
        "schema_migrations",
    }
)

_PROGRAMS_IN_SECTOR = (
    "(SELECT id FROM org_units WHERE parent_id = $1 AND level = 'program')"
)


@dataclass(frozen=True)
class ScopePlan:
    tables: frozenset[str]
    filters: dict[str, str]
    bind: Any
    must_filter: bool
    unscoped_ok: frozenset[str]


def _college_filters() -> dict[str, str]:
    return {
        "org_units": (
            "({ref}.id = $1 OR {ref}.id = (SELECT parent_id FROM org_units WHERE id = $1) "
            "OR {ref}.level = 'university')"
        ),
        "people": (
            "({ref}.id IN (SELECT person_id FROM students WHERE program_id = $1) "
            "OR {ref}.id IN (SELECT person_id FROM staff WHERE org_unit_id = $1 "
            "OR person_id IN (SELECT sca.staff_person_id FROM staff_course_assignments sca "
            "JOIN courses c ON c.id = sca.course_id WHERE c.program_id = $1)))"
        ),
        "staff": (
            "({ref}.org_unit_id = $1 OR {ref}.person_id IN ("
            "SELECT sca.staff_person_id FROM staff_course_assignments sca "
            "JOIN courses c ON c.id = sca.course_id WHERE c.program_id = $1))"
        ),
        "students": "{ref}.program_id = $1",
        "courses": "{ref}.program_id = $1",
        "course_offerings": "{ref}.course_id IN (SELECT id FROM courses WHERE program_id = $1)",
        "course_sections": (
            "{ref}.offering_id IN (SELECT o.id FROM course_offerings o "
            "JOIN courses c ON c.id = o.course_id WHERE c.program_id = $1)"
        ),
        "staff_course_assignments": (
            "{ref}.course_id IN (SELECT id FROM courses WHERE program_id = $1)"
        ),
        "enrollments": "{ref}.student_id IN (SELECT id FROM students WHERE program_id = $1)",
        "exams": (
            "{ref}.offering_id IN (SELECT o.id FROM course_offerings o "
            "JOIN courses c ON c.id = o.course_id WHERE c.program_id = $1)"
        ),
        "questions": (
            "{ref}.exam_id IN (SELECT e.id FROM exams e "
            "JOIN course_offerings o ON o.id = e.offering_id "
            "JOIN courses c ON c.id = o.course_id WHERE c.program_id = $1)"
        ),
        "exam_attempts": "{ref}.student_id IN (SELECT id FROM students WHERE program_id = $1)",
        "attempt_answers": (
            "{ref}.attempt_id IN (SELECT a.id FROM exam_attempts a "
            "JOIN students s ON s.id = a.student_id WHERE s.program_id = $1)"
        ),
        "transcript_entries": (
            "{ref}.student_id IN (SELECT id FROM students WHERE program_id = $1)"
        ),
    }


def _sector_filters() -> dict[str, str]:
    prog = _PROGRAMS_IN_SECTOR
    return {
        "org_units": "({ref}.id = $1 OR {ref}.parent_id = $1 OR {ref}.level = 'university')",
        "people": (
            f"({{ref}}.id IN (SELECT person_id FROM students WHERE program_id IN {prog}) "
            f"OR {{ref}}.id IN (SELECT person_id FROM staff WHERE org_unit_id = $1 "
            f"OR org_unit_id IN {prog}))"
        ),
        "staff": f"({{ref}}.org_unit_id = $1 OR {{ref}}.org_unit_id IN {prog})",
        "students": f"{{ref}}.program_id IN {prog}",
        "courses": f"{{ref}}.program_id IN {prog}",
        "course_offerings": (
            f"{{ref}}.course_id IN (SELECT id FROM courses WHERE program_id IN {prog})"
        ),
        "course_sections": (
            f"{{ref}}.offering_id IN (SELECT o.id FROM course_offerings o "
            f"JOIN courses c ON c.id = o.course_id WHERE c.program_id IN {prog})"
        ),
        "staff_course_assignments": (
            f"{{ref}}.course_id IN (SELECT id FROM courses WHERE program_id IN {prog})"
        ),
        "enrollments": (
            f"{{ref}}.student_id IN (SELECT id FROM students WHERE program_id IN {prog})"
        ),
        "exams": (
            f"{{ref}}.offering_id IN (SELECT o.id FROM course_offerings o "
            f"JOIN courses c ON c.id = o.course_id WHERE c.program_id IN {prog})"
        ),
        "questions": (
            f"{{ref}}.exam_id IN (SELECT e.id FROM exams e "
            f"JOIN course_offerings o ON o.id = e.offering_id "
            f"JOIN courses c ON c.id = o.course_id WHERE c.program_id IN {prog})"
        ),
        "exam_attempts": (
            f"{{ref}}.student_id IN (SELECT id FROM students WHERE program_id IN {prog})"
        ),
        "attempt_answers": (
            f"{{ref}}.attempt_id IN (SELECT a.id FROM exam_attempts a "
            f"JOIN students s ON s.id = a.student_id WHERE s.program_id IN {prog})"
        ),
        "integrity_flags": (
            f"{{ref}}.attempt_id IN (SELECT a.id FROM exam_attempts a "
            f"JOIN students s ON s.id = a.student_id WHERE s.program_id IN {prog})"
        ),
        "transcript_entries": (
            f"{{ref}}.student_id IN (SELECT id FROM students WHERE program_id IN {prog})"
        ),
    }


def _professor_filters() -> dict[str, str]:
    courses = "$1::text[]"
    return {
        "courses": f"{{ref}}.id = ANY({courses})",
        "course_offerings": f"{{ref}}.course_id = ANY({courses})",
        "course_sections": (
            f"{{ref}}.offering_id IN (SELECT id FROM course_offerings WHERE course_id = ANY({courses}))"
        ),
        "exams": (
            f"{{ref}}.offering_id IN (SELECT id FROM course_offerings WHERE course_id = ANY({courses}))"
        ),
        "questions": (
            f"{{ref}}.exam_id IN (SELECT e.id FROM exams e "
            f"JOIN course_offerings o ON o.id = e.offering_id WHERE o.course_id = ANY({courses}))"
        ),
        "exam_attempts": (
            f"{{ref}}.exam_id IN (SELECT e.id FROM exams e "
            f"JOIN course_offerings o ON o.id = e.offering_id WHERE o.course_id = ANY({courses}))"
        ),
        "attempt_answers": (
            f"{{ref}}.attempt_id IN (SELECT a.id FROM exam_attempts a "
            f"JOIN exams e ON e.id = a.exam_id "
            f"JOIN course_offerings o ON o.id = e.offering_id WHERE o.course_id = ANY({courses}))"
        ),
        "enrollments": (
            f"{{ref}}.offering_id IN (SELECT id FROM course_offerings WHERE course_id = ANY({courses}))"
        ),
        "students": (
            f"{{ref}}.id IN (SELECT e.student_id FROM enrollments e "
            f"JOIN course_offerings o ON o.id = e.offering_id WHERE o.course_id = ANY({courses}))"
        ),
        "people": (
            f"({{ref}}.id IN (SELECT s.person_id FROM students s "
            f"JOIN enrollments e ON e.student_id = s.id "
            f"JOIN course_offerings o ON o.id = e.offering_id WHERE o.course_id = ANY({courses})) "
            f"OR {{ref}}.id IN (SELECT staff_person_id FROM staff_course_assignments "
            f"WHERE course_id = ANY({courses})))"
        ),
    }


def _student_filters() -> dict[str, str]:
    return {
        "students": "{ref}.id = $1",
        "people": "{ref}.id = (SELECT person_id FROM students WHERE id = $1)",
        "transcript_entries": "{ref}.student_id = $1",
        "enrollments": "{ref}.student_id = $1",
        "exam_attempts": "{ref}.student_id = $1",
        "courses": (
            "{ref}.id IN (SELECT o.course_id FROM enrollments e "
            "JOIN course_offerings o ON o.id = e.offering_id WHERE e.student_id = $1)"
        ),
        "course_offerings": (
            "{ref}.id IN (SELECT offering_id FROM enrollments WHERE student_id = $1)"
        ),
    }


def scope_plan(ctx: UserContext) -> ScopePlan:
    role = ctx.role
    if role == "senior_management" and ctx.scope_level == "sector":
        if not ctx.sector_id:
            raise QueryRejected(403, "Your account has no sector scope")
        return ScopePlan(
            tables=UNIVERSITY_TABLES,
            filters=_sector_filters(),
            bind=ctx.sector_id,
            must_filter=True,
            unscoped_ok=CALENDAR,
        )
    if role == "senior_management":
        return ScopePlan(
            tables=UNIVERSITY_TABLES,
            filters={},
            bind=None,
            must_filter=False,
            unscoped_ok=CALENDAR,
        )
    if role in ("program_director", "academic_affairs"):
        if not ctx.college_id:
            raise QueryRejected(403, "Your account has no college scope")
        return ScopePlan(
            tables=FACULTY_TABLES,
            filters=_college_filters(),
            bind=ctx.college_id,
            must_filter=True,
            unscoped_ok=CALENDAR,
        )
    if role == "professor":
        # Bound professors to their college (program). Assigned-course lists alone
        # would still answer a university-wide headcount from only those courses.
        if ctx.college_id:
            return ScopePlan(
                tables=PROFESSOR_TABLES,
                filters=_college_filters(),
                bind=ctx.college_id,
                must_filter=True,
                unscoped_ok=frozenset(),
            )
        if not ctx.course_ids:
            raise QueryRejected(403, "You have no assigned courses")
        return ScopePlan(
            tables=PROFESSOR_TABLES,
            filters=_professor_filters(),
            bind=list(ctx.course_ids),
            must_filter=True,
            unscoped_ok=frozenset(),
        )
    if role == "it_academic_integrity":
        return ScopePlan(
            tables=INTEGRITY_TABLES,
            filters={},
            bind=None,
            must_filter=False,
            unscoped_ok=frozenset(),
        )
    if role == "student":
        if not ctx.student_id:
            raise QueryRejected(403, "Your account is not linked to a student record")
        return ScopePlan(
            tables=STUDENT_TABLES,
            filters=_student_filters(),
            bind=ctx.student_id,
            must_filter=True,
            unscoped_ok=frozenset(),
        )
    raise QueryRejected(403, "Your role cannot use the assistant")


def allowed_tables(ctx: UserContext) -> frozenset[str]:
    return scope_plan(ctx).tables
