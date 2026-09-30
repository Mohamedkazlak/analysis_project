"""In-process AI decision cache.

Limitation: this cache is per-process and is not shared across multiple API
workers or hosts. It is appropriate for a single-instance prototype.

This cache is not a security boundary. Keys include user_id, role, scope,
filters, academic year, term, and data version so one user's scoped result
cannot be served to another user.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from core.config import settings
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters

_CACHE: dict[str, tuple[float, Any]] = {}
_MAX_ENTRIES = 256


def make_cache_key(
    ctx: UserContext,
    filters: AnalyticsFilters,
    academic_year_id: str = "",
    term_id: str = "",
    data_version: str = "v1",
    language: str = "en",
) -> str:
    return "|".join(
        [
            ctx.user_id,
            ctx.role,
            ctx.scope_id or "",
            ctx.person_id or "",
            ctx.student_id or "",
            filters.sector_id or "",
            filters.college_id or "",
            filters.curriculum_id or "",
            filters.student_id or "",
            filters.professor_id or "",
            str(academic_year_id or ""),
            str(term_id or ""),
            data_version,
            language or "en",
        ]
    )


def get(key: str) -> Optional[Any]:
    row = _CACHE.get(key)
    if not row:
        return None
    expires_at, value = row
    if expires_at < time.monotonic():
        _CACHE.pop(key, None)
        return None
    return value


def _evict() -> None:
    now = time.monotonic()
    expired = [k for k, (expires_at, _) in _CACHE.items() if expires_at < now]
    for key in expired:
        _CACHE.pop(key, None)
    if len(_CACHE) < _MAX_ENTRIES:
        return
    overflow = len(_CACHE) - _MAX_ENTRIES + 1
    oldest = sorted(_CACHE.items(), key=lambda item: item[1][0])[:overflow]
    for key, _ in oldest:
        _CACHE.pop(key, None)


def set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    ttl_seconds = settings.AI_CACHE_TTL_SECONDS if ttl is None else ttl
    if len(_CACHE) >= _MAX_ENTRIES:
        _evict()
    _CACHE[key] = (time.monotonic() + ttl_seconds, value)


def clear() -> None:
    _CACHE.clear()
