from typing import Optional

from fastapi import APIRouter, Depends, Query
from schemas.integrity import IntegrityReport
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from core.dependencies import require_role, get_validated_filters
from core.locale import normalize_language
from db.pool import get_db_conn
import asyncpg
from services.integrity import get_integrity_report

router = APIRouter(prefix="/api/integrity-report", tags=["integrity"])


@router.get("", response_model=IntegrityReport)
async def route_get_integrity_report(
    ctx: UserContext = Depends(
        require_role("it_academic_integrity", "senior_management")
    ),
    db: asyncpg.Connection = Depends(get_db_conn),
    filters: AnalyticsFilters = Depends(get_validated_filters),
    language: Optional[str] = Query("en"),
):
    return await get_integrity_report(
        ctx, db, filters, language=normalize_language(language)
    )
