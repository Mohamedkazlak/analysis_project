from typing import Optional

from fastapi import APIRouter, Depends, Query
from schemas.realtime import RealTimeReport
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from core.dependencies import require_role, get_validated_filters
from core.locale import normalize_language
from db.pool import get_db_conn
import asyncpg
from services.realtime import get_real_time_struggling

router = APIRouter(prefix="/api/real-time-struggling", tags=["realtime"])


@router.get("", response_model=RealTimeReport)
async def route_get_real_time_struggling(
    ctx: UserContext = Depends(
        require_role("senior_management", "professor", "it_academic_integrity")
    ),
    db: asyncpg.Connection = Depends(get_db_conn),
    filters: AnalyticsFilters = Depends(get_validated_filters),
    language: Optional[str] = Query("en"),
):
    return await get_real_time_struggling(
        ctx, db, filters, language=normalize_language(language)
    )
