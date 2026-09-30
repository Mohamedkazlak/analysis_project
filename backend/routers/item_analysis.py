from typing import Optional

from fastapi import APIRouter, Depends, Query
from schemas.item_analysis import ItemAnalysisReport
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from core.dependencies import require_role, get_validated_filters
from core.locale import normalize_language
from db.pool import get_db_conn
import asyncpg
from services.item_analysis import get_item_analysis

router = APIRouter(prefix="/api/item-analysis", tags=["item_analysis"])


@router.get("", response_model=ItemAnalysisReport)
async def route_get_item_analysis(
    ctx: UserContext = Depends(
        require_role(
            "senior_management",
            "program_director",
            "academic_affairs",
            "professor",
            "it_academic_integrity",
        )
    ),
    db: asyncpg.Connection = Depends(get_db_conn),
    filters: AnalyticsFilters = Depends(get_validated_filters),
    language: Optional[str] = Query("en"),
):
    return await get_item_analysis(
        ctx, db, filters, language=normalize_language(language)
    )
