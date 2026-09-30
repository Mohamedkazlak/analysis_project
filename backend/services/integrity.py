import asyncpg
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from core.locale import Language
import repositories.integrity as repo


async def get_integrity_report(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language = "en",
):
    return await repo.get_integrity_report(ctx, db, filters, language=language)
