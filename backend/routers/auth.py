from fastapi import APIRouter, Depends, HTTPException
from schemas.auth import (
    LoginRequest,
    SessionProfile,
    TokenResponse,
    UserContext,
    AssignedCourse,
)
from db.pool import get_db_conn
from core.config import settings
from core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from core.dependencies import get_live_user
from repositories.accounts import load_auth_scope, user_context_from_scope
import asyncpg

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID = "Invalid credentials"
# Used when the account or key does not match, so a missing hash still pays
# the bcrypt cost.
_DUMMY_PASSWORD_HASH = get_password_hash("invalid-login")


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: asyncpg.Connection = Depends(get_db_conn)):
    user_id = (req.id or "").strip()
    password = req.password or ""
    if not user_id or not password or len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=401, detail=_INVALID)
    password_hash = await db.fetchval(
        "SELECT account_password_for_login($1)",
        user_id,
    )
    if not verify_password(password, password_hash or _DUMMY_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail=_INVALID)
    if not password_hash:
        raise HTTPException(status_code=401, detail=_INVALID)
    confirmed = await db.fetchval(
        "SELECT user_id FROM record_password_login($1)",
        user_id,
    )
    if confirmed != user_id:
        raise HTTPException(status_code=401, detail=_INVALID)
    await db.execute("SELECT set_config('app.current_user_id', $1, true)", user_id)
    scope = await load_auth_scope(db, user_id)
    profile = user_context_from_scope(scope)
    access_token = create_access_token({"user_id": user_id})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
        user=SessionProfile(
            user_id=profile.user_id,
            role=profile.role,
            display_role=profile.display_role,
            name=profile.name,
            scope_level=profile.scope_level,
            scope_label=profile.scope_label,
            sector_id=profile.sector_id,
            college_id=profile.college_id,
            student_id=profile.student_id,
        ),
    )


@router.get("/me", response_model=UserContext)
async def get_me(
    current_user: UserContext = Depends(get_live_user),
    db: asyncpg.Connection = Depends(get_db_conn),
):
    name = current_user.name or current_user.user_id
    parts = [p for p in name.split() if p]
    initials = (
        f"{parts[0][0]}{parts[-1][0]}".upper() if len(parts) >= 2 else name[:2].upper()
    )
    courses = []
    if current_user.role == "professor" and current_user.person_id:
        rows = await db.fetch(
            """
            SELECT
                c.id, c.code, c.name,
                (
                    SELECT COUNT(*)::int
                    FROM enrollments e
                    JOIN course_offerings o ON o.id = e.offering_id
                    WHERE o.course_id = c.id
                ) AS enrolled,
                ARRAY(
                    SELECT DISTINCT cs.code
                    FROM course_sections cs
                    JOIN course_offerings o ON o.id = cs.offering_id
                    WHERE o.course_id = c.id
                    ORDER BY cs.code
                ) AS sections
            FROM courses c
            JOIN staff_course_assignments sca
              ON sca.course_id = c.id AND sca.staff_person_id = $1
            ORDER BY c.code
            """,
            current_user.person_id,
        )
        courses = [
            AssignedCourse(
                id=r["id"],
                code=r["code"],
                name=r["name"],
                enrolled=r["enrolled"],
                sections=list(r["sections"] or []),
            )
            for r in rows
        ]
    current_user.initials = initials
    current_user.courses = courses
    current_user.course_ids = [c.id for c in courses] or current_user.course_ids
    return current_user
