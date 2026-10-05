"""Keyword retrieval over policy_documents (no embeddings in this PoC).

RAG supplies document context. It never invents numerical analytics.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import asyncpg

from schemas.auth import UserContext

_POLICY_HINT = re.compile(
    r"\b("
    r"policy|policies|regulation|retake|appeal|probation|cheating|integrity|"
    r"grading\s+scale|absence|remediation|failed\s+final|assessment\s+policy|"
    r"سياسة|لوائح|إعادة|استئناف|إنذار|غش|غياب|مقياس\s+الدرجات"
    r")\b",
    re.I,
)

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "for",
        "in",
        "on",
        "is",
        "are",
        "what",
        "does",
        "how",
        "about",
        "with",
        "from",
        "that",
        "this",
        "university",
        "policy",
        "هل",
        "ما",
        "عن",
        "في",
        "من",
        "على",
        "الجامعة",
        "سياسة",
    }
)


def looks_like_policy_question(question: str) -> bool:
    return bool(_POLICY_HINT.search(question or ""))


def _tokens(question: str) -> list[str]:
    raw = re.findall(r"[A-Za-z\u0600-\u06FF0-9]{3,}", question.lower())
    return [t for t in raw if t not in _STOP][:12]


async def retrieve_policies(
    db: asyncpg.Connection,
    ctx: UserContext,
    question: str,
    *,
    language: Optional[str] = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return ranked policy snippets the caller is allowed to read.

    RLS on policy_documents already requires an authenticated app role.
    """
    if not looks_like_policy_question(question):
        return []

    tokens = _tokens(question)
    lang = (language or "en")[:2]
    rows = await db.fetch(
        """
        SELECT id, title, language, body, effective_date::text AS effective_date
        FROM policy_documents
        WHERE ($1::text IS NULL OR language = $1)
        ORDER BY effective_date DESC
        LIMIT 40
        """,
        lang if lang in ("en", "ar") else None,
    )
    if not rows and lang:
        rows = await db.fetch(
            """
            SELECT id, title, language, body, effective_date::text AS effective_date
            FROM policy_documents
            ORDER BY effective_date DESC
            LIMIT 40
            """
        )

    scored: list[tuple[int, dict]] = []
    for row in rows:
        title = row["title"] or ""
        body = row["body"] or ""
        blob = f"{title}\n{body}".lower()
        score = 0
        for tok in tokens:
            if tok in blob:
                score += 2 if tok in title.lower() else 1
        if score <= 0 and looks_like_policy_question(question):
            # Soft match: still surface one generic related doc by title keywords.
            if any(
                k in blob for k in ("retake", "appeal", "grading", "cheat", "absence")
            ):
                score = 1
        if score <= 0:
            continue
        # Snippet around first token hit.
        snippet = body.strip()
        if len(snippet) > 480:
            snippet = snippet[:477] + "…"
        scored.append(
            (
                score,
                {
                    "id": row["id"],
                    "title": title,
                    "language": row["language"],
                    "effectiveDate": row["effective_date"],
                    "snippet": snippet,
                    "provenance": "rag_document",
                    "score": score,
                },
            )
        )

    scored.sort(key=lambda x: (-x[0], x[1]["title"]))
    return [item for _, item in scored[:limit]]


def format_policy_context(docs: list[dict[str, Any]]) -> str:
    if not docs:
        return ""
    parts = ["Retrieved policy evidence (do not invent beyond these excerpts):"]
    for doc in docs:
        parts.append(
            f"- [{doc['id']}] {doc['title']} ({doc.get('effectiveDate')}): {doc['snippet']}"
        )
    return "\n".join(parts)
