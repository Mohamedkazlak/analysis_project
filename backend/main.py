from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from db.pool import create_pool
from routers import (
    auth,
    management,
    performance,
    item_analysis,
    integrity,
    participation,
    course_performance,
    realtime,
    directory,
    student,
    ai_insights,
    filter_options,
    rag,
    speech,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    app.state.pool = await create_pool()
    yield
    await app.state.pool.close()


app = FastAPI(
    title="BNU Analytics API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(management.router)
app.include_router(performance.router)
app.include_router(item_analysis.router)
app.include_router(integrity.router)
app.include_router(participation.router)
app.include_router(course_performance.router)
app.include_router(realtime.router)
app.include_router(directory.router)
app.include_router(student.router)
app.include_router(ai_insights.router)
app.include_router(filter_options.router)
app.include_router(rag.router)
app.include_router(speech.router)
