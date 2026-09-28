import asyncpg

from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
import repositories.management as repo


async def get_management_overview(
    ctx: UserContext, db: asyncpg.Connection, filters: AnalyticsFilters | None = None
):
    """SQL overview only. Wording stays on the AI decision request."""
    return await repo.get_management_overview(ctx, db, filters)
