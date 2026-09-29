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
        "id": "sector-dean-scope",
        "roles": frozenset({"senior_management"}),
        "scope_levels": frozenset({"sector"}),
        "text": (
            "The caller is a sector dean. Authorized rows are only that sector. "
            "If the question is about the university, the institution, all colleges, "
            "or every program, answer for this sector alone. Never include another sector. "
            "If the question names a different sector, do not invent an answer — "
            "that request is refused before SQL runs."
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
        "id": "professor-college-scope",
        "roles": frozenset({"professor"}),
        "scope_levels": None,
        "text": (
            "The caller is a college professor. Authorized rows are only that college "
            "(program-level org unit). If the question is about the university, another "
            "college, or all programs, answer for this college only."
        ),
    },
    {
        "id": "college-staff-scope",
        "roles": frozenset({"program_director", "academic_affairs"}),
        "scope_levels": None,
        "text": (
            "The caller works in one college (program-level org unit). "
            "If the question is about the university or another college, answer only "
            "for that college. Do not include other colleges."
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
    bound = _bound_org_note(ctx)
    if bound:
        notes.insert(0, bound)
    return notes


def _bound_org_note(ctx: UserContext) -> str | None:
    """Name the caller's org unit so university-wide wording stays in scope."""
    if ctx.role == "senior_management" and ctx.scope_level == "sector":
        name = (ctx.sector_name or "").strip() or "the caller's sector"
        return (
            f"Caller sector: {name}. "
            f"University-wide questions must be answered for {name} only."
        )
    if ctx.role == "professor":
        college = (ctx.college_name or "").strip() or "the caller's college"
        return (
            f"Caller college: {college}. "
            f"University-wide or other-college questions must be answered for "
            f"{college} only."
        )
    if ctx.role in ("program_director", "academic_affairs"):
        college = (ctx.college_name or "").strip() or "the caller's college"
        return (
            f"Caller college: {college}. "
            f"University-wide or other-college questions must be answered for "
            f"{college} only."
        )
    return None
