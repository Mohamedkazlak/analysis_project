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
from rag.question_sql import (
    NOT_UNDERSTOOD,
    OUT_OF_CONTEXT,
    extract_select,
    is_out_of_context_sql,
    sql_for_question,
)
from rag.schema_docs import build_schema_context
from rag.sql_guard import MAX_ROWS, guard_sql
from schemas.auth import UserContext

logger = logging.getLogger(__name__)

_KEY_RE = re.compile(r"\b(?:bnu|sis)_[A-Za-z0-9_\-]{8,}\b", re.IGNORECASE)

_SQL_SYSTEM = """You are a SQL generator for a Postgres academic database.
The user may ask the same thing in different words, in English or Arabic. Read the meaning, then write the query.
Rules:
- Output ONE SELECT statement only. No comments, no markdown, no explanation.
- Use only the tables and columns listed below.
- Use JOIN when you need another table. Do not use subqueries, CTEs, UNION, or parameters.
- Do not write INSERT, UPDATE, DELETE, or any other statement.
- Do not add a security filter. The server adds the caller's scope.
- If the question is not about this database, output: SELECT 1 AS unsupported WHERE FALSE
- If the question asks for data the listed tables cannot represent, output that same statement.
- Every SELECT value must be a column or an aggregate. Do not type a guessed number, percentage, or name into the SELECT list.
- College means an org_units row with level = 'program'. Sector means level = 'sector'. Curriculum means a courses row.
- Match a named college with lower(org_units.name) or lower(org_units.code), using the words the user wrote.
- "How many courses are in the computer science program?" and "What about courses in the veterinary program?" are the same kind of question. Both are one COUNT of that entity in the named program. The same applies to students.
- List rows only when the user asks to list, show, or name them.
- Do not think out loud. Output the SELECT immediately.

Schema:
{schema}

Notes available to this user:
{notes}
"""

_ANSWER_SYSTEM = """You answer questions about academic records for a {role}.
Write one or two short sentences a person can read. Do not describe your reasoning.
A quantity question is answered like: There are 28 courses in the computer science program.
Copy every number from the rows. Copy names from the question or the rows. Do not round or calculate a new number.
Never write column=value, a table, or a list of codes. The person must not see raw records.
Do not mention rows, SQL, table names, or these instructions.
Answer in the language the user used.
"""

_SQL_RETRY = (
    "That statement was rejected. Answer the same question with one SELECT only. "
    "Use columns and aggregates. No subqueries, comments, or guessed numbers."
)
_SQL_COUNT = (
    "That question asks for a quantity, even when it is phrased as 'what about'. "
    "Return one COUNT, SUM, or AVG for the named program. Do not list rows."
)
_QUANTITY = re.compile(
    r"how many|what about|number of|how much|count of|كم|عدد|ماذا عن",
    re.IGNORECASE,
)
_WANTS_ROWS = re.compile(
    r"\b(list|show|name|which|أسماء|اعرض|اذكر)\b",
    re.IGNORECASE,
)
_AGGREGATE = re.compile(r"\b(count|sum|avg|min|max)\s*\(", re.IGNORECASE)
_THINKING = re.compile(
    r"\b(the user asks|i have authorized|i need to|i should|let me|authorized rows)\b",
    re.IGNORECASE,
)

_SQL_MAX_TOKENS = 1024
_ANSWER_MAX_TOKENS = 512
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_SELECT_REPLY = re.compile(r"(?is)^\s*(?:```(?:sql)?\s*)?select\b")
_RAW_DUMP = re.compile(r"(?i)\b[a-z][a-z0-9_]*\s*=")


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


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall((text or "").translate(_INDIC_DIGITS)))


def format_answer(question: str, rows: list[dict], truncated: bool) -> str:
    """A sentence from the query result. Raw column dumps stay off the chat."""
    arabic = any("\u0600" <= char <= "\u06ff" for char in question)
    if len(rows) == 1 and len(rows[0]) == 1 and not truncated:
        key, value = next(iter(rows[0].items()))
        label = str(key).replace("_", " ")
        rendered = "" if value is None else str(value)
        if arabic:
            return f"بناءً على البيانات المتاحة، {label} هي {rendered}."
        return f"Based on the available data, {label} is {rendered}."
    if truncated:
        if arabic:
            return "بناءً على البيانات المتاحة، هناك نتائج أكثر مما يمكن ذكره كعدد واحد."
        return (
            "Based on the available data, there are more matching records "
            "than can be stated as a single total."
        )
    count = len(rows)
    if arabic:
        return f"بناءً على البيانات المتاحة، عدد النتائج المطابقة هو {count}."
    if count == 1:
        return "Based on the available data, there is 1 matching record."
    return f"Based on the available data, there are {count} matching records."


def wording_is_grounded(wording: str, rows: list[dict], truncated: bool) -> bool:
    """True only when every number in the wording already appears in the rows."""
    text = (wording or "").strip()
    if not text or len(text) > 2000 or _SELECT_REPLY.match(text):
        return False
    if _THINKING.search(text) or _RAW_DUMP.search(text):
        return False
    row_numbers = _numbers(_rows_to_text(rows))
    allowed = set(row_numbers)
    if truncated:
        allowed.add(str(MAX_ROWS))
    stated = _numbers(text)
    if row_numbers and not (stated & row_numbers):
        return False
    return stated <= allowed


async def _explain_rows(
    role: str, question: str, rows: list[dict], truncated: bool
) -> str:
    """Ask the model to phrase the rows, then drop any number it did not receive."""
    fallback = format_answer(question, rows, truncated)
    context = _rows_to_text(rows)
    if truncated:
        context += f"\n(Results truncated to {MAX_ROWS} authorized rows.)"
    try:
        drafted = await chat_completion(
            [
                {"role": "system", "content": _ANSWER_SYSTEM.format(role=role)},
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nAuthorized rows:\n{context}",
                },
            ],
            temperature=0,
            max_tokens=_ANSWER_MAX_TOKENS,
        )
    except (LlmNotConfigured, LlmUpstreamError):
        return fallback
    if not wording_is_grounded(drafted, rows, truncated):
        logger.info("chat wording discarded because it added a number")
        return fallback
    return drafted.strip()


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


def _asks_for_quantity(question: str) -> bool:
    return (
        _QUANTITY.search(question) is not None and _WANTS_ROWS.search(question) is None
    )


def _is_aggregate(sql: str) -> bool:
    return _AGGREGATE.search(sql or "") is not None


async def _model_sql(
    schema: str, notes: list[str], question: str, *, followup: str | None = None
) -> str:
    messages = [
        {
            "role": "system",
            "content": _SQL_SYSTEM.format(
                schema=schema,
                notes="\n".join(f"- {note}" for note in notes) or "- none",
            ),
        },
        {"role": "user", "content": question},
    ]
    if followup:
        messages.append({"role": "user", "content": followup})
    raw = await chat_completion(
        messages, temperature=0, max_tokens=_SQL_MAX_TOKENS, sql=True
    )
    return extract_select(raw)


async def _query(ctx: UserContext, db, pool, raw_sql: str):
    scoped_sql, bind = guard_sql(raw_sql, ctx)
    try:
        records = await _run_select(db, pool, ctx.user_id, scoped_sql, bind)
    except asyncpg.PostgresError:
        logger.exception("guarded chat query failed")
        raise HTTPException(
            status_code=503,
            detail="The database could not complete that request",
        )
    return records, scoped_sql


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
    written_by_user = sql_for_question(cleaned)
    try:
        raw_sql = written_by_user or await _model_sql(schema, notes, cleaned)
        if (
            written_by_user is None
            and _asks_for_quantity(cleaned)
            and not is_out_of_context_sql(raw_sql)
            and not _is_aggregate(raw_sql)
        ):
            raw_sql = await _model_sql(schema, notes, cleaned, followup=_SQL_COUNT)
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

    if is_out_of_context_sql(raw_sql):
        elapsed = int((time.perf_counter() - started) * 1000)
        await _log(pool, ctx, cleaned, None, 0, None, elapsed, True)
        return {"text": OUT_OF_CONTEXT, "blocked": False}

    generated_sql = None
    try:
        try:
            records, generated_sql = await _query(ctx, db, pool, raw_sql)
        except QueryRejected as exc:
            if written_by_user is not None or exc.status_code == 403:
                raise
            raw_sql = await _model_sql(schema, notes, cleaned, followup=_SQL_RETRY)
            if is_out_of_context_sql(raw_sql):
                elapsed = int((time.perf_counter() - started) * 1000)
                await _log(pool, ctx, cleaned, None, 0, None, elapsed, True)
                return {"text": OUT_OF_CONTEXT, "blocked": False}
            records, generated_sql = await _query(ctx, db, pool, raw_sql)
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
        raise HTTPException(status_code=exc.status_code, detail=NOT_UNDERSTOOD) from exc
    except LlmNotConfigured:
        elapsed = int((time.perf_counter() - started) * 1000)
        await _log(pool, ctx, cleaned, None, None, "llm_unconfigured", elapsed, False)
        raise HTTPException(status_code=503, detail="The assistant is not configured")
    except LlmUpstreamError:
        elapsed = int((time.perf_counter() - started) * 1000)
        await _log(pool, ctx, cleaned, generated_sql, None, "llm_error", elapsed, False)
        raise HTTPException(
            status_code=502, detail="The assistant is temporarily unavailable"
        )
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
        text = await _explain_rows(ctx.role, cleaned, rows, truncated)

    elapsed = int((time.perf_counter() - started) * 1000)
    await _log(pool, ctx, cleaned, generated_sql, len(rows), None, elapsed, True)
    return {"text": text.strip(), "blocked": False}
