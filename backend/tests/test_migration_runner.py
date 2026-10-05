from pathlib import Path

from run_migration import _strip_outer_transaction, collect_migrations


def test_collect_migrations_orders_by_filename(tmp_path: Path):
    (tmp_path / "002_second.sql").write_text("select 2")
    (tmp_path / "001_first.sql").write_text("select 1")
    names = [path.name for _, path in collect_migrations(tmp_path)]
    assert names == ["001_first.sql", "002_second.sql"]


def test_collect_migrations_rejects_duplicate_versions(tmp_path: Path):
    (tmp_path / "001_x.sql").write_text("select 1")
    (tmp_path / "001_y.sql").write_text("select 2")
    try:
        collect_migrations(tmp_path)
    except ValueError as exc:
        assert "Duplicate migration version 001" in str(exc)
        assert "001_x.sql" in str(exc)
        assert "001_y.sql" in str(exc)
    else:
        raise AssertionError("expected duplicate version error")


def test_collect_migrations_rejects_invalid_filename(tmp_path: Path):
    (tmp_path / "not-a-migration.sql").write_text("select 1")
    try:
        collect_migrations(tmp_path)
    except ValueError as exc:
        assert "Invalid migration filename" in str(exc)
    else:
        raise AssertionError("expected invalid filename error")


def test_strip_outer_transaction_ignores_leading_comments():
    sql = """
-- comment
-- another

begin;

create table t (id int);

commit;
"""
    stripped = _strip_outer_transaction(sql)
    assert "begin" not in stripped.lower()
    assert "commit" not in stripped.lower()
    assert "create table t (id int);" in stripped


def test_strip_outer_transaction_leaves_plpgsql_begin():
    sql = """
do $$
begin
  perform 1;
end $$;
"""
    stripped = _strip_outer_transaction(sql)
    assert "begin" in stripped.lower()


def test_repo_migrations_have_unique_padded_versions():
    from run_migration import DEFAULT_MIGRATIONS_DIR

    versions = [version for version, _ in collect_migrations(DEFAULT_MIGRATIONS_DIR)]
    assert versions == [
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
        "023",
    ]
