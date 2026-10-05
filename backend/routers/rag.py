from fastapi import APIRouter, Depends, Request
import asyncpg

from core.dependencies import get_live_user
from db.pool import get_db_conn
from schemas.ai_insights import ChatRequest, ChatResponse
from schemas.auth import UserContext
import services.chat as chat_service

router = APIRouter(tags=["rag"])


@router.post("/api/chat", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    request: Request,
    ctx: UserContext = Depends(get_live_user),
    db: asyncpg.Connection = Depends(get_db_conn),
):
    return await chat_service.get_chat_answer(
        ctx,
        db,
        body.question,
        request.app.state.pool,
        card_id=body.cardId,
        slice_ids=body.slice,
        item_id=body.itemId,
        language=body.language,
    )
