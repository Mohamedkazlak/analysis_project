"""Validate one generated SELECT and attach the caller's scope before it runs."""

import re

import sqlglot
from sqlglot import exp

from rag.errors import QueryRejected
from rag.permissions import DENIED_TABLES, scope_plan
from schemas.auth import UserContext

MAX_ROWS = 50
_FORBIDDEN_TEXT = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|merge|"
    r"comment|do|call|execute|prepare|set|reset|vacuum|analyze|listen|notify|"
    r"security|owner|into|returning|offset|for\s+update|dblink|lo_import|"
    r"lo_export|set_config|current_setting|union|except|intersect"
    r")\b",
    re.IGNORECASE,
)
_ALLOWED_FUNCS = frozenset(
    {
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "round",
        "coalesce",
        "nullif",
        "lower",
        "upper",
        "cast",
        "date_trunc",
        "extract",
        "abs",
        "ceil",
        "ceiling",
        "floor",
        "greatest",
        "least",
        "concat",
        "trim",
        "btrim",
        "ltrim",
        "rtrim",
        "length",
        "substring",
        "current_date",
        "current_timestamp",
        "now",
        "date_part",
        "array_agg",
        "string_agg",
        "json_agg",
        "jsonb_agg",
        "bool_and",
        "bool_or",
        "case",
        "if",
        "row_number",
        "rank",
        "dense_rank",
    }
)
_TRAILING = re.compile(r"\b(group\s+by|order\s+by|having|limit)\b", re.IGNORECASE)


def _reject(status: int, detail: str) -> None:
    raise QueryRejected(status, detail)


def _clean(raw_sql: str) -> str:
    text = raw_sql.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.lower().startswith("sql"):
            text = text[3:]
    return text.strip().rstrip(";").strip()


def _parse_select(sql: str) -> exp.Expression:
    if not sql or len(sql) > 4000:
        _reject(400, "The query could not be validated")
    lowered = sql.lower()
    if "--" in sql or "/*" in sql or ";" in sql or "$" in sql:
        _reject(400, "The query could not be validated")
    if "pg_" in lowered or "information_schema" in lowered:
        _reject(403, "That query is outside your authorized data")
    if _FORBIDDEN_TEXT.search(sql):
        _reject(400, "Only a single read-only query is allowed")
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.SqlglotError:
        _reject(400, "The query could not be validated")
    if len(statements) != 1 or statements[0] is None:
        _reject(400, "Only a single read-only query is allowed")
    statement = statements[0]
    if not isinstance(statement, exp.Select):
        _reject(400, "Only a single read-only query is allowed")
    if statement.args.get("into"):
        _reject(400, "Only a single read-only query is allowed")
    if any(
        statement.find(kind)
        for kind in (exp.Union, exp.Except, exp.Intersect, exp.CTE, exp.Subquery)
    ):
        _reject(400, "That query is too complex to validate safely")
    for kind in (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Alter,
        exp.Create,
        exp.Command,
        exp.Grant,
        exp.Merge,
    ):
        if statement.find(kind):
            _reject(400, "Only a single read-only query is allowed")
    for func in statement.find_all(exp.Func):
        name = (func.sql_name() or "").lower()
        if name not in _ALLOWED_FUNCS:
            _reject(400, "The query could not be validated")
    return statement


def _table_refs(statement: exp.Expression) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for table in statement.find_all(exp.Table):
        name = (table.name or "").lower()
        if not name:
            _reject(400, "The query could not be validated")
        schema = (table.db or "").lower()
        if schema and schema != "public":
            _reject(403, "That query is outside your authorized data")
        alias = table.alias or table.name
        refs.append((name, alias))
    return refs


def _insert_filter(sql: str, predicate: str) -> str:
    connector = "AND" if re.search(r"\bwhere\b", sql, re.IGNORECASE) else "WHERE"
    clause = f" {connector} ({predicate})"
    match = _TRAILING.search(sql)
    if match:
        return f"{sql[: match.start()].rstrip()}{clause} {sql[match.start():]}"
    return sql + clause


def _cap_limit(sql: str) -> str:
    match = re.search(r"\blimit\s+(\d+)\s*$", sql, re.IGNORECASE)
    if match:
        if int(match.group(1)) > MAX_ROWS:
            return sql[: match.start()] + f"LIMIT {MAX_ROWS}"
        return sql
    return sql + f" LIMIT {MAX_ROWS + 1}"


def guard_sql(raw_sql: str, ctx: UserContext) -> tuple[str, object]:
    """Return scoped SQL and the single bind value (None when the role is unscoped)."""
    sql = _clean(raw_sql)
    statement = _parse_select(sql)
    plan = scope_plan(ctx)
    refs = _table_refs(statement)
    if not refs:
        _reject(400, "That question cannot be answered from your authorized data")

    used = {name for name, _alias in refs}
    if used & DENIED_TABLES or used - plan.tables:
        _reject(403, "That query is outside your authorized data")

    needs_filter = [name for name in used if name not in plan.unscoped_ok]
    if plan.must_filter and needs_filter:
        missing = [name for name in needs_filter if name not in plan.filters]
        if missing:
            _reject(400, "That question cannot be answered from your authorized data")
    if plan.must_filter and not needs_filter and not (used & set(plan.filters)):
        # Calendar-only questions are allowed for roles that have unscoped calendar tables.
        if not used <= plan.unscoped_ok:
            _reject(400, "That question cannot be answered from your authorized data")

    rendered = statement.sql(dialect="postgres")
    bind = None
    if plan.must_filter:
        applied = False
        for name, alias in refs:
            template = plan.filters.get(name)
            if not template:
                continue
            rendered = _insert_filter(rendered, template.format(ref=alias))
            applied = True
            bind = plan.bind
        if needs_filter and not applied:
            _reject(400, "That question cannot be answered from your authorized data")

    rendered = _cap_limit(rendered.strip().rstrip(";"))
    # Re-parse the original shape only. Injected predicates are server-written.
    if rendered.count(";") or "--" in rendered:
        _reject(400, "The query could not be validated")
    return rendered, bind
