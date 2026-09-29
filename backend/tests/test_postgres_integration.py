"""PostgreSQL integration tests for schema, migrations, and RLS.

Skipped when the admin database is unreachable. CI provides
TEST_DATABASE_URL against a disposable Postgres service.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "db" / "schema.sql"
SEED = ROOT / "db" / "seed.sql"

ADMIN_URL = os.getenv("TEST_DATABASE_URL") or os.getenv(
    "DATABASE_ADMIN_URL", "postgresql://postgres@localhost:5432/postgres"
)
FRESH_DB = "bnu_analytics_ci_fresh"
MIGRATED_DB = "bnu_analytics_ci_migrated"

pytestmark = pytest.mark.integration


def _db_url(dbname: str) -> str:
    parsed = urlparse(ADMIN_URL)
    return urlunparse(parsed._replace(path=f"/{dbname}"))


def _app_url(dbname: str) -> str:
    parsed = urlparse(ADMIN_URL)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    password = parsed.password
    if password:
        netloc = f"app_user:{quote(password, safe='')}@{host}{port}"
    else:
        netloc = f"app_user@{host}{port}"
    return urlunparse(parsed._replace(netloc=netloc, path=f"/{dbname}"))


def _psql(url: str, *args: str, sql: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["psql", url, "-v", "ON_ERROR_STOP=1", "-q", *args]
    return subprocess.run(
        cmd,
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )


def _require_admin() -> None:
    host = (urlparse(ADMIN_URL).hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip(
            "Integration tests only run against local PostgreSQL. "
            f"Refusing host {host}."
        )
    result = _psql(ADMIN_URL, "-c", "SELECT 1")
    if result.returncode != 0:
        pytest.skip(f"PostgreSQL not available: {result.stderr.strip()}")


def _recreate(dbname: str) -> None:
    _psql(
        ADMIN_URL,
        sql=(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{dbname}' AND pid <> pg_backend_pid();"
        ),
    )
    drop = _psql(ADMIN_URL, "-c", f"DROP DATABASE IF EXISTS {dbname}")
    if drop.returncode != 0:
        pytest.fail(drop.stderr)
    created = _psql(ADMIN_URL, "-c", f"CREATE DATABASE {dbname}")
    if created.returncode != 0:
        pytest.fail(created.stderr)


def _apply_file(url: str, path: Path) -> None:
    result = _psql(url, "-f", str(path))
    if result.returncode != 0:
        pytest.fail(f"{path.name} failed:\n{result.stderr}\n{result.stdout}")


def _prepare_app_user(url: str) -> None:
    parsed = urlparse(url)
    dbname = parsed.path.lstrip("/")
    password = urlparse(ADMIN_URL).password
    if password:
        escaped = password.replace("'", "''")
        alter_sql = "ALTER ROLE app_user LOGIN PASSWORD '" + escaped + "';"
    else:
        alter_sql = "ALTER ROLE app_user LOGIN;"
    alter = _psql(url, sql=alter_sql)
    if alter.returncode != 0:
        pytest.fail(alter.stderr)
    grant = _psql(ADMIN_URL, "-c", f'GRANT CONNECT ON DATABASE "{dbname}" TO app_user')
    if grant.returncode != 0:
        pytest.fail(grant.stderr)


async def _fetch(url: str, sql: str, *args):
    import asyncpg

    conn = await asyncpg.connect(url)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


async def _fetch_as_app(dbname: str, user_id: str, sql: str):
    import asyncpg

    conn = await asyncpg.connect(_app_url(dbname))
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_user_id', $1, true)",
                user_id,
            )
            return await conn.fetch(sql)
    finally:
        await conn.close()


def _column_udt(url: str, table: str, column: str) -> str:
    rows = asyncio.run(
        _fetch(
            url,
            """
            SELECT udt_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=$1 AND column_name=$2
            """,
            table,
            column,
        )
    )
    return rows[0]["udt_name"]


def _policy_qual(url: str, table: str, policy: str) -> str:
    rows = asyncio.run(
        _fetch(
            url,
            """
            SELECT qual FROM pg_policies
            WHERE schemaname='public' AND tablename=$1 AND policyname=$2
            """,
            table,
            policy,
        )
    )
    return rows[0]["qual"] if rows else ""


RLS_EQUIVALENCE_USERS = (
    "u-president",
    "u-vp-aa",
    "u-dean-eng",
    "u-pd-cs",
    "u-aa-cs",
    "u-prof-cs",
    "u-it-integrity",
    "u-student",
)

RLS_EQUIVALENCE_QUERIES = {
    "org_units": "SELECT id AS k FROM org_units ORDER BY 1",
    "institution_settings": "SELECT org_unit_id AS k FROM institution_settings ORDER BY 1",
    "academic_years": "SELECT id AS k FROM academic_years ORDER BY 1",
    "terms": "SELECT id AS k FROM terms ORDER BY 1",
    "people": "SELECT id AS k FROM people ORDER BY 1",
    "staff": "SELECT person_id AS k FROM staff ORDER BY 1",
    "students": "SELECT id AS k FROM students ORDER BY 1",
    "user_accounts": "SELECT id AS k FROM user_accounts ORDER BY 1",
    "courses": "SELECT id AS k FROM courses ORDER BY 1",
    "course_offerings": "SELECT id AS k FROM course_offerings ORDER BY 1",
    "course_sections": "SELECT id AS k FROM course_sections ORDER BY 1",
    "staff_course_assignments": (
        "SELECT staff_person_id || ':' || course_id AS k "
        "FROM staff_course_assignments ORDER BY 1"
    ),
    "enrollments": "SELECT id AS k FROM enrollments ORDER BY 1",
    "exams": "SELECT id AS k FROM exams ORDER BY 1",
    "questions": "SELECT id AS k FROM questions ORDER BY 1",
    "exam_attempts": "SELECT id AS k FROM exam_attempts ORDER BY 1",
    "attempt_answers": (
        "SELECT attempt_id || ':' || question_id AS k FROM attempt_answers ORDER BY 1"
    ),
    "integrity_flags": "SELECT id AS k FROM integrity_flags ORDER BY 1",
    "transcript_entries": "SELECT id AS k FROM transcript_entries ORDER BY 1",
    "v_students": "SELECT id AS k FROM v_students ORDER BY 1",
    "v_exam_attempts": "SELECT id AS k FROM v_exam_attempts ORDER BY 1",
}

PER_ROW_AUTH_MARKERS = (
    "exam_attempt_is_visible",
    "student_is_visible(",
    "org_unit_is_visible(",
    "course_is_visible(",
    "offering_is_visible(",
    "exam_is_visible(",
    "attempt_is_visible(",
)


# Pre-011 schema: boolean RLS helpers, no InitPlan visibility sets / later policies.
# Never fall back to main — main already includes 013+ and breaks equivalence tests.
_LEGACY_SCHEMA_REFS = (
    "origin/production-hardening:db/schema.sql",
    "production-hardening:db/schema.sql",
)


def _git_show_text(*refs: str) -> str | None:
    for ref in refs:
        candidate = subprocess.run(
            ["git", "show", ref],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if candidate.returncode == 0 and candidate.stdout.strip():
            return candidate.stdout
    return None


def _legacy_schema_sql(tmp: Path) -> Path:
    shown = _git_show_text(*_LEGACY_SCHEMA_REFS)
    if shown is None:
        pytest.skip(
            "production-hardening:db/schema.sql is required as the pre-optimization "
            "baseline (do not use main — it already includes InitPlan RLS)."
        )
    legacy = tmp / "legacy_schema.sql"
    legacy.write_text(shown)
    return legacy


async def _snapshot_visible(dbname: str, user_id: str) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for table, sql in RLS_EQUIVALENCE_QUERIES.items():
        rows = await _fetch_as_app(dbname, user_id, sql)
        out[table] = tuple(r["k"] for r in rows)
    return out


def _walk_plan(node: dict):
    yield node
    for child in node.get("Plans") or []:
        yield from _walk_plan(child)


def _plan_mentions_per_row_helpers(plan: dict) -> list[str]:
    found: list[str] = []
    for node in _walk_plan(plan):
        blob = json.dumps(node)
        for marker in PER_ROW_AUTH_MARKERS:
            if marker in blob:
                found.append(marker)
    return sorted(set(found))


async def _explain_as_app(dbname: str, user_id: str, sql: str) -> dict:
    import asyncpg

    conn = await asyncpg.connect(_app_url(dbname))
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_user_id', $1, true)",
                user_id,
            )
            await conn.execute("SET LOCAL statement_timeout = '120s'")
            rows = await conn.fetch(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}")
            payload = rows[0][0]
            if isinstance(payload, str):
                payload = json.loads(payload)
            if isinstance(payload, list):
                payload = payload[0]
            return payload
    finally:
        await conn.close()


def _function_src(url: str, name: str) -> str:
    rows = asyncio.run(
        _fetch(
            url,
            """
            SELECT pg_get_functiondef(p.oid) AS def
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname = $1
            """,
            name,
        )
    )
    return rows[0]["def"] if rows else ""


def _constraint_names(url: str, table: str) -> set[str]:
    rows = asyncio.run(
        _fetch(
            url,
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = ($1::text)::regclass
            """,
            f"public.{table}",
        )
    )
    return {r["conname"] for r in rows}


@pytest.fixture(scope="module")
def fresh_db():
    _require_admin()
    _recreate(FRESH_DB)
    url = _db_url(FRESH_DB)
    _apply_file(url, SCHEMA)
    _apply_file(url, SEED)
    _prepare_app_user(url)
    yield url


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory):
    _require_admin()
    _recreate(MIGRATED_DB)
    url = _db_url(MIGRATED_DB)
    tmp = tmp_path_factory.mktemp("legacy")
    legacy = _legacy_schema_sql(tmp)
    _apply_file(url, legacy)
    env = os.environ.copy()
    env["DATABASE_ADMIN_URL"] = url
    env["DATABASE_URL"] = url
    runner = subprocess.run(
        [sys.executable, str(ROOT / "backend" / "run_migration.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if runner.returncode != 0:
        pytest.fail(f"migration runner failed:\n{runner.stdout}\n{runner.stderr}")
    if "already a transaction in progress" in (runner.stderr or "").lower():
        pytest.fail(f"nested transaction while migrating:\n{runner.stderr}")
    _prepare_app_user(url)
    yield url


def test_fresh_schema_curriculum_is_text_college(fresh_db):
    assert _column_udt(fresh_db, "courses", "requirement_level_type") == "text"
    assert _column_udt(fresh_db, "courses", "counted_in_cumulative_gpa") == "bool"
    assert _column_udt(fresh_db, "courses", "pass_fail_subject") == "bool"
    rows = asyncio.run(
        _fetch(
            fresh_db,
            "SELECT DISTINCT requirement_level_type AS v FROM courses ORDER BY 1",
        )
    )
    assert [r["v"] for r in rows] == ["college"]
    assert "current_visible_org_unit_ids" in _policy_qual(
        fresh_db, "org_units", "org_units_read"
    )
    tables = asyncio.run(
        _fetch(
            fresh_db,
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='schema_migrations'
            """,
        )
    )
    assert tables


def test_migrated_schema_matches_fresh_curriculum_and_org_policy(fresh_db, migrated_db):
    assert _column_udt(migrated_db, "courses", "requirement_level_type") == "text"
    assert _column_udt(migrated_db, "courses", "counted_in_cumulative_gpa") == "bool"
    assert _column_udt(migrated_db, "courses", "pass_fail_subject") == "bool"
    assert "current_visible_org_unit_ids" in _policy_qual(
        migrated_db, "org_units", "org_units_read"
    )
    assert "current_visible_org_unit_ids" in _policy_qual(
        fresh_db, "org_units", "org_units_read"
    )
    versions = asyncio.run(
        _fetch(
            migrated_db,
            "SELECT version FROM public.schema_migrations ORDER BY version",
        )
    )
    assert [r["version"] for r in versions] == [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006",
        "007",
        "008",
        "009",
        "010",
        "011",
        "012",
        "013",
        "014",
        "015",
        "016",
        "019",
        "020",
        "021",
        "022",
    ]
    sector_col = asyncio.run(
        _fetch(
            migrated_db,
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='v_exam_attempts'
              AND column_name IN ('sector_id', 'program_id', 'section', 'student_name')
            ORDER BY 1
            """,
        )
    )
    assert [r["column_name"] for r in sector_col] == [
        "program_id",
        "section",
        "sector_id",
        "student_name",
    ]
    org_src = _function_src(fresh_db, "current_visible_org_unit_ids")
    migrated_org_src = _function_src(migrated_db, "current_visible_org_unit_ids")
    assert "org_unit_is_visible" not in org_src
    assert "UNION" in org_src.upper()
    assert "org_unit_is_visible" not in migrated_org_src
    assert "UNION" in migrated_org_src.upper()
    assert "exam_attempts_enrollment_student_fk" in _constraint_names(
        fresh_db, "exam_attempts"
    )
    assert "exam_attempts_enrollment_student_fk" in _constraint_names(
        migrated_db, "exam_attempts"
    )
    assert "enrollments_id_student_id_key" in _constraint_names(fresh_db, "enrollments")
    assert "enrollments_id_student_id_key" in _constraint_names(
        migrated_db, "enrollments"
    )


def test_migration_runner_skips_already_applied(migrated_db):
    env = os.environ.copy()
    env["DATABASE_ADMIN_URL"] = migrated_db
    env["DATABASE_URL"] = migrated_db
    runner = subprocess.run(
        [sys.executable, str(ROOT / "backend" / "run_migration.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert runner.returncode == 0, runner.stderr
    assert "already a transaction in progress" not in runner.stderr
    assert "skip 001_curriculum_metadata.sql (already applied)" in runner.stdout
    assert "skip 007_org_unit_rls_and_helpers.sql (already applied)" in runner.stdout
    assert (
        "skip 008_revoke_anon_execute_on_helpers.sql (already applied)" in runner.stdout
    )
    assert (
        "skip 009_disable_schema_migrations_rls.sql (already applied)" in runner.stdout
    )
    assert "skip 010_syn_transc_marker_backfill.sql (already applied)" in runner.stdout
    assert (
        "skip 011_set_updated_at_search_path_and_fk_indexes.sql (already applied)"
        in runner.stdout
    )
    assert (
        "skip 012_exam_attempts_enrollment_student_fk.sql (already applied)"
        in runner.stdout
    )
    assert (
        "skip 013_rls_initplan_visibility_sets.sql (already applied)" in runner.stdout
    )
    assert "skip 014_professor_staff_isolation.sql (already applied)" in runner.stdout
    assert "skip 015_exam_attempts_section.sql (already applied)" in runner.stdout
    assert "skip 016_ai_insights_attempt_scale.sql (already applied)" in runner.stdout
    assert "skip 019_api_key_login_and_rag_audit.sql (already applied)" in runner.stdout
    assert "skip 020_api_keys_allow_rotation.sql (already applied)" in runner.stdout
    assert "skip 021_password_and_api_key_login.sql (already applied)" in runner.stdout
    assert (
        "skip 022_password_login_without_client_key.sql (already applied)"
        in runner.stdout
    )
    assert not any(line.startswith("applied ") for line in runner.stdout.splitlines())


def test_failed_migration_rolls_back_and_is_not_recorded(tmp_path):
    _require_admin()
    dbname = "bnu_analytics_ci_migfail"
    _recreate(dbname)
    url = _db_url(dbname)
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_ok.sql").write_text("create table mig_ok (id int);")
    (migrations / "002_bad.sql").write_text(
        "create table mig_bad (id int);\nselect 1 / 0;"
    )
    from run_migration import apply_migrations

    with pytest.raises(Exception):
        asyncio.run(apply_migrations(url, migrations))

    recorded = asyncio.run(
        _fetch(url, "SELECT version FROM public.schema_migrations ORDER BY version")
    )
    assert [r["version"] for r in recorded] == ["001"]
    present = asyncio.run(
        _fetch(
            url,
            "SELECT to_regclass('public.mig_ok') AS ok, to_regclass('public.mig_bad') AS bad",
        )
    )
    assert present[0]["ok"] == "mig_ok"
    assert present[0]["bad"] is None


def test_migration_003_marks_owner_synthetic_ids_and_keeps_default_false():
    _require_admin()
    dbname = "bnu_analytics_ci_syn003"
    _recreate(dbname)
    url = _db_url(dbname)
    setup = _psql(
        url,
        sql="""
        CREATE TABLE exams (id text PRIMARY KEY);
        CREATE TABLE questions (id text PRIMARY KEY, exam_id text);
        CREATE TABLE exam_attempts (id text PRIMARY KEY, exam_id text);
        CREATE TABLE attempt_answers (
          attempt_id text NOT NULL,
          question_id text NOT NULL,
          PRIMARY KEY (attempt_id, question_id)
        );
        CREATE TABLE integrity_flags (id text PRIMARY KEY, attempt_id text);
        CREATE TABLE transcript_entries (id text PRIMARY KEY);

        INSERT INTO exams (id) VALUES
          ('syn-exam-1'), ('e1'), ('ex-midterm'), ('imported-exam-99');
        INSERT INTO questions (id, exam_id) VALUES
          ('q-1', 'e1'),
          ('child-of-syn', 'syn-exam-1'),
          ('imported-q-1', 'imported-exam-99');
        INSERT INTO exam_attempts (id, exam_id) VALUES
          ('att-1', 'e1'),
          ('child-att-syn', 'syn-exam-1'),
          ('imported-att-1', 'imported-exam-99');
        INSERT INTO attempt_answers (attempt_id, question_id) VALUES
          ('att-1', 'q-1'),
          ('imported-att-1', 'imported-q-1');
        INSERT INTO integrity_flags (id, attempt_id) VALUES
          ('flg-1', 'att-1'),
          ('imported-flg-1', 'imported-att-1');
        INSERT INTO transcript_entries (id) VALUES
          ('tr-s1-c1'), ('syn-transc-1'), ('imported-transc-99');
        """,
    )
    if setup.returncode != 0:
        pytest.fail(setup.stderr)

    migration = ROOT / "db" / "migrations" / "003_synthetic-data-markers.sql"
    _apply_file(url, migration)
    _apply_file(url, migration)

    def flags(table: str) -> dict[str, bool]:
        rows = asyncio.run(_fetch(url, f"SELECT id, is_synthetic FROM {table}"))
        return {r["id"]: r["is_synthetic"] for r in rows}

    assert flags("exams") == {
        "syn-exam-1": True,
        "e1": True,
        "ex-midterm": True,
        "imported-exam-99": False,
    }
    assert flags("questions") == {
        "q-1": True,
        "child-of-syn": True,
        "imported-q-1": False,
    }
    assert flags("exam_attempts") == {
        "att-1": True,
        "child-att-syn": True,
        "imported-att-1": False,
    }
    assert flags("integrity_flags") == {
        "flg-1": True,
        "imported-flg-1": False,
    }
    assert flags("transcript_entries") == {
        "tr-s1-c1": True,
        "syn-transc-1": True,
        "imported-transc-99": False,
    }
    answer_rows = asyncio.run(
        _fetch(
            url,
            "SELECT attempt_id, is_synthetic FROM attempt_answers ORDER BY attempt_id",
        )
    )
    assert [(r["attempt_id"], r["is_synthetic"]) for r in answer_rows] == [
        ("att-1", True),
        ("imported-att-1", False),
    ]

    inserted = _psql(
        url,
        sql="INSERT INTO transcript_entries (id) VALUES ('future-unspecified');",
    )
    if inserted.returncode != 0:
        pytest.fail(inserted.stderr)
    future = asyncio.run(
        _fetch(
            url,
            "SELECT is_synthetic FROM transcript_entries WHERE id = 'future-unspecified'",
        )
    )
    assert future[0]["is_synthetic"] is False

    default_row = asyncio.run(
        _fetch(
            url,
            """
            SELECT column_default, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'transcript_entries'
              AND column_name = 'is_synthetic'
            """,
        )
    )
    assert default_row[0]["is_nullable"] == "NO"
    assert "false" in default_row[0]["column_default"].lower()


def test_migration_006_backfills_only_synthetic_attempts_after_003():
    _require_admin()
    dbname = "bnu_analytics_ci_syn006"
    _recreate(dbname)
    url = _db_url(dbname)
    setup = _psql(
        url,
        sql="""
        CREATE TABLE exams (id text PRIMARY KEY);
        CREATE TABLE questions (
          id text PRIMARY KEY,
          exam_id text,
          number smallint NOT NULL DEFAULT 1,
          max_score numeric(6, 2) NOT NULL DEFAULT 1
        );
        CREATE TABLE exam_attempts (
          id text PRIMARY KEY,
          exam_id text,
          student_id text NOT NULL DEFAULT 's1',
          status text NOT NULL DEFAULT 'submitted'
        );
        CREATE TABLE attempt_answers (
          attempt_id text NOT NULL,
          question_id text NOT NULL,
          is_correct boolean NOT NULL DEFAULT false,
          points numeric(6, 2),
          PRIMARY KEY (attempt_id, question_id)
        );
        CREATE TABLE integrity_flags (id text PRIMARY KEY, attempt_id text);
        CREATE TABLE transcript_entries (id text PRIMARY KEY);

        INSERT INTO exams (id) VALUES ('syn-exam-1'), ('imported-exam-99');
        INSERT INTO questions (id, exam_id, number, max_score) VALUES
          ('item-syn', 'syn-exam-1', 1, 5),
          ('imported-q-1', 'imported-exam-99', 1, 5);
        INSERT INTO exam_attempts (id, exam_id, student_id, status) VALUES
          ('attempt-syn', 'syn-exam-1', 's1', 'submitted'),
          ('attempt-absent', 'syn-exam-1', 's2', 'absent'),
          ('imported-att-1', 'imported-exam-99', 's3', 'submitted');
        INSERT INTO transcript_entries (id) VALUES ('syn-transc-1');
        """,
    )
    if setup.returncode != 0:
        pytest.fail(setup.stderr)

    _apply_file(url, ROOT / "db" / "migrations" / "003_synthetic-data-markers.sql")
    _apply_file(url, ROOT / "db" / "migrations" / "006_synthetic_item_answers.sql")
    _apply_file(url, ROOT / "db" / "migrations" / "006_synthetic_item_answers.sql")

    rows = asyncio.run(
        _fetch(
            url,
            """
            SELECT attempt_id, question_id, is_synthetic
            FROM attempt_answers
            ORDER BY attempt_id, question_id
            """,
        )
    )
    assert [(r["attempt_id"], r["question_id"], r["is_synthetic"]) for r in rows] == [
        ("attempt-syn", "item-syn", True)
    ]
    marked = asyncio.run(
        _fetch(
            url,
            "SELECT is_synthetic FROM transcript_entries WHERE id = 'syn-transc-1'",
        )
    )
    assert marked[0]["is_synthetic"] is True


def test_migration_010_backfills_unmarked_syn_transc_via_runner():
    _require_admin()
    dbname = "bnu_analytics_ci_syn010"
    _recreate(dbname)
    url = _db_url(dbname)
    setup = _psql(
        url,
        sql="""
        CREATE TABLE transcript_entries (
          id text PRIMARY KEY,
          is_synthetic boolean NOT NULL DEFAULT false
        );
        INSERT INTO transcript_entries (id, is_synthetic) VALUES
          ('syn-transc-needs-backfill', false),
          ('syn-transc-already-true', true),
          ('tr-s1-c1', false),
          ('imported-transc-99', false);

        CREATE TABLE public.schema_migrations (
          version text PRIMARY KEY,
          filename text NOT NULL,
          applied_at timestamptz NOT NULL DEFAULT now()
        );
        INSERT INTO public.schema_migrations (version, filename) VALUES
          ('001', '001_curriculum_metadata.sql'),
          ('002', '002_performance_indexes.sql'),
          ('003', '003_synthetic-data-markers.sql'),
          ('004', '004_exam_attempt_scope_columns.sql'),
          ('005', '005_auth_and_exam_average_helpers.sql'),
          ('006', '006_synthetic_item_answers.sql'),
          ('007', '007_org_unit_rls_and_helpers.sql'),
          ('008', '008_revoke_anon_execute_on_helpers.sql'),
          ('009', '009_disable_schema_migrations_rls.sql'),
          ('011', '011_set_updated_at_search_path_and_fk_indexes.sql'),
          ('012', '012_exam_attempts_enrollment_student_fk.sql'),
          ('013', '013_rls_initplan_visibility_sets.sql'),
          ('014', '014_professor_staff_isolation.sql'),
          ('015', '015_exam_attempts_section.sql'),
          ('016', '016_ai_insights_attempt_scale.sql'),
          ('019', '019_api_key_login_and_rag_audit.sql'),
          ('020', '020_api_keys_allow_rotation.sql'),
          ('021', '021_password_and_api_key_login.sql'),
          ('022', '022_password_login_without_client_key.sql');
        """,
    )
    if setup.returncode != 0:
        pytest.fail(setup.stderr)

    before = asyncio.run(
        _fetch(
            url,
            """
            SELECT id, is_synthetic, xmin::text AS xmin
            FROM transcript_entries
            """,
        )
    )
    before_map = {r["id"]: r for r in before}

    from run_migration import DEFAULT_MIGRATIONS_DIR, apply_migrations

    log = asyncio.run(apply_migrations(url, DEFAULT_MIGRATIONS_DIR))
    assert "applied 010_syn_transc_marker_backfill.sql" in log
    assert "skip 003_synthetic-data-markers.sql (already applied)" in log
    assert not any(line.startswith("applied ") and "010_" not in line for line in log)

    after = asyncio.run(
        _fetch(
            url,
            """
            SELECT id, is_synthetic, xmin::text AS xmin
            FROM transcript_entries
            """,
        )
    )
    after_map = {r["id"]: r for r in after}
    assert after_map["syn-transc-needs-backfill"]["is_synthetic"] is True
    assert (
        after_map["syn-transc-needs-backfill"]["xmin"]
        != before_map["syn-transc-needs-backfill"]["xmin"]
    )
    assert after_map["syn-transc-already-true"]["is_synthetic"] is True
    assert (
        after_map["syn-transc-already-true"]["xmin"]
        == before_map["syn-transc-already-true"]["xmin"]
    )
    assert after_map["tr-s1-c1"]["is_synthetic"] is False
    assert after_map["tr-s1-c1"]["xmin"] == before_map["tr-s1-c1"]["xmin"]
    assert after_map["imported-transc-99"]["is_synthetic"] is False
    assert (
        after_map["imported-transc-99"]["xmin"]
        == before_map["imported-transc-99"]["xmin"]
    )

    recorded = asyncio.run(
        _fetch(
            url,
            "SELECT version, filename FROM public.schema_migrations ORDER BY version",
        )
    )
    assert [r["version"] for r in recorded] == [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006",
        "007",
        "008",
        "009",
        "010",
        "011",
        "012",
        "013",
        "014",
        "015",
        "016",
        "019",
        "020",
        "021",
        "022",
    ]
    assert recorded[-1]["filename"] == "022_password_login_without_client_key.sql"

    _apply_file(url, ROOT / "db" / "migrations" / "010_syn_transc_marker_backfill.sql")
    reapplied = asyncio.run(
        _fetch(
            url,
            """
            SELECT id, is_synthetic, xmin::text AS xmin
            FROM transcript_entries
            """,
        )
    )
    reapplied_map = {r["id"]: r for r in reapplied}
    for row_id, row in after_map.items():
        assert reapplied_map[row_id]["is_synthetic"] == row["is_synthetic"]
        assert reapplied_map[row_id]["xmin"] == row["xmin"]

    second = asyncio.run(apply_migrations(url, DEFAULT_MIGRATIONS_DIR))
    assert "skip 010_syn_transc_marker_backfill.sql (already applied)" in second
    assert not any(line.startswith("applied ") for line in second)


def test_rls_student_cannot_see_other_students(fresh_db):
    rows = asyncio.run(_fetch_as_app(FRESH_DB, "u-student", "SELECT id FROM students"))
    assert [r["id"] for r in rows] == ["s7"]


def test_rls_professor_sees_only_enrolled_assigned_students(fresh_db):
    rows = asyncio.run(_fetch_as_app(FRESH_DB, "u-prof-cs", "SELECT id FROM students"))
    ids = {r["id"] for r in rows}
    assert "s7" in ids
    assert "s70" not in ids


def test_rls_professor_cannot_see_other_faculty(fresh_db):
    rows = asyncio.run(
        _fetch_as_app(FRESH_DB, "u-prof-cs", "SELECT person_id FROM staff")
    )
    ids = {r["person_id"] for r in rows}
    assert "p-tomas-oyelaran" in ids
    assert "p-yasser-mansour" not in ids
    assert "p-mai-khalil" not in ids
    assert "p-daniel-osei" not in ids


def test_rls_sector_dean_cannot_see_foreign_org_units(fresh_db):
    sectors = asyncio.run(
        _fetch_as_app(
            FRESH_DB,
            "u-dean-eng",
            "SELECT id FROM org_units WHERE level = 'sector'",
        )
    )
    sector_ids = {r["id"] for r in sectors}
    assert "sec-engineering" in sector_ids
    assert "sec-health" not in sector_ids
    colleges = asyncio.run(
        _fetch_as_app(
            FRESH_DB,
            "u-dean-eng",
            "SELECT id FROM org_units WHERE level = 'program'",
        )
    )
    college_ids = {r["id"] for r in colleges}
    assert "prog-computer-science" in college_ids
    assert "prog-medicine" not in college_ids


def test_rls_program_director_cannot_see_other_college(fresh_db):
    rows = asyncio.run(
        _fetch_as_app(
            FRESH_DB,
            "u-pd-cs",
            "SELECT id FROM org_units WHERE level = 'program'",
        )
    )
    assert [r["id"] for r in rows] == ["prog-computer-science"]


def test_rls_university_sm_sees_all_sectors(fresh_db):
    rows = asyncio.run(
        _fetch_as_app(
            FRESH_DB,
            "u-president",
            "SELECT id FROM org_units WHERE level = 'sector'",
        )
    )
    ids = {r["id"] for r in rows}
    assert {"sec-engineering", "sec-health", "sec-humanities"} <= ids


def test_rls_it_does_not_see_transcripts(fresh_db):
    rows = asyncio.run(
        _fetch_as_app(
            FRESH_DB,
            "u-it-integrity",
            "SELECT count(*)::int AS n FROM transcript_entries",
        )
    )
    assert rows[0]["n"] == 0


def test_http_student_and_professor_scope(fresh_db):
    import hashlib

    from core.config import settings
    from core.security import create_access_token, decode_access_token
    from fastapi.testclient import TestClient

    student_key = "bnu_student_integration_key_0001"
    professor_key = "bnu_professor_integration_key_001"
    revoked_key = "bnu_student_revoked_integration_key"
    expired_key = "bnu_student_expired_integration_key"
    password = "integration-pass"

    def _hash(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def _prepare_keys():
        import asyncpg

        conn = await asyncpg.connect(fresh_db)
        try:
            await conn.execute("UPDATE user_accounts SET is_active = true")
            from core.security import get_password_hash

            password_hash = get_password_hash(password)
            await conn.execute(
                """
                UPDATE user_accounts
                SET password_hash = $2
                WHERE id = ANY($1::text[])
                """,
                ["u-student", "u-prof-cs", "u-president"],
                password_hash,
            )
            await conn.execute(
                """
                INSERT INTO api_keys (id, user_id, key_prefix, key_hash, is_active, label)
                VALUES
                  ('k-student', 'u-student', $1, $2, true, 'integration'),
                  ('k-professor', 'u-prof-cs', $3, $4, true, 'integration'),
                  ('k-revoked', 'u-student', $5, $6, false, 'integration-revoked'),
                  ('k-expired', 'u-student', $7, $8, true, 'integration-expired'),
                  ('k-president', 'u-president', $9, $10, false, 'integration-revoked')
                """,
                student_key[:12],
                _hash(student_key),
                professor_key[:12],
                _hash(professor_key),
                revoked_key[:12],
                _hash(revoked_key),
                expired_key[:12],
                _hash(expired_key),
                "bnu_president"[:12],
                _hash("bnu_president_revoked_key_0001"),
            )
            await conn.execute(
                """
                UPDATE api_keys
                SET revoked_at = now()
                WHERE id IN ('k-revoked', 'k-president')
                """
            )
            await conn.execute(
                """
                UPDATE api_keys
                SET expires_at = now() - interval '1 day'
                WHERE id = 'k-expired'
                """
            )
        finally:
            await conn.close()

    asyncio.run(_prepare_keys())
    settings.DATABASE_URL = _app_url(FRESH_DB)
    settings.APP_ENV = "test"
    from main import app

    with TestClient(app) as client:
        assert (
            client.post(
                "/auth/login",
                json={"id": "u-president", "password": password},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/auth/login",
                json={"id": "u-student", "password": "wrong-password"},
            ).status_code
            == 401
        )
        login = client.post(
            "/auth/login",
            json={"id": "u-student", "password": password},
        )
        assert login.status_code == 200, login.text
        body = login.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["user_id"] == "u-student"
        assert body["user"]["role"] == "student"
        payload = decode_access_token(body["access_token"])
        assert payload["user_id"] == "u-student"
        assert "role" not in payload
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        assert client.get("/api/student-dashboard", headers=headers).status_code == 200
        assert (
            client.get(
                "/api/student-dashboard?studentId=s70", headers=headers
            ).status_code
            == 403
        )
        assert client.get("/api/students/s70", headers=headers).status_code == 403
        assert (
            client.get(
                "/api/student-performance?studentId=s70", headers=headers
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/student-directory?studentId=s70", headers=headers
            ).status_code
            == 403
        )

        async def _deactivate():
            import asyncpg

            conn = await asyncpg.connect(fresh_db)
            try:
                await conn.execute(
                    "UPDATE user_accounts SET is_active = false WHERE id = 'u-student'"
                )
            finally:
                await conn.close()

        asyncio.run(_deactivate())
        assert (
            client.post(
                "/auth/login",
                json={"id": "u-student", "password": password},
            ).status_code
            == 401
        )
        unknown = client.get(
            "/auth/me",
            headers={
                "Authorization": "Bearer "
                + create_access_token({"user_id": "does-not-exist"})
            },
        )
        assert unknown.status_code == 401

        async def _reactivate():
            import asyncpg

            conn = await asyncpg.connect(fresh_db)
            try:
                await conn.execute(
                    "UPDATE user_accounts SET is_active = true WHERE id = 'u-student'"
                )
            finally:
                await conn.close()

        asyncio.run(_reactivate())

        prof = client.post(
            "/auth/login",
            json={"id": "u-prof-cs", "password": password},
        )
        assert prof.status_code == 200
        pheaders = {"Authorization": f"Bearer {prof.json()['access_token']}"}
        allowed = client.get("/api/students/s7", headers=pheaders)
        assert allowed.status_code == 200
        assert client.get("/api/students/s70", headers=pheaders).status_code == 403
        assert (
            client.get(
                "/api/filter-options?curriculumId=c10", headers=pheaders
            ).status_code
            == 403
        )


def test_rls_vp_aa_sees_all_sectors(fresh_db):
    rows = asyncio.run(
        _fetch_as_app(
            FRESH_DB,
            "u-vp-aa",
            "SELECT id FROM org_units WHERE level = 'sector'",
        )
    )
    ids = {r["id"] for r in rows}
    assert {"sec-engineering", "sec-health", "sec-humanities"} <= ids


def test_exam_attempts_composite_fk_rejects_mismatched_student(fresh_db):
    setup = _psql(
        fresh_db,
        sql="""
        DO $$
        DECLARE
          attempt_exam text;
          attempt_enroll text;
          other_student text;
        BEGIN
          SELECT a.exam_id, a.enrollment_id, s.id
            INTO attempt_exam, attempt_enroll, other_student
          FROM exam_attempts a
          JOIN students s ON s.id <> a.student_id
          WHERE NOT EXISTS (
            SELECT 1
            FROM exam_attempts a2
            WHERE a2.exam_id = a.exam_id
              AND a2.student_id = s.id
          )
          LIMIT 1;
          INSERT INTO exam_attempts (id, exam_id, student_id, enrollment_id, status)
          VALUES (
            'att-fk-mismatch-test',
            attempt_exam,
            other_student,
            attempt_enroll,
            'absent'
          );
        END $$;
        """,
    )
    assert setup.returncode != 0, setup.stdout
    assert "exam_attempts_enrollment_student_fk" in setup.stderr
    leftover = asyncio.run(
        _fetch(
            fresh_db,
            "SELECT 1 FROM exam_attempts WHERE id = 'att-fk-mismatch-test'",
        )
    )
    assert leftover == []


def test_migration_012_refuses_violating_rows_without_rewriting_them():
    _require_admin()
    dbname = "bnu_analytics_ci_fk012"
    _recreate(dbname)
    url = _db_url(dbname)
    setup = _psql(
        url,
        sql="""
        CREATE TABLE enrollments (
          id text PRIMARY KEY,
          student_id text NOT NULL
        );
        CREATE TABLE exam_attempts (
          id text PRIMARY KEY,
          enrollment_id text NOT NULL,
          student_id text NOT NULL
        );
        INSERT INTO enrollments (id, student_id) VALUES ('enr-1', 's1');
        INSERT INTO exam_attempts (id, enrollment_id, student_id)
        VALUES ('att-1', 'enr-1', 's2');
        """,
    )
    if setup.returncode != 0:
        pytest.fail(setup.stderr)
    migration = (
        ROOT / "db" / "migrations" / "012_exam_attempts_enrollment_student_fk.sql"
    )
    result = _psql(url, "-f", str(migration))
    assert result.returncode != 0
    assert "exam_attempts_enrollment_student_fk" in result.stderr
    rows = asyncio.run(
        _fetch(url, "SELECT id, student_id FROM exam_attempts ORDER BY 1")
    )
    assert [(r["id"], r["student_id"]) for r in rows] == [("att-1", "s2")]
    constraints = asyncio.run(
        _fetch(
            url,
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'public.exam_attempts'::regclass
            """,
        )
    )
    assert "exam_attempts_enrollment_student_fk" not in {
        r["conname"] for r in constraints
    }


def test_rls_v_exam_attempts_plan_uses_initplan_not_per_row_helpers(fresh_db):
    plan = asyncio.run(
        _explain_as_app(
            FRESH_DB,
            "u-president",
            "SELECT count(*) FROM public.v_exam_attempts",
        )
    )
    assert _plan_mentions_per_row_helpers(plan) == []
    blob = json.dumps(plan)
    assert "hashed SubPlan" in blob
    for node in _walk_plan(plan["Plan"]):
        if node.get("Parent Relationship") == "SubPlan":
            assert node.get("Actual Loops", 1) <= 1
    join_plan = asyncio.run(
        _explain_as_app(
            FRESH_DB,
            "u-president",
            """
            SELECT count(*)
            FROM public.v_exam_attempts a
            JOIN public.v_students s ON s.id = a.student_id
            """,
        )
    )
    assert _plan_mentions_per_row_helpers(join_plan) == []
    join_blob = json.dumps(join_plan)
    assert "hashed SubPlan" in join_blob


def test_rls_visibility_sets_match_pre_optimization_boolean_helpers(tmp_path):
    _require_admin()
    dbname = "bnu_analytics_ci_rls_eq"
    _recreate(dbname)
    url = _db_url(dbname)
    _apply_file(url, _legacy_schema_sql(tmp_path))
    _apply_file(url, SEED)
    _prepare_app_user(url)

    before: dict[str, dict[str, tuple[str, ...]]] = {}
    for user_id in RLS_EQUIVALENCE_USERS:
        before[user_id] = asyncio.run(_snapshot_visible(dbname, user_id))

    before_plan = asyncio.run(
        _explain_as_app(
            dbname,
            "u-president",
            "SELECT count(*) FROM public.v_exam_attempts",
        )
    )

    for name in (
        "011_set_updated_at_search_path_and_fk_indexes.sql",
        "012_exam_attempts_enrollment_student_fk.sql",
        "013_rls_initplan_visibility_sets.sql",
    ):
        _apply_file(url, ROOT / "db" / "migrations" / name)

    after: dict[str, dict[str, tuple[str, ...]]] = {}
    for user_id in RLS_EQUIVALENCE_USERS:
        after[user_id] = asyncio.run(_snapshot_visible(dbname, user_id))

    mismatches = []
    for user_id in RLS_EQUIVALENCE_USERS:
        for table in RLS_EQUIVALENCE_QUERIES:
            if before[user_id][table] != after[user_id][table]:
                mismatches.append(
                    (
                        user_id,
                        table,
                        len(before[user_id][table]),
                        len(after[user_id][table]),
                    )
                )
    assert mismatches == [], mismatches

    after_plan = asyncio.run(
        _explain_as_app(
            dbname,
            "u-president",
            "SELECT count(*) FROM public.v_exam_attempts",
        )
    )
    assert _plan_mentions_per_row_helpers(after_plan) == []
    assert _plan_mentions_per_row_helpers(before_plan)
    assert before["u-dean-eng"]["org_units"] != before["u-president"]["org_units"]
    assert "sec-health" not in before["u-dean-eng"]["org_units"]
    assert "s70" not in before["u-student"]["students"]
    assert before["u-it-integrity"]["transcript_entries"] == ()
    _ = before_plan
