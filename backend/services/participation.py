import asyncpg
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from core.locale import Language
import repositories.participation as repo


async def get_participation_report(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language = "en",
):
    return await repo.get_participation_report(ctx, db, filters, language=language)
