"""Issue one active API key per user account.

The raw key is written to backend/.api-keys.local and is not printed.
Role and scope are copied onto the key row only when those legacy columns
exist; login ignores them and reads user_accounts.
"""

import asyncio
import hashlib
import secrets
import sys
from pathlib import Path

import asyncpg

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from core.config import settings  # noqa: E402

OUT = BACKEND / ".api-keys.local"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def issue() -> int:
    url = settings.DATABASE_ADMIN_URL or settings.DATABASE_URL
    if not url:
        raise SystemExit("DATABASE_ADMIN_URL or DATABASE_URL is required")
    conn = await asyncpg.connect(url)
    created = 0
    try:
        columns = {
            row["column_name"]
            for row in await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'api_keys'
                """
            )
        }
        if "user_id" not in columns or "key_hash" not in columns:
            raise SystemExit(
                "api_keys is missing user_id or key_hash; apply migrations first"
            )
        users = await conn.fetch(
            """
            SELECT id, role::text AS role, scope_id, person_id, student_id
            FROM user_accounts
            WHERE is_active
            ORDER BY id
            """
        )
        lines = [
            "# Local API keys. Do not commit this file.",
            "# Each line is user_id=<id> key=<secret>",
        ]
        for user in users:
            existing = await conn.fetchval(
                """
                SELECT 1
                FROM api_keys
                WHERE user_id = $1
                  AND is_active
                  AND revoked_at IS NULL
                  AND label = 'platform-login'
                """,
                user["id"],
            )
            if existing:
                lines.append(f"user_id={user['id']} key=<already-issued>")
                continue
            raw = f"bnu_{secrets.token_urlsafe(32)}"
            values = {
                "user_id": user["id"],
                "key_prefix": raw[:12],
                "key_hash": _hash(raw),
                "label": "platform-login",
                "is_active": True,
            }
            if "role" in columns:
                values["role"] = user["role"]
            if "scope_id" in columns:
                values["scope_id"] = user["scope_id"]
            if "person_id" in columns:
                values["person_id"] = user["person_id"]
            if "student_id" in columns:
                values["student_id"] = user["student_id"]
            cols = list(values)
            placeholders = ", ".join(
                f"${i}::app_role" if col == "role" else f"${i}"
                for i, col in enumerate(cols, start=1)
            )
            await conn.execute(
                f"INSERT INTO api_keys ({', '.join(cols)}) VALUES ({placeholders})",
                *[values[col] for col in cols],
            )
            lines.append(f"user_id={user['id']} key={raw}")
            created += 1
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        OUT.chmod(0o600)
    finally:
        await conn.close()
    print(f"wrote {OUT.name}; new keys: {created}")
    return created


if __name__ == "__main__":
    asyncio.run(issue())
