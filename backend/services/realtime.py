import asyncpg
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from core.locale import Language
import repositories.realtime as repo


async def get_real_time_struggling(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language = "en",
):
    return await repo.get_real_time_struggling(ctx, db, filters, language=language)
