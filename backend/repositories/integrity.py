import asyncpg

from core.locale import Language, txt
from repositories.sql_filters import attempt_where
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters


def _short(title: str) -> str:
    return (title or "").split("—")[0].strip()


def _integrity_base_sql(where_sql: str, include_name: bool = True) -> str:
    """Participated attempts plus median-time and shared-IP signals.

    Does not join v_students. Student names come from v_exam_attempts when needed.
    Counts omit student_name so the planner can prune the people join.
    """
    name_col = "a.student_name,\n                " if include_name else ""
    return f"""
        participated AS MATERIALIZED (
            SELECT
                a.id,
                a.student_id,
                {name_col}a.exam_id,
                a.exam_title,
                a.course_code,
                a.started_at,
                a.ended_at,
                a.ip,
                a.device,
                a.attempt_count,
                a.late_start,
                a.time_taken_min,
                a.program
            FROM v_exam_attempts a
            WHERE a.participated AND {where_sql}
        ),
        medians AS MATERIALIZED (
            SELECT exam_id, percentile_cont(0.5) WITHIN GROUP (ORDER BY time_taken_min) AS median_time
            FROM participated
            WHERE time_taken_min IS NOT NULL
            GROUP BY exam_id
        ),
        ip_share AS MATERIALIZED (
            SELECT exam_id, ip, COUNT(DISTINCT student_id) AS n
            FROM participated
            WHERE ip IS NOT NULL AND ip <> ''
            GROUP BY exam_id, ip
            HAVING COUNT(DISTINCT student_id) > 1
        )
    """


def _is_flagged_sql(alias: str = "p") -> str:
    return f"""
        {alias}.id IN (SELECT f.attempt_id FROM integrity_flags f)
        OR {alias}.attempt_count > 1
        OR {alias}.late_start
        OR (
            {alias}.time_taken_min IS NOT NULL
            AND (
                {alias}.time_taken_min < 25
                OR (
                    m.median_time IS NOT NULL
                    AND {alias}.time_taken_min < m.median_time * 0.6
                )
            )
        )
        OR ip.n IS NOT NULL
    """


async def get_integrity_report(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language = "en",
):
    filters = filters or AnalyticsFilters()
    where_sql, args, _ = attempt_where(filters)

    rows = await db.fetch(
        f"""
        WITH {_integrity_base_sql(where_sql)},
        stored AS (
            SELECT f.attempt_id, ARRAY_AGG(REPLACE(f.flag_type::text, '_', ' ') ORDER BY f.flag_type) AS flags
            FROM integrity_flags f
            JOIN participated p ON p.id = f.attempt_id
            GROUP BY f.attempt_id
        )
        SELECT
            p.*,
            m.median_time,
            (ip.exam_id IS NOT NULL) AS shared_ip,
            COALESCE(st.flags, ARRAY[]::text[]) AS stored_flags
        FROM participated p
        LEFT JOIN medians m ON m.exam_id = p.exam_id
        LEFT JOIN ip_share ip ON ip.exam_id = p.exam_id AND ip.ip = p.ip
        LEFT JOIN stored st ON st.attempt_id = p.id
        ORDER BY p.started_at DESC NULLS LAST
        """,
        *args,
    )

    report_rows = []
    summary_map: dict[str, dict] = {}
    for a in rows:
        flags = [f.title() for f in (a["stored_flags"] or [])]
        if a["attempt_count"] and a["attempt_count"] > 1:
            flags.append(f"{a['attempt_count']} attempts")
        if (
            a["time_taken_min"] is not None
            and a["median_time"]
            and a["time_taken_min"] < float(a["median_time"]) * 0.6
        ):
            flags.append("Unusually fast submission")
        elif a["time_taken_min"] is not None and a["time_taken_min"] < 25:
            flags.append("Unusually fast submission")
        if a["late_start"]:
            flags.append("Late start")
        if a["shared_ip"]:
            flags.append("Shared IP address")
        flags = list(dict.fromkeys(flags))
        exam_label = f"{a['course_code']} · {_short(a['exam_title'])}"
        report_rows.append(
            {
                "id": f"{a['exam_id']}-{a['student_id']}",
                "student": a["student_name"],
                "exam": exam_label,
                "startedAt": str(a["started_at"]) if a["started_at"] else "",
                "endedAt": str(a["ended_at"]) if a["ended_at"] else "",
                "ip": a["ip"] or "",
                "device": a["device"] or "",
                "attempts": a["attempt_count"],
                "flags": flags,
            }
        )
        entry = summary_map.setdefault(
            exam_label,
            {"exam": exam_label, "program": a["program"], "flagged": 0, "total": 0},
        )
        entry["total"] += 1
        if flags:
            entry["flagged"] += 1

    flagged_count = sum(1 for r in report_rows if r["flags"])
    insight = (
        txt(
            language,
            f"{flagged_count} of {len(report_rows)} monitored attempts show at least one anomaly this period.",
            f"{flagged_count} من أصل {len(report_rows)} محاولة مراقبة تُظهر شذوذًا واحدًا على الأقل في هذه الفترة.",
        )
        if report_rows
        else txt(
            language,
            "No monitored attempts in this scope yet.",
            "لا محاولات مراقبة في هذا النطاق بعد.",
        )
    )
    return {
        "rows": report_rows,
        "summary": list(summary_map.values()),
        "flaggedCount": flagged_count,
        "totalAttempts": len(report_rows),
        "insight": insight,
    }


async def get_integrity_counts(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
) -> dict:
    """Aggregate flagged/total counts in SQL. No per-attempt payload."""
    filters = filters or AnalyticsFilters()
    where_sql, args, _ = attempt_where(filters)
    flagged_sql = _is_flagged_sql("p")

    rows = await db.fetch(
        f"""
        WITH {_integrity_base_sql(where_sql, include_name=False)},
        scored AS (
            SELECT
                p.course_code,
                p.exam_title,
                p.program,
                ({flagged_sql}) AS flagged
            FROM participated p
            LEFT JOIN medians m ON m.exam_id = p.exam_id
            LEFT JOIN ip_share ip ON ip.exam_id = p.exam_id AND ip.ip = p.ip
        )
        SELECT
            btrim(p.course_code || ' · ' || split_part(p.exam_title, '—', 1)) AS exam,
            p.program,
            COUNT(*) FILTER (WHERE p.flagged)::int AS flagged,
            COUNT(*)::int AS total,
            SUM(COUNT(*)::int) OVER ()::int AS total_attempts,
            SUM(COUNT(*) FILTER (WHERE p.flagged)::int) OVER ()::int AS flagged_count
        FROM scored p
        GROUP BY p.course_code, p.exam_title, p.program
        """,
        *args,
    )
    if not rows:
        return {
            "flaggedCount": 0,
            "totalAttempts": 0,
            "summary": [],
        }
    return {
        "flaggedCount": int(rows[0]["flagged_count"] or 0),
        "totalAttempts": int(rows[0]["total_attempts"] or 0),
        "summary": [
            {
                "exam": r["exam"],
                "program": r["program"],
                "flagged": int(r["flagged"]),
                "total": int(r["total"]),
            }
            for r in rows
        ],
    }
