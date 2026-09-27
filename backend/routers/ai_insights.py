from typing import Optional

from fastapi import APIRouter, Depends
import asyncpg

from schemas.auth import UserContext
from schemas.ai_insights import Insight, Prediction, RecommendationSet, AiDecision
from schemas.filters import AnalyticsFilters, AiDecisionRequest
from core.dependencies import get_live_user, get_validated_filters
from db.pool import get_db_conn
from repositories.accounts import validate_analytics_filters
import services.ai_insights as ai_service

router = APIRouter(tags=["ai_insights"])


@router.post("/api/ai/decision", response_model=AiDecision)
async def post_ai_decision(
    body: AiDecisionRequest,
    ctx: UserContext = Depends(get_live_user),
    db: asyncpg.Connection = Depends(get_db_conn),
):
    filters = await validate_analytics_filters(ctx, db, body.to_filters())
    return await ai_service.get_ai_decision(ctx, db, filters)


@router.get("/api/insights", response_model=Optional[Insight])
async def get_insights(
    ctx: UserContext = Depends(get_live_user),
    db: asyncpg.Connection = Depends(get_db_conn),
    filters: AnalyticsFilters = Depends(get_validated_filters),
):
    return await ai_service.get_insight(ctx, db, filters)


@router.get("/api/predictions", response_model=Optional[Prediction])
async def get_predictions(
    ctx: UserContext = Depends(get_live_user),
    db: asyncpg.Connection = Depends(get_db_conn),
    filters: AnalyticsFilters = Depends(get_validated_filters),
):
    return await ai_service.get_prediction(ctx, db, filters)


@router.get("/api/recommendations", response_model=Optional[RecommendationSet])
async def get_recommendations(
    insightId: str = "insight",
    ctx: UserContext = Depends(get_live_user),
    db: asyncpg.Connection = Depends(get_db_conn),
    filters: AnalyticsFilters = Depends(get_validated_filters),
):
    return await ai_service.get_recommendations(ctx, db, insightId, filters)
