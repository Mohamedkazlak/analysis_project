"""Answer-key SQL assertions for planted stories."""

from __future__ import annotations

from seed_demo.constants import (
    AIM303_COURSE_ID,
    AIM303_EXAM_2025,
    PROGRAMS,
    S1_PASS_2025,
    S1_SECTION_GAP,
    S5_COURSE_ID,
    S5_PASS,
)


async def verify_stories(conn) -> list[dict]:
    results: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        results.append({"name": name, "ok": ok, "detail": detail})

    # S1 pass rate ~50%
    row = await conn.fetchrow(
        """
        SELECT COUNT(*) FILTER (WHERE score IS NOT NULL)::float AS scored,
               COUNT(*) FILTER (WHERE score >= 60)::float AS passed
        FROM exam_attempts WHERE exam_id = $1 AND is_synthetic = true
        """,
        AIM303_EXAM_2025,
    )
    rate = (row["passed"] / row["scored"]) if row and row["scored"] else 0
    check(
        "S1_pass_rate",
        abs(rate - S1_PASS_2025) <= 0.08,
        f"pass_rate={rate:.3f} target={S1_PASS_2025} n={row['scored'] if row else 0}",
    )

    # S1 section gap ~15
    gap_row = await conn.fetchrow(
        """
        SELECT
          AVG(a.score) FILTER (WHERE cs.code = 'A') AS avg_a,
          AVG(a.score) FILTER (WHERE cs.code = 'B') AS avg_b
        FROM exam_attempts a
        JOIN enrollments e ON e.id = a.enrollment_id
        JOIN course_sections cs ON cs.id = e.section_id
        WHERE a.exam_id = $1 AND a.score IS NOT NULL
        """,
        AIM303_EXAM_2025,
    )
    if gap_row and gap_row["avg_a"] is not None and gap_row["avg_b"] is not None:
        gap = float(gap_row["avg_a"]) - float(gap_row["avg_b"])
        check(
            "S1_section_gap",
            abs(gap - S1_SECTION_GAP) <= 6.0,
            f"gap={gap:.1f} target={S1_SECTION_GAP}",
        )
    else:
        check("S1_section_gap", False, "missing section averages")

    # S1 weak topics <= 30% correct
    topic_rows = await conn.fetch(
        """
        SELECT q.topic,
               AVG(CASE WHEN ans.is_correct THEN 1.0 ELSE 0.0 END) AS correct_rate
        FROM attempt_answers ans
        JOIN questions q ON q.id = ans.question_id
        WHERE q.exam_id = $1 AND ans.is_synthetic
        GROUP BY q.topic
        """,
        AIM303_EXAM_2025,
    )
    weak = [r for r in topic_rows if r["topic"] in ("Use Cases", "Sequence Diagrams")]
    strong = [r for r in topic_rows if r["topic"] not in ("Use Cases", "Sequence Diagrams")]
    weak_ok = bool(weak) and all(float(r["correct_rate"]) <= 0.35 for r in weak)
    strong_ok_count = sum(1 for r in strong if float(r["correct_rate"]) >= 0.55)
    strong_ok = strong_ok_count >= 3
    check(
        "S1_topics",
        weak_ok and strong_ok,
        f"weak={[ (r['topic'], round(float(r['correct_rate']),2)) for r in weak ]} "
        f"strong={[ (r['topic'], round(float(r['correct_rate']),2)) for r in strong ]} "
        f"strong_ok_count={strong_ok_count}",
    )

    # S4 Visual Arts years
    art_years = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT t.academic_year_id)::int
        FROM transcript_entries t
        JOIN courses c ON c.id = t.course_id
        WHERE c.program_id = $1
        """,
        PROGRAMS["art"],
    )
    check("S4_art_years", art_years == 2, f"years={art_years}")

    # Forecast preconditions: programs except art have >=3 years
    year_rows = await conn.fetch(
        """
        SELECT c.program_id, COUNT(DISTINCT t.academic_year_id)::int AS years
        FROM transcript_entries t
        JOIN courses c ON c.id = t.course_id
        GROUP BY c.program_id
        """
    )
    year_map = {r["program_id"]: r["years"] for r in year_rows}
    bad = [
        (pid, n)
        for pid, n in year_map.items()
        if pid != PROGRAMS["art"] and n < 3
    ]
    check(
        "forecast_years",
        not bad and year_map.get(PROGRAMS["art"], 0) == 2,
        f"art={year_map.get(PROGRAMS['art'])} bad={bad}",
    )

    # S5 pass near 68%
    s5 = await conn.fetchrow(
        """
        SELECT COUNT(*) FILTER (WHERE a.score IS NOT NULL)::float AS scored,
               COUNT(*) FILTER (WHERE a.score >= 60)::float AS passed
        FROM exam_attempts a
        JOIN exams x ON x.id = a.exam_id
        JOIN course_offerings o ON o.id = x.offering_id
        WHERE o.course_id = $1 AND a.is_synthetic
        """,
        S5_COURSE_ID,
    )
    s5_rate = (s5["passed"] / s5["scored"]) if s5 and s5["scored"] else 0
    check(
        "S5_pass_rate",
        abs(s5_rate - S5_PASS) <= 0.08,
        f"pass_rate={s5_rate:.3f} target={S5_PASS}",
    )

    # S6 flag type coverage
    types = await conn.fetch(
        "SELECT flag_type::text AS t, COUNT(*)::int AS n FROM integrity_flags GROUP BY 1"
    )
    type_names = {r["t"] for r in types}
    total = sum(r["n"] for r in types)
    needed = {
        "multiple_attempts",
        "fast_submission",
        "late_start",
        "shared_ip",
        "similar_answers",
    }
    check(
        "S6_flag_types",
        needed.issubset(type_names) and 40 <= total <= 80,
        f"types={sorted(type_names)} total={total}",
    )

    # Engineering decline on dedicated demosb trend course
    eng = await conn.fetch(
        """
        SELECT t.academic_year_id AS y,
               AVG(CASE WHEN t.average >= 60 THEN 1.0 ELSE 0.0 END) AS pass_rate
        FROM transcript_entries t
        WHERE t.course_id = $1 AND t.is_synthetic
        GROUP BY t.academic_year_id
        ORDER BY t.academic_year_id
        """,
        "demosb-crs-eng-trend",
    )
    rates = [float(r["pass_rate"]) for r in eng]
    check(
        "S2_eng_decline",
        len(rates) >= 3 and rates[0] >= rates[1] >= rates[2] - 0.02,
        f"rates={[(r['y'], round(float(r['pass_rate']),3)) for r in eng]}",
    )

    # AIM303 course exists under CS
    prog = await conn.fetchval(
        "SELECT program_id FROM courses WHERE id = $1", AIM303_COURSE_ID
    )
    check("S1_program", prog == PROGRAMS["cs"], f"program_id={prog}")

    return results
