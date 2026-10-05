"""CLI: python -m seed_demo dry-run|apply|reset-synthetic"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Allow `python -m seed_demo` from backend/ or repo root.
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.config import settings  # noqa: E402
from core.security import get_password_hash  # noqa: E402
from seed_demo.apply import apply_plan, real_checksums, reset_owned  # noqa: E402
from seed_demo.policies import load_policies  # noqa: E402
from seed_demo.plan import build_plan, load_context  # noqa: E402
from seed_demo.verify import verify_stories  # noqa: E402


def _db_kind(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "supabase" in host:
        return "hosted-supabase"
    if host in ("localhost", "127.0.0.1"):
        return "local"
    return "other-remote"


def _admin_url() -> str:
    return (settings.DATABASE_ADMIN_URL or settings.DATABASE_URL or "").strip()


async def _connect():
    import asyncpg

    url = _admin_url()
    if not url:
        raise SystemExit("DATABASE_ADMIN_URL or DATABASE_URL is required")
    return await asyncpg.connect(url)


async def run(mode: str) -> int:
    url = _admin_url()
    kind = _db_kind(url)
    parsed = urlparse(url)
    print(
        json.dumps(
            {
                "mode": mode,
                "db_kind": kind,
                "db_host": parsed.hostname,
                "db_name": (parsed.path or "").lstrip("/"),
                "db_user": parsed.username,
            },
            indent=2,
        )
    )

    conn = await _connect()
    try:
        before = await real_checksums(conn)
        policies = load_policies()
        ctx = await load_context(conn)
        plan = build_plan(ctx, policies)

        if mode == "dry-run":
            # Simulate thin-program expansion counts without writing.
            from seed_demo.apply import _complete_thin_programs

            await _complete_thin_programs(conn, plan)
            report = {
                "rows_to_add": plan.counts(),
                "real_checksums_before": before,
                "notes": plan.notes,
                "db_kind": kind,
                "stop_for_apply": kind == "hosted-supabase",
            }
            print(json.dumps(report, indent=2, default=str))
            if kind == "hosted-supabase":
                print(
                    "\nCHECKPOINT: environment points at hosted bnu_analytics. "
                    "Not applying. Say 'apply' to continue.",
                    file=sys.stderr,
                )
            return 0

        if mode == "reset-synthetic":
            deleted = await reset_owned(conn)
            after = await real_checksums(conn)
            print(
                json.dumps(
                    {
                        "deleted": deleted,
                        "real_checksums_before": before,
                        "real_checksums_after": after,
                        "real_unchanged": before == after,
                    },
                    indent=2,
                )
            )
            return 0 if before == after else 2

        # apply
        password = os.environ.get("DEMO_ACCOUNT_PASSWORD") or ""
        password_hash = get_password_hash(password) if password else None
        if not password:
            print(
                "WARNING: DEMO_ACCOUNT_PASSWORD unset; demo account hashes not updated",
                file=sys.stderr,
            )
        written = await apply_plan(conn, plan, password_hash=password_hash)
        after = await real_checksums(conn)
        checks = await verify_stories(conn)
        ok = all(c["ok"] for c in checks) and before == after
        print(
            json.dumps(
                {
                    "written": written,
                    "real_checksums_before": before,
                    "real_checksums_after": after,
                    "real_unchanged": before == after,
                    "answer_key_checks": checks,
                    "ok": ok,
                },
                indent=2,
                default=str,
            )
        )
        return 0 if ok else 1
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="BNU demo storyboard seeder")
    parser.add_argument(
        "mode",
        choices=("dry-run", "apply", "reset-synthetic"),
        help="dry-run reports counts; apply writes; reset-synthetic removes owned rows",
    )
    args = parser.parse_args(argv)
    raise SystemExit(asyncio.run(run(args.mode)))


if __name__ == "__main__":
    main()
