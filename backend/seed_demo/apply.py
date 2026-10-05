"""Apply / reset storyboard rows. Uses admin connection (bypasses RLS)."""

from __future__ import annotations

from typing import Any

from seed_demo.constants import AIM303_EXAM_2025, OWNED_PREFIX, PROGRAMS
from seed_demo.grades import owned_id, letter_for, rng, scores_for_pass_rate
from seed_demo.plan import Plan


async def real_checksums(conn) -> dict[str, str]:
    """Checksum is_synthetic=false rows; must be unchanged after apply."""
    out: dict[str, str] = {}
    tables = [
        "exams",
        "questions",
        "exam_attempts",
        "attempt_answers",
        "integrity_flags",
        "transcript_entries",
    ]
    for table in tables:
        row = await conn.fetchrow(
            f"""
            SELECT COUNT(*)::text AS n,
                   COALESCE(md5(string_agg(id::text, ',' ORDER BY id::text)), 'empty') AS h
            FROM {table}
            WHERE is_synthetic = false
            """
            if table != "attempt_answers"
            else """
            SELECT COUNT(*)::text AS n,
                   COALESCE(
                     md5(string_agg(attempt_id || ':' || question_id, ',' ORDER BY attempt_id, question_id)),
                     'empty'
                   ) AS h
            FROM attempt_answers
            WHERE is_synthetic = false
            """
        )
        out[table] = f"{row['n']}:{row['h']}"
    return out


async def reset_owned(conn) -> dict[str, int]:
    """Delete demosb- owned rows and rebuildable AIM303 synthetic children."""
    deleted: dict[str, int] = {}

    async def _del(sql: str, *args) -> int:
        status = await conn.execute(sql, *args)
        # status like "DELETE 12"
        try:
            return int(status.split()[-1])
        except Exception:
            return 0

    # Children of owned / rebuilt exams first.
    deleted["attempt_answers"] = await _del(
        """
        DELETE FROM attempt_answers
        WHERE is_synthetic = true
          AND (
            attempt_id LIKE $1
            OR question_id LIKE $1
            OR attempt_id IN (
              SELECT id FROM exam_attempts
              WHERE exam_id = $2 OR exam_id LIKE $1
            )
          )
        """,
        f"{OWNED_PREFIX}%",
        AIM303_EXAM_2025,
    )
    deleted["integrity_flags"] = await _del(
        """
        DELETE FROM integrity_flags
        WHERE is_synthetic = true
          AND (id LIKE $1 OR attempt_id LIKE $1
               OR attempt_id IN (
                 SELECT id FROM exam_attempts
                 WHERE exam_id = $2 OR exam_id LIKE $1
               ))
        """,
        f"{OWNED_PREFIX}%",
        AIM303_EXAM_2025,
    )
    deleted["exam_attempts"] = await _del(
        """
        DELETE FROM exam_attempts
        WHERE is_synthetic = true
          AND (id LIKE $1 OR exam_id = $2 OR exam_id LIKE $1)
        """,
        f"{OWNED_PREFIX}%",
        AIM303_EXAM_2025,
    )
    deleted["questions"] = await _del(
        """
        DELETE FROM questions
        WHERE is_synthetic = true
          AND (id LIKE $1 OR exam_id = $2 OR exam_id LIKE $1)
        """,
        f"{OWNED_PREFIX}%",
        AIM303_EXAM_2025,
    )
    deleted["exams"] = await _del(
        """
        DELETE FROM exams
        WHERE is_synthetic = true
          AND id LIKE $1
        """,
        f"{OWNED_PREFIX}%",
    )
    # Keep AIM303_EXAM_2025 row itself (will be upserted); wipe only owned exams.
    deleted["transcript_entries"] = await _del(
        "DELETE FROM transcript_entries WHERE is_synthetic = true AND id LIKE $1",
        f"{OWNED_PREFIX}%",
    )
    deleted["enrollments"] = await _del(
        "DELETE FROM enrollments WHERE id LIKE $1",
        f"{OWNED_PREFIX}%",
    )
    deleted["course_sections"] = await _del(
        "DELETE FROM course_sections WHERE id LIKE $1",
        f"{OWNED_PREFIX}%",
    )
    deleted["course_offerings"] = await _del(
        "DELETE FROM course_offerings WHERE id LIKE $1",
        f"{OWNED_PREFIX}%",
    )
    deleted["staff_course_assignments"] = await _del(
        """
        DELETE FROM staff_course_assignments
        WHERE staff_person_id LIKE $1 OR course_id LIKE $1
        """,
        f"{OWNED_PREFIX}%",
    )
    deleted["user_accounts"] = await _del(
        "DELETE FROM user_accounts WHERE id LIKE $1",
        f"{OWNED_PREFIX}%",
    )
    deleted["staff"] = await _del(
        "DELETE FROM staff WHERE person_id LIKE $1",
        f"{OWNED_PREFIX}%",
    )
    deleted["people"] = await _del(
        "DELETE FROM people WHERE id LIKE $1",
        f"{OWNED_PREFIX}%",
    )
    deleted["courses"] = await _del(
        "DELETE FROM courses WHERE id LIKE $1",
        f"{OWNED_PREFIX}%",
    )
    deleted["policy_documents"] = await _del(
        "DELETE FROM policy_documents WHERE id LIKE $1 OR is_synthetic = true",
        f"{OWNED_PREFIX}%",
    )
    return deleted


async def _complete_thin_programs(conn, plan: Plan) -> None:
    for note in list(plan.notes):
        if not note.startswith("thin-program:"):
            continue
        _, prog_key, prog_id, cid = note.split(":", 3)
        students = await conn.fetch(
            """
            SELECT id FROM students
            WHERE program_id = $1 AND status = 'active'
            ORDER BY id LIMIT 30
            """,
            prog_id,
        )
        for year, rate in (("2023/24", 0.74), ("2024/25", 0.72), ("2025/26", 0.71)):
            r = rng(f"thin-{prog_key}-{year}")
            scores = scores_for_pass_rate(r, len(students), rate)
            for i, st in enumerate(students):
                plan.transcripts.append(
                    {
                        "id": owned_id("tr", "thin", prog_key, year, st["id"]),
                        "student_id": st["id"],
                        "course_id": cid,
                        "academic_year_id": year,
                        "average": scores[i],
                        "letter_grade": letter_for(scores[i]),
                        "credits": 3,
                        "is_synthetic": True,
                    }
                )


async def apply_plan(conn, plan: Plan, *, password_hash: str | None) -> dict[str, int]:
    await _complete_thin_programs(conn, plan)
    await reset_owned(conn)
    written: dict[str, int] = {k: 0 for k in plan.counts()}

    async def many(sql: str, rows: list[dict], keys: list[str]) -> int:
        if not rows:
            return 0
        await conn.executemany(sql, [tuple(r[k] for k in keys) for r in rows])
        return len(rows)

    written["people"] = await many(
        """
        INSERT INTO people (id, full_name, email)
        VALUES ($1, $2, $3)
        ON CONFLICT (id) DO UPDATE SET full_name = EXCLUDED.full_name, email = EXCLUDED.email
        """,
        plan.people,
        ["id", "full_name", "email"],
    )
    written["staff"] = await many(
        """
        INSERT INTO staff (person_id, title, org_unit_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (person_id) DO UPDATE
          SET title = EXCLUDED.title, org_unit_id = EXCLUDED.org_unit_id
        """,
        plan.staff,
        ["person_id", "title", "org_unit_id"],
    )
    written["courses"] = await many(
        """
        INSERT INTO courses (id, program_id, code, name, credits, year_level)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, credits = EXCLUDED.credits
        """,
        plan.courses,
        ["id", "program_id", "code", "name", "credits", "year_level"],
    )
    written["course_offerings"] = await many(
        """
        INSERT INTO course_offerings (id, course_id, academic_year_id, term_id, instructor_id)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO UPDATE SET instructor_id = EXCLUDED.instructor_id
        """,
        plan.offerings,
        ["id", "course_id", "academic_year_id", "term_id", "instructor_id"],
    )
    written["course_sections"] = await many(
        """
        INSERT INTO course_sections (id, offering_id, code)
        VALUES ($1, $2, $3)
        ON CONFLICT (id) DO NOTHING
        """,
        plan.sections,
        ["id", "offering_id", "code"],
    )
    # Enrollments: unique (student, offering) — delete conflicts for demosb first already.
    # Existing non-demosb enrollments on AIM303 may conflict; remove only synthetic
    # enrollments we replace by deleting demosb, and also clear tiny existing AIM303
    # enrollments if they block (4 rows) — those have no is_synthetic; do NOT delete
    # unless id is demosb. For students already enrolled, skip insert.
    existing = {
        (r["student_id"], r["offering_id"])
        for r in await conn.fetch(
            "SELECT student_id, offering_id FROM enrollments"
        )
    }
    new_enr = [
        e
        for e in plan.enrollments
        if (e["student_id"], e["offering_id"]) not in existing
    ]
    # Remap attempts that referenced skipped enrollments to existing enrollment ids.
    enr_lookup = {
        (r["student_id"], r["offering_id"]): r["id"]
        for r in await conn.fetch(
            "SELECT id, student_id, offering_id FROM enrollments"
        )
    }
    for e in new_enr:
        enr_lookup[(e["student_id"], e["offering_id"])] = e["id"]
    written["enrollments"] = await many(
        """
        INSERT INTO enrollments (id, student_id, offering_id, section_id)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (id) DO NOTHING
        """,
        new_enr,
        ["id", "student_id", "offering_id", "section_id"],
    )

    # Fix attempt enrollment_ids to whatever is actually in DB for that student/offering.
    exam_offering = {e["id"]: e["offering_id"] for e in plan.exams}
    # Also map existing AIM303 exam offering
    for e in plan.exams:
        exam_offering[e["id"]] = e["offering_id"]
    fixed_attempts = []
    for a in plan.attempts:
        off = exam_offering.get(a["exam_id"])
        key = (a["student_id"], off)
        real_enr = enr_lookup.get(key)
        if not real_enr:
            continue
        a = dict(a)
        a["enrollment_id"] = real_enr
        fixed_attempts.append(a)
    plan.attempts = fixed_attempts
    answer_attempt_ids = {a["id"] for a in plan.attempts}
    plan.answers = [x for x in plan.answers if x["attempt_id"] in answer_attempt_ids]
    plan.flags = [x for x in plan.flags if x["attempt_id"] in answer_attempt_ids]

    for row in plan.staff_assignments:
        await conn.execute(
            """
            INSERT INTO staff_course_assignments (staff_person_id, course_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            row["staff_person_id"],
            row["course_id"],
        )
    written["staff_course_assignments"] = len(plan.staff_assignments)

    # Upsert AIM303 exam row
    written["exams"] = await many(
        """
        INSERT INTO exams (
          id, offering_id, title, scheduled_at, duration_minutes,
          question_count, pass_mark, status, is_synthetic
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (id) DO UPDATE SET
          title = EXCLUDED.title,
          question_count = EXCLUDED.question_count,
          is_synthetic = true
        """,
        plan.exams,
        [
            "id",
            "offering_id",
            "title",
            "scheduled_at",
            "duration_minutes",
            "question_count",
            "pass_mark",
            "status",
            "is_synthetic",
        ],
    )
    written["questions"] = await many(
        """
        INSERT INTO questions (id, exam_id, number, topic, prompt, max_score, is_synthetic)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT (id) DO UPDATE SET topic = EXCLUDED.topic, prompt = EXCLUDED.prompt
        """,
        plan.questions,
        ["id", "exam_id", "number", "topic", "prompt", "max_score", "is_synthetic"],
    )
    written["exam_attempts"] = await many(
        """
        INSERT INTO exam_attempts (
          id, exam_id, student_id, enrollment_id, score, time_taken_min,
          started_at, ended_at, ip, device, attempt_count, late_start, status, is_synthetic
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::inet,$10,$11,$12,$13,$14)
        ON CONFLICT (id) DO UPDATE SET score = EXCLUDED.score, is_synthetic = true
        """,
        plan.attempts,
        [
            "id",
            "exam_id",
            "student_id",
            "enrollment_id",
            "score",
            "time_taken_min",
            "started_at",
            "ended_at",
            "ip",
            "device",
            "attempt_count",
            "late_start",
            "status",
            "is_synthetic",
        ],
    )
    written["attempt_answers"] = await many(
        """
        INSERT INTO attempt_answers (attempt_id, question_id, is_correct, points, is_synthetic)
        VALUES ($1,$2,$3,$4,$5)
        ON CONFLICT (attempt_id, question_id) DO UPDATE
          SET is_correct = EXCLUDED.is_correct, points = EXCLUDED.points
        """,
        plan.answers,
        ["attempt_id", "question_id", "is_correct", "points", "is_synthetic"],
    )
    written["integrity_flags"] = await many(
        """
        INSERT INTO integrity_flags (id, attempt_id, flag_type, detail, is_synthetic)
        VALUES ($1,$2,$3::integrity_flag_type,$4,$5)
        ON CONFLICT (id) DO NOTHING
        """,
        plan.flags,
        ["id", "attempt_id", "flag_type", "detail", "is_synthetic"],
    )
    # Transcripts: skip any existing (student, course, year) — including prior
    # synthetic rows we do not own — so we never touch real or foreign keys.
    # Also dedupe within the plan (S2/S3/S6 can target the same triple).
    existing_tr_keys = {
        (r["student_id"], r["course_id"], r["academic_year_id"])
        for r in await conn.fetch(
            """
            SELECT student_id, course_id, academic_year_id
            FROM transcript_entries
            """
        )
    }
    deduped: dict[tuple, dict] = {}
    for t in plan.transcripts:
        key = (t["student_id"], t["course_id"], t["academic_year_id"])
        if key in existing_tr_keys:
            continue
        deduped[key] = t
    syn_transcripts = list(deduped.values())
    written["transcript_entries"] = await many(
        """
        INSERT INTO transcript_entries (
          id, student_id, course_id, academic_year_id, average, letter_grade, credits, is_synthetic
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (id) DO UPDATE SET average = EXCLUDED.average, letter_grade = EXCLUDED.letter_grade
        """,
        syn_transcripts,
        [
            "id",
            "student_id",
            "course_id",
            "academic_year_id",
            "average",
            "letter_grade",
            "credits",
            "is_synthetic",
        ],
    )

    for acct in plan.accounts:
        await conn.execute(
            """
            INSERT INTO user_accounts (
              id, person_id, role, scope_id, student_id, password_hash, is_demo, is_active
            ) VALUES ($1,$2,$3::app_role,$4,$5,$6,$7,$8)
            ON CONFLICT (id) DO UPDATE SET
              scope_id = EXCLUDED.scope_id,
              password_hash = COALESCE(EXCLUDED.password_hash, user_accounts.password_hash),
              is_demo = true,
              is_active = true
            """,
            acct["id"],
            acct["person_id"],
            acct["role"],
            acct["scope_id"],
            acct["student_id"],
            password_hash,
            True,
            True,
        )
    written["user_accounts"] = len(plan.accounts)

    if plan.policies:
        from datetime import date as date_cls

        policy_rows = []
        for p in plan.policies:
            row = dict(p)
            ed = row.get("effective_date")
            if isinstance(ed, str):
                row["effective_date"] = date_cls.fromisoformat(ed)
            policy_rows.append(row)
        written["policy_documents"] = await many(
            """
            INSERT INTO policy_documents (id, title, language, body, effective_date, is_synthetic)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (id) DO UPDATE SET body = EXCLUDED.body, title = EXCLUDED.title
            """,
            policy_rows,
            ["id", "title", "language", "body", "effective_date", "is_synthetic"],
        )

    # Ensure existing demo accounts keep password if provided.
    if password_hash:
        await conn.execute(
            """
            UPDATE user_accounts
            SET password_hash = $1
            WHERE is_demo = true AND (password_hash IS NULL OR password_hash = '')
            """,
            password_hash,
        )

    return written
