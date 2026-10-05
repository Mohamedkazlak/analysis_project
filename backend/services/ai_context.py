"""Shared analytics snapshot for one AI decision request.

Loads datasets required for the authenticated role *and* the current page
so each dashboard surface can show page-local AI analysis.
"""

from __future__ import annotations

from typing import Any, Optional

import asyncpg

from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from services.ai_pages import normalize_page
import repositories.management as mgmt_repo
import repositories.course_performance as course_repo
import repositories.participation as part_repo
import repositories.integrity as integrity_repo
import repositories.item_analysis as item_repo
import repositories.performance as perf_repo
import repositories.student as student_repo
import repositories.ai_insights as ai_repo


def _page_needs(page: str) -> set[str]:
    """Datasets required for a non-overview page.

    Overview is special-cased in ``datasets_for`` to load the full role union.
    """
    page = normalize_page(page)
    mapping = {
        "courses": {"overview", "courses"},
        "exam-activity": {"overview", "courses"},
        "performance": {"overview", "performance"},
        "participation": {"overview", "participation"},
        "item-analysis": {"overview", "items"},
        "integrity": {"integrity", "flagged"},
        "real-time": {"integrity", "overview", "flagged"},
        "students": {"overview", "performance"},
        "student": {"performance"},
        "my-progress": {"dashboard"},
    }
    return set(mapping.get(page, {"overview"}))


def _role_allows(role: str) -> set[str]:
    if role == "student":
        return {"dashboard"}
    if role == "senior_management":
        return {
            "overview",
            "integrity",
            "flagged",
            "courses",
            "participation",
            "items",
            "performance",
        }
    if role == "program_director":
        return {"overview", "items", "courses", "participation", "performance"}
    if role == "academic_affairs":
        return {"participation", "performance", "overview", "courses", "items"}
    if role == "professor":
        return {"courses", "participation", "items", "performance", "overview"}
    if role == "it_academic_integrity":
        return {"integrity", "flagged", "overview", "items"}
    return set()


def datasets_for(role: str, page: Optional[str] = None) -> set[str]:
    """Intersect page needs with role allow-list.

    Overview loads every dataset the role is allowed to see so one card can
    summarize the full picture.
    """
    page_id = normalize_page(page)
    allowed = _role_allows(role)
    if page_id == "overview":
        return set(allowed)
    needed = _page_needs(page_id) & allowed
    return needed or set(allowed)


async def load_ai_context(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    page: Optional[str] = None,
) -> dict[str, Any]:
    role = ctx.role
    page_id = normalize_page(page)
    data: dict[str, Any] = {"role": role, "filters": filters, "page": page_id}

    needed = datasets_for(role, page_id)

    if "dashboard" in needed and role == "student":
        data["dashboard"] = await student_repo.get_student_dashboard(ctx, db, filters)

    if "overview" in needed:
        data["overview"] = await mgmt_repo.get_management_overview(ctx, db, filters)

    if "courses" in needed:
        data["courses"] = await course_repo.get_course_performance(ctx, db, filters)

    if "participation" in needed:
        data["participation"] = await part_repo.get_participation_report(
            ctx, db, filters
        )

    if "performance" in needed:
        data["performance"] = await perf_repo.get_student_performance(ctx, db, filters)

    if "items" in needed:
        data["items"] = await item_repo.get_item_analysis(ctx, db, filters)

    if "integrity" in needed:
        data["integrity"] = await integrity_repo.get_integrity_counts(ctx, db, filters)

    if "flagged" in needed:
        data["flagged"] = await ai_repo.top_flagged_attempts(
            db, limit=3, filters=filters
        )

    # Fact packets expect an overview-shaped block. Synthesize one from
    # course / performance payloads when management overview was not loaded.
    if "overview" not in data:
        data["overview"] = _synthesize_overview(data)

    return data


def _synthesize_overview(data: dict[str, Any]) -> dict[str, Any]:
    courses_payload = data.get("courses") or {}
    by_course = (
        courses_payload.get("passRateByCourse")
        or courses_payload.get("courses")
        or courses_payload.get("rows")
        or []
    )
    if not by_course:
        # Course performance repo exposes sections with passRate.
        by_course = [
            {
                "course": row.get("course") or row.get("section"),
                "passRate": row.get("passRate"),
                "participants": row.get("enrolled") or row.get("participants") or 0,
                "students": row.get("enrolled") or row.get("students") or 0,
            }
            for row in courses_payload.get("sections") or []
            if row.get("passRate") is not None
        ]
    performance = data.get("performance") or {}
    participation = data.get("participation") or {}
    totals = dict(
        courses_payload.get("totals")
        or performance.get("totals")
        or participation.get("totals")
        or {}
    )
    if (
        totals.get("attendance") is None
        and participation.get("attendanceRate") is not None
    ):
        totals["attendance"] = participation.get("attendanceRate")
    if totals.get("passRate") is None and by_course:
        rates = [
            float(r["passRate"]) for r in by_course if r.get("passRate") is not None
        ]
        if rates:
            totals["passRate"] = round(sum(rates) / len(rates), 1)
    return {
        "totals": totals,
        "passRateByCourse": by_course,
        "passRateByCollege": (
            courses_payload.get("passRateByCollege")
            or performance.get("passRateByCollege")
            or []
        ),
    }
