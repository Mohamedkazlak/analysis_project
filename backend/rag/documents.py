"""Role-scoped notes. Filter these before they are placed in a model prompt."""

from schemas.auth import UserContext

# visibility: roles that may see the note, and optional scope_levels.
# A sector dean is senior_management with scope_level sector, so university-only
# notes stay out of that prompt.
_DOCUMENTS = (
    {
        "id": "org-model",
        "roles": frozenset(
            {
                "senior_management",
                "program_director",
                "academic_affairs",
                "professor",
                "it_academic_integrity",
                "student",
            }
        ),
        "scope_levels": None,
        "text": (
            "Organizational levels in this database are university, sector, and program. "
            "The product label College is a program-level org unit. "
            "There is no separate faculty or department table."
        ),
    },
    {
        "id": "university-leadership",
        "roles": frozenset({"senior_management"}),
        "scope_levels": frozenset({"university"}),
        "text": (
            "University senior management can discuss institution-wide academic performance. "
            "Sector deans cannot. Do not describe another sector's results to a sector dean."
        ),
    },
    {
        "id": "integrity-operations",
        "roles": frozenset({"it_academic_integrity", "senior_management"}),
        "scope_levels": None,
        "text": (
            "Integrity flags are monitoring signals attached to exam attempts. "
            "They are not grades and they are not a finding of misconduct by themselves."
        ),
    },
    {
        "id": "professor-assignments",
        "roles": frozenset({"professor"}),
        "scope_levels": None,
        "text": (
            "A professor's data boundary is staff_course_assignments, then the courses, "
            "offerings, enrollments, and exams that follow from those courses. "
            "A faculty-wide scope does not grant access to unassigned courses."
        ),
    },
    {
        "id": "student-own-record",
        "roles": frozenset({"student"}),
        "scope_levels": None,
        "text": "A student can only be shown their own academic record.",
    },
)


def visible_documents(ctx: UserContext) -> list[str]:
    role = ctx.role
    level = ctx.scope_level
    notes: list[str] = []
    for doc in _DOCUMENTS:
        if role not in doc["roles"]:
            continue
        allowed_levels = doc["scope_levels"]
        if allowed_levels is not None and level not in allowed_levels:
            continue
        notes.append(doc["text"])
    return notes
