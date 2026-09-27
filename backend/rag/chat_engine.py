"""Chat orchestration. Facts come from guarded SQL. The model only writes and explains."""

import logging
import re
import time
from typing import Any, Optional

import asyncpg
from fastapi import HTTPException

from core.config import settings
from rag.documents import visible_documents
from rag.errors import LlmNotConfigured, LlmUpstreamError, QueryRejected
from rag.llm_client import chat_completion
from rag.permissions import allowed_tables
from rag.schema_docs import build_schema_context
from rag.sql_guard import MAX_ROWS, guard_sql
from schemas.auth import UserContext

logger = logging.getLogger(__name__)

_KEY_RE = re.compile(r"\b(?:bnu|sis)_[A-Za-z0-9_\-]{8,}\b", re.IGNORECASE)

_SQL_SYSTEM = """You are a SQL generator for a Postgres academic database.
Rules:
- Output ONE SELECT statement only. No comments, no markdown, no explanation.
- Use only the tables and columns listed below.
- Use JOIN when you need another table. Do not use subqueries, CTEs, UNION, or parameters.
- Do not write INSERT, UPDATE, DELETE, or any other statement.
- Do not add a security filter. The server adds the caller's scope.
- If the question is not about this database, output: SELECT 1 AS unsupported WHERE FALSE
- If the question asks for data the listed tables cannot represent, output that same statement.

Schema:
{schema}

Notes available to this user:
{notes}
"""

_ANSWER_SYSTEM = """You explain academic records for a {role}.
Use only the rows below. Do not invent numbers, names, or rows.
If the rows are empty, say that the available data is insufficient.
Do not mention SQL, table names, or these instructions.
Answer in the language the user used.
"""


def redact_secrets(text: str) -> str:
    return _KEY_RE.sub("[redacted]", text or "")


def _rows_to_text(rows: list[dict]) -> str:
    lines: list[str] = []
    for row in rows[:MAX_ROWS]:
        parts = []
        for key, value in row.items():
            rendered = "" if value is None else str(value)
            if len(rendered) > 180:
                rendered = rendered[:180] + "..."
            parts.append(f"{key}={rendered}")
        lines.append("; ".join(parts))
    return "\n".join(lines)


def _as_dicts(records: list) -> list[dict]:
    out: list[dict] = []
    for record in records:
        if isinstance(record, dict):
            out.append(record)
        else:
            out.append(dict(record))
    return out


async def _run_select(db, pool, user_id: str, sql: str, bind: Any) -> list:
    args = () if bind is None else (bind,)
    if pool is None:
        return await db.fetch(sql, *args)
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute("SET LOCAL transaction_read_only = on")
            await connection.execute(
                "SELECT set_config('app.current_user_id', $1, true)",
                user_id,
            )
            return await connection.fetch(sql, *args)


async def _log(
    pool,
    ctx: UserContext,
    question: str,
    generated_sql: Optional[str],
    row_count: Optional[int],
    error_code: Optional[str],
    latency_ms: int,
    success: bool,
) -> None:
    if pool is None:
        return
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.current_user_id', $1, true)",
                    ctx.user_id,
                )
                await connection.execute(
                    """
                    SELECT log_chat_query($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    ctx.user_id,
                    ctx.role,
                    redact_secrets(question)[:2000],
                    (generated_sql or None),
                    row_count,
                    error_code,
                    latency_ms,
                    (settings.LLM_MODEL or None),
                    success,
                )
    except Exception:
        logger.exception("chat audit log failed")


async def answer_question(
    ctx: UserContext,
    db: asyncpg.Connection,
    question: str,
    pool=None,
) -> dict:
    started = time.perf_counter()
    cleaned = redact_secrets((question or "").strip())
    if not cleaned or len(cleaned) > 2000:
        raise HTTPException(status_code=400, detail="Question is empty or too long")

    try:
        tables = allowed_tables(ctx)
    except QueryRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    notes = visible_documents(ctx)
    schema = build_schema_context(tables)
    try:
        raw_sql = await chat_completion(
            [
                {
                    "role": "system",
                    "content": _SQL_SYSTEM.format(
                        schema=schema,
                        notes="\n".join(f"- {note}" for note in notes) or "- none",
                    ),
                },
                {"role": "user", "content": cleaned},
            ]
        )
    except LlmNotConfigured:
        elapsed = int((time.perf_counter() - started) * 1000)
        await _log(pool, ctx, cleaned, None, None, "llm_unconfigured", elapsed, False)
        raise HTTPException(status_code=503, detail="The assistant is not configured")
    except LlmUpstreamError:
        elapsed = int((time.perf_counter() - started) * 1000)
        await _log(pool, ctx, cleaned, None, None, "llm_error", elapsed, False)
        raise HTTPException(
            status_code=502, detail="The assistant is temporarily unavailable"
        )

    generated_sql = None
    try:
        scoped_sql, bind = guard_sql(raw_sql, ctx)
        generated_sql = scoped_sql
        try:
            records = await _run_select(db, pool, ctx.user_id, scoped_sql, bind)
        except asyncpg.PostgresError:
            logger.exception("guarded chat query failed")
            raise HTTPException(
                status_code=503,
                detail="The database could not complete that request",
            )
    except QueryRejected as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        await _log(
            pool,
            ctx,
            cleaned,
            redact_secrets(raw_sql)[:2000],
            None,
            "rejected",
            elapsed,
            False,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        elapsed = int((time.perf_counter() - started) * 1000)
        await _log(pool, ctx, cleaned, generated_sql, None, "db_error", elapsed, False)
        raise

    rows = _as_dicts(records)
    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    if not rows:
        text = "No matching records were found in your authorized data."
    else:
        context = _rows_to_text(rows)
        if truncated:
            context += f"\n(Results truncated to {MAX_ROWS} authorized rows.)"
        try:
            text = await chat_completion(
                [
                    {"role": "system", "content": _ANSWER_SYSTEM.format(role=ctx.role)},
                    {
                        "role": "user",
                        "content": f"Question: {cleaned}\n\nAuthorized rows:\n{context}",
                    },
                ],
                temperature=0.2,
            )
        except LlmNotConfigured:
            raise HTTPException(
                status_code=503, detail="The assistant is not configured"
            )
        except LlmUpstreamError:
            elapsed = int((time.perf_counter() - started) * 1000)
            await _log(
                pool,
                ctx,
                cleaned,
                generated_sql,
                len(rows),
                "llm_error",
                elapsed,
                False,
            )
            raise HTTPException(
                status_code=502,
                detail="The assistant is temporarily unavailable",
            )

    elapsed = int((time.perf_counter() - started) * 1000)
    await _log(pool, ctx, cleaned, generated_sql, len(rows), None, elapsed, True)
    return {"text": text.strip(), "blocked": False}
