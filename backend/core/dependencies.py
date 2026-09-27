from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import asyncpg

from core.security import decode_access_token
from db.pool import get_db_conn
from repositories.accounts import (
    load_auth_scope,
    user_context_from_scope,
    validate_analytics_filters,
)
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    token: HTTPAuthorizationCredentials = Security(security),
) -> UserContext:
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(token.credentials)
    if not payload or not payload.get("user_id"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_ctx = UserContext(
        user_id=payload["user_id"],
        role="",
        scope_id=None,
        person_id="",
        student_id=None,
    )
    request.state.user = user_ctx
    return user_ctx


async def get_live_user(
    request: Request,
    token_user: UserContext = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_conn),
) -> UserContext:
    """Role and scope come from the live user_accounts row, not the JWT body."""
    scope = await load_auth_scope(db, token_user.user_id)
    live = user_context_from_scope(scope)
    request.state.user = live
    return live


def require_role(*allowed_roles: str):
    async def role_checker(current_user: UserContext = Depends(get_live_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user

    return role_checker


async def get_validated_filters(
    sectorId: str | None = None,
    collegeId: str | None = None,
    curriculumId: str | None = None,
    studentId: str | None = None,
    professorId: str | None = None,
    ctx: UserContext = Depends(get_live_user),
    db: asyncpg.Connection = Depends(get_db_conn),
) -> AnalyticsFilters:
    filters = AnalyticsFilters.from_query(
        sectorId, collegeId, curriculumId, studentId, professorId
    )
    return await validate_analytics_filters(ctx, db, filters)


async def get_partial_filters(
    sectorId: str | None = None,
    collegeId: str | None = None,
    curriculumId: str | None = None,
    studentId: str | None = None,
    professorId: str | None = None,
    ctx: UserContext = Depends(get_live_user),
    db: asyncpg.Connection = Depends(get_db_conn),
) -> AnalyticsFilters:
    """Filter-options may be requested before required analytics filters are set."""
    filters = AnalyticsFilters.from_query(
        sectorId, collegeId, curriculumId, studentId, professorId
    )
    return await validate_analytics_filters(ctx, db, filters, require_complete=False)
