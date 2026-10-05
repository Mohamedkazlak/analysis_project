"""Build the in-memory storyboard plan from live DB context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from seed_demo.constants import (
    AIM303_COURSE_ID,
    AIM303_EXAM_2025,
    AIM303_OFFERING_2025,
    AIM303_SECTION_A,
    AIM303_SECTION_B,
    PROGRAMS,
    S1_PASS_2023,
    S1_PASS_2024,
    S1_PASS_2025,
    S1_SECTION_GAP,
    S1_STRONG_TOPIC_RATE,
    S1_WEAK_TOPIC_RATE,
    S2_ENG_PASS,
    S3_CS_PASS,
    S5_COURSE_CODE,
    S5_COURSE_ID,
    S5_PASS,
    TERMS,
    YEARS,
)
from seed_demo.grades import (
    letter_for,
    owned_id,
    rng,
    scores_for_pass_rate,
    shift_scores,
)


WEAK_TOPICS = ("Use Cases", "Sequence Diagrams")
STRONG_TOPICS = ("Requirements", "Architecture", "Data Modeling", "UI Flows")


@dataclass
class Plan:
    people: list[dict] = field(default_factory=list)
    staff: list[dict] = field(default_factory=list)
    courses: list[dict] = field(default_factory=list)
    offerings: list[dict] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    enrollments: list[dict] = field(default_factory=list)
    staff_assignments: list[dict] = field(default_factory=list)
    exams: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)
    answers: list[dict] = field(default_factory=list)
    flags: list[dict] = field(default_factory=list)
    transcripts: list[dict] = field(default_factory=list)
    accounts: list[dict] = field(default_factory=list)
    policies: list[dict] = field(default_factory=list)
    # Existing rows the seeder may safely replace (is_synthetic children).
    delete_exam_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "people": len(self.people),
            "staff": len(self.staff),
            "courses": len(self.courses),
            "course_offerings": len(self.offerings),
            "course_sections": len(self.sections),
            "enrollments": len(self.enrollments),
            "staff_course_assignments": len(self.staff_assignments),
            "exams": len(self.exams),
            "questions": len(self.questions),
            "exam_attempts": len(self.attempts),
            "attempt_answers": len(self.answers),
            "integrity_flags": len(self.flags),
            "transcript_entries": len(self.transcripts),
            "user_accounts": len(self.accounts),
            "policy_documents": len(self.policies),
        }


async def load_context(conn) -> dict[str, Any]:
    cs_students = await conn.fetch(
        """
        SELECT id, person_id, section, cohort_year
        FROM students
        WHERE program_id = $1 AND status = 'active'
        ORDER BY id
        """,
        PROGRAMS["cs"],
    )
    eng_students = await conn.fetch(
        """
        SELECT id, person_id, section, cohort_year
        FROM students
        WHERE program_id = $1 AND status = 'active'
        ORDER BY id
        """,
        PROGRAMS["eng"],
    )
    vet_students = await conn.fetch(
        """
        SELECT id, person_id, section, cohort_year
        FROM students
        WHERE program_id = $1 AND status = 'active'
        ORDER BY id
        """,
        PROGRAMS["vet"],
    )
    art_students = await conn.fetch(
        """
        SELECT id, person_id, section, cohort_year
        FROM students
        WHERE program_id = $1 AND status = 'active'
        ORDER BY id
        """,
        PROGRAMS["art"],
    )
    eng_courses = await conn.fetch(
        """
        SELECT id, code, credits FROM courses
        WHERE program_id = $1 ORDER BY code
        """,
        PROGRAMS["eng"],
    )
    cs_courses = await conn.fetch(
        """
        SELECT id, code, credits FROM courses
        WHERE program_id = $1 ORDER BY code
        """,
        PROGRAMS["cs"],
    )
    existing_flags = await conn.fetchval(
        "SELECT COUNT(*)::int FROM integrity_flags"
    )
    aim_enrollments = await conn.fetch(
        """
        SELECT e.id, e.student_id, e.section_id
        FROM enrollments e
        WHERE e.offering_id = $1
        ORDER BY e.student_id
        """,
        AIM303_OFFERING_2025,
    )
    return {
        "cs_students": [dict(r) for r in cs_students],
        "eng_students": [dict(r) for r in eng_students],
        "vet_students": [dict(r) for r in vet_students],
        "art_students": [dict(r) for r in art_students],
        "eng_courses": [dict(r) for r in eng_courses],
        "cs_courses": [dict(r) for r in cs_courses],
        "existing_flags": int(existing_flags or 0),
        "aim_enrollments": [dict(r) for r in aim_enrollments],
    }


def _scheduled(year: str) -> datetime:
    # Fall 2025 / spring terms — fixed timestamps for determinism.
    if year == "2025/26":
        return datetime(2025, 12, 10, 9, 0, tzinfo=timezone.utc)
    if year == "2024/25":
        return datetime(2025, 5, 12, 9, 0, tzinfo=timezone.utc)
    return datetime(2024, 5, 13, 9, 0, tzinfo=timezone.utc)


def _add_exam_bundle(
    plan: Plan,
    *,
    exam_id: str,
    offering_id: str,
    title: str,
    year: str,
    students: list[dict],
    enrollments_by_student: dict[str, dict],
    pass_rate: float,
    section_gap: float | None,
    weak_topics: bool,
    stream: str,
    plant_integrity_cluster: bool = False,
) -> None:
    r = rng(stream)
    n_q = 10
    topics: list[str] = []
    for i in range(n_q):
        if weak_topics and i < 4:
            topics.append(WEAK_TOPICS[i % 2])
        else:
            topics.append(STRONG_TOPICS[i % len(STRONG_TOPICS)])

    plan.exams.append(
        {
            "id": exam_id,
            "offering_id": offering_id,
            "title": title,
            "scheduled_at": _scheduled(year),
            "duration_minutes": 90,
            "question_count": n_q,
            "pass_mark": 60,
            "status": "closed",
            "is_synthetic": True,
        }
    )
    q_ids = []
    for i, topic in enumerate(topics, start=1):
        qid = owned_id("q", exam_id, i) if not exam_id.startswith("syn-") else f"{exam_id}-q{i}"
        # Prefer owned ids for reset; for rebuilt AIM303 syn exam use owned question ids.
        qid = owned_id("q", exam_id.replace("syn-exam-", ""), i)
        q_ids.append(qid)
        plan.questions.append(
            {
                "id": qid,
                "exam_id": exam_id,
                "number": i,
                "topic": topic,
                "prompt": f"Item {i} on {topic}",
                "max_score": 10.0,
                "is_synthetic": True,
            }
        )

    sid_list = [s["id"] for s in students if s["id"] in enrollments_by_student]
    if not sid_list:
        return
    base = scores_for_pass_rate(r, len(sid_list), pass_rate)
    if section_gap is not None and len(sid_list) >= 4:
        mid = len(sid_list) // 2
        # Section A higher, section B lower by ~section_gap.
        for i in range(mid):
            base[i] = round(min(100.0, base[i] + section_gap / 2), 1)
        for i in range(mid, len(sid_list)):
            base[i] = round(max(0.0, base[i] - section_gap / 2), 1)

    cluster_ids = sid_list[:6] if plant_integrity_cluster else []
    for idx, sid in enumerate(sid_list):
        enr = enrollments_by_student[sid]
        score = base[idx]
        att_id = owned_id("att", exam_id.replace("/", "-"), sid)
        late = r.random() < 0.05
        time_taken = 12 if (plant_integrity_cluster and sid in cluster_ids) else int(40 + r.random() * 40)
        ip = "10.50.1.9" if (plant_integrity_cluster and sid in cluster_ids) else f"10.20.{r.randint(1,40)}.{r.randint(1,250)}"
        started = _scheduled(year)
        ended = started.replace(minute=started.minute)  # placeholder; set below via offset
        from datetime import timedelta

        ended = started + timedelta(minutes=time_taken)
        plan.attempts.append(
            {
                "id": att_id,
                "exam_id": exam_id,
                "student_id": sid,
                "enrollment_id": enr["id"],
                "score": score,
                "time_taken_min": time_taken,
                "started_at": started,
                "ended_at": ended,
                "ip": ip,
                "device": "demo-chrome",
                "attempt_count": 2 if (plant_integrity_cluster and sid in cluster_ids[:2]) else 1,
                "late_start": late,
                "status": "submitted",
                "is_synthetic": True,
            }
        )
        # Answers aligned with score: points sum ≈ score.
        points_left = score
        for qi, qid in enumerate(q_ids):
            topic = topics[qi]
            if weak_topics and topic in WEAK_TOPICS:
                p_correct = S1_WEAK_TOPIC_RATE
            elif weak_topics:
                p_correct = S1_STRONG_TOPIC_RATE
            else:
                p_correct = 0.55 + (score - 50) / 200
            correct = r.random() < p_correct
            pts = 10.0 if correct else 0.0
            # Last question absorbs residual to match attempt score within tolerance.
            if qi == len(q_ids) - 1:
                pts = round(max(0.0, min(10.0, points_left)), 1)
                correct = pts >= 5.0
            else:
                points_left -= pts
            plan.answers.append(
                {
                    "attempt_id": att_id,
                    "question_id": qid,
                    "is_correct": correct,
                    "points": pts,
                    "is_synthetic": True,
                }
            )
        if plant_integrity_cluster and sid in cluster_ids:
            for ftype in ("shared_ip", "fast_submission", "similar_answers"):
                plan.flags.append(
                    {
                        "id": owned_id("flg", att_id, ftype),
                        "attempt_id": att_id,
                        "flag_type": ftype,
                        "detail": f"Storyboard cluster {ftype}",
                        "is_synthetic": True,
                    }
                )


def build_plan(ctx: dict[str, Any], policies: list[dict]) -> Plan:
    plan = Plan()
    plan.policies = policies
    plan.delete_exam_ids = [AIM303_EXAM_2025]

    # --- Professors for AIM303 sections (S7) ---
    prof_a = {
        "id": "p-tomas-oyelaran",  # existing CS professor
        "existing": True,
    }
    prof_b_person = {
        "id": owned_id("person", "prof-aim303-b"),
        "full_name": "Mona Farid",
        "email": "mona.farid@demo.bnu.edu.eg",
    }
    plan.people.append(prof_b_person)
    plan.staff.append(
        {
            "person_id": prof_b_person["id"],
            "title": "Lecturer, Computer Science",
            "org_unit_id": PROGRAMS["cs"],
        }
    )
    plan.accounts.append(
        {
            "id": owned_id("acct", "prof-aim303-b"),
            "person_id": prof_b_person["id"],
            "role": "professor",
            "scope_id": PROGRAMS["cs"],
            "student_id": None,
            "is_demo": True,
            "is_active": True,
        }
    )
    plan.staff_assignments.append(
        {"staff_person_id": prof_a["id"], "course_id": AIM303_COURSE_ID}
    )
    plan.staff_assignments.append(
        {"staff_person_id": prof_b_person["id"], "course_id": AIM303_COURSE_ID}
    )
    # Engineering PD already exists (u-pd-eng). Expand eng assignments.
    for course in ctx["eng_courses"][:3]:
        plan.staff_assignments.append(
            {"staff_person_id": "p-hana-elmasry", "course_id": course["id"]}
        )

    # Declining student account (S7) — pick a CS student with synthetic history.
    demo_student = ctx["cs_students"][0]
    plan.accounts.append(
        {
            "id": owned_id("acct", "student-decline"),
            "person_id": demo_student["person_id"],
            "role": "student",
            "scope_id": PROGRAMS["cs"],
            "student_id": demo_student["id"],
            "is_demo": True,
            "is_active": True,
        }
    )

    # --- AIM303 offerings prior years + section B on 2025 ---
    plan.sections.append(
        {"id": AIM303_SECTION_B, "offering_id": AIM303_OFFERING_2025, "code": "B"}
    )

    cs_pool = ctx["cs_students"][:80]
    # Ensure enrollments for AIM303 2025 covering both sections.
    enroll_map_2025: dict[str, dict] = {}
    for i, st in enumerate(cs_pool):
        section_id = AIM303_SECTION_A if i < 40 else AIM303_SECTION_B
        eid = owned_id("enr", "aim303", "2025", st["id"])
        row = {
            "id": eid,
            "student_id": st["id"],
            "offering_id": AIM303_OFFERING_2025,
            "section_id": section_id,
        }
        plan.enrollments.append(row)
        enroll_map_2025[st["id"]] = row

    # Rebuild 2025 AIM303 exam (S1)
    _add_exam_bundle(
        plan,
        exam_id=AIM303_EXAM_2025,
        offering_id=AIM303_OFFERING_2025,
        title="AIM303 Systems Analysis Final",
        year="2025/26",
        students=cs_pool,
        enrollments_by_student=enroll_map_2025,
        pass_rate=S1_PASS_2025,
        section_gap=S1_SECTION_GAP,
        weak_topics=True,
        stream="s1-2025",
        plant_integrity_cluster=True,
    )

    # Prior year AIM303 offerings/exams
    for year, rate in (("2023/24", S1_PASS_2023), ("2024/25", S1_PASS_2024)):
        off_id = owned_id("off", "aim303", year)
        plan.offerings.append(
            {
                "id": off_id,
                "course_id": AIM303_COURSE_ID,
                "academic_year_id": year,
                "term_id": TERMS[year],
                "instructor_id": prof_a["id"],
            }
        )
        sec_id = owned_id("sec", "aim303", year, "A")
        plan.sections.append({"id": sec_id, "offering_id": off_id, "code": "A"})
        emap: dict[str, dict] = {}
        # Cohort plausibility: earlier years use older cohort_year students first.
        pool = [s for s in cs_pool if int(s.get("cohort_year") or 2023) <= int(year[:4]) + 1]
        if len(pool) < 40:
            pool = cs_pool[:60]
        else:
            pool = pool[:60]
        for st in pool:
            eid = owned_id("enr", "aim303", year, st["id"])
            row = {
                "id": eid,
                "student_id": st["id"],
                "offering_id": off_id,
                "section_id": sec_id,
            }
            plan.enrollments.append(row)
            emap[st["id"]] = row
        exam_id = owned_id("exam", "aim303", year)
        _add_exam_bundle(
            plan,
            exam_id=exam_id,
            offering_id=off_id,
            title=f"AIM303 Final {year}",
            year=year,
            students=pool,
            enrollments_by_student=emap,
            pass_rate=rate,
            section_gap=None,
            weak_topics=True,
            stream=f"s1-{year}",
        )
        # Transcript history for AIM303
        for st in pool:
            avg = next(
                (a["score"] for a in plan.attempts if a["exam_id"] == exam_id and a["student_id"] == st["id"]),
                60.0,
            )
            plan.transcripts.append(
                {
                    "id": owned_id("tr", "aim303", year, st["id"]),
                    "student_id": st["id"],
                    "course_id": AIM303_COURSE_ID,
                    "academic_year_id": year,
                    "average": avg,
                    "letter_grade": letter_for(avg),
                    "credits": 3,
                    "is_synthetic": True,
                }
            )

    # Also plant 2025 AIM303 transcripts for enrolled students (synthetic).
    for st in cs_pool:
        avg = next(
            (
                a["score"]
                for a in plan.attempts
                if a["exam_id"] == AIM303_EXAM_2025 and a["student_id"] == st["id"]
            ),
            None,
        )
        if avg is None:
            continue
        plan.transcripts.append(
            {
                "id": owned_id("tr", "aim303", "2025-26", st["id"]),
                "student_id": st["id"],
                "course_id": AIM303_COURSE_ID,
                "academic_year_id": "2025/26",
                "average": avg,
                "letter_grade": letter_for(avg),
                "credits": 3,
                "is_synthetic": True,
            }
        )

    # --- S2 Engineering program yearly transcripts on a dedicated demosb course
    # so existing synthetic Eng rows and S6 YoY do not distort the trend.
    eng_trend_course = {
        "id": owned_id("crs", "eng", "trend"),
        "program_id": PROGRAMS["eng"],
        "code": "ENG 298",
        "name": "Engineering Design Studio",
        "credits": 3,
        "year_level": 3,
    }
    plan.courses.append(eng_trend_course)
    eng_students = ctx["eng_students"][:80]
    for year, rate in S2_ENG_PASS.items():
        r = rng(f"s2-{year}")
        scores = scores_for_pass_rate(r, len(eng_students), rate)
        for i, st in enumerate(eng_students):
            avg = scores[i]
            plan.transcripts.append(
                {
                    "id": owned_id("tr", "engtrend", year, st["id"]),
                    "student_id": st["id"],
                    "course_id": eng_trend_course["id"],
                    "academic_year_id": year,
                    "average": avg,
                    "letter_grade": letter_for(avg),
                    "credits": 3,
                    "is_synthetic": True,
                }
            )

    # Keep a handle for S6 dedicated YoY course (separate from S2 trend).
    eng_courses = ctx["eng_courses"][:4]
    # --- S3 CS improving history (earlier years only, other courses) ---
    other_cs = [c for c in ctx["cs_courses"] if c["id"] != AIM303_COURSE_ID][:3]
    for year, rate in S3_CS_PASS.items():
        r = rng(f"s3-{year}")
        pool = ctx["cs_students"][:100]
        scores = scores_for_pass_rate(r, len(pool), rate)
        for course in other_cs:
            for i, st in enumerate(pool):
                avg = scores[i]
                plan.transcripts.append(
                    {
                        "id": owned_id("tr", "cs", course["id"], year, st["id"]),
                        "student_id": st["id"],
                        "course_id": course["id"],
                        "academic_year_id": year,
                        "average": avg,
                        "letter_grade": letter_for(avg),
                        "credits": int(course.get("credits") or 3),
                        "is_synthetic": True,
                    }
                )

    # Declining student: two courses trending down across years.
    decline_courses = other_cs[:2] if len(other_cs) >= 2 else other_cs
    for j, course in enumerate(decline_courses):
        for year, avg in (("2023/24", 78.0 - j), ("2024/25", 68.0 - j), ("2025/26", 55.0 - j)):
            plan.transcripts.append(
                {
                    "id": owned_id("tr", "decline", course["id"], year, demo_student["id"]),
                    "student_id": demo_student["id"],
                    "course_id": course["id"],
                    "academic_year_id": year,
                    "average": avg,
                    "letter_grade": letter_for(avg),
                    "credits": int(course.get("credits") or 3),
                    "is_synthetic": True,
                }
            )

    # --- S4 Visual Arts: only 2 years ---
    art_course_id = owned_id("crs", "art", "studio")
    plan.courses.append(
        {
            "id": art_course_id,
            "program_id": PROGRAMS["art"],
            "code": "ART 220",
            "name": "Studio Practice II",
            "credits": 3,
            "year_level": 2,
        }
    )
    art_students = ctx["art_students"][:40]
    for year, rate in (("2024/25", 0.74), ("2025/26", 0.71)):
        r = rng(f"s4-{year}")
        scores = scores_for_pass_rate(r, len(art_students), rate)
        for i, st in enumerate(art_students):
            plan.transcripts.append(
                {
                    "id": owned_id("tr", "art", year, st["id"]),
                    "student_id": st["id"],
                    "course_id": art_course_id,
                    "academic_year_id": year,
                    "average": scores[i],
                    "letter_grade": letter_for(scores[i]),
                    "credits": 3,
                    "is_synthetic": True,
                }
            )

    # Thin history for remaining programs (3 years) except art.
    for prog_key, prog_id in PROGRAMS.items():
        if prog_key in ("cs", "eng", "art", "vet"):
            continue
        r = rng(f"thin-{prog_key}")
        # Use one owned course per program for yearly averages.
        cid = owned_id("crs", prog_key, "core")
        plan.courses.append(
            {
                "id": cid,
                "program_id": prog_id,
                "code": f"{prog_key.upper()[:3]} 100",
                "name": f"{prog_key} Core Topics",
                "credits": 3,
                "year_level": 1,
            }
        )
        # Pull up to 30 students in that program from DB via a lightweight query placeholder:
        # build_plan only has eng/cs/vet/art — fetch remaining at apply time.
        plan.notes.append(f"thin-program:{prog_key}:{prog_id}:{cid}")

    # --- S5 Vet synthetic course near 68% ---
    plan.courses.append(
        {
            "id": S5_COURSE_ID,
            "program_id": PROGRAMS["vet"],
            "code": S5_COURSE_CODE,
            "name": "Clinical Physiology Review",
            "credits": 2,
            "year_level": 2,
        }
    )
    off5 = owned_id("off", "s5", "2025")
    plan.offerings.append(
        {
            "id": off5,
            "course_id": S5_COURSE_ID,
            "academic_year_id": "2025/26",
            "term_id": TERMS["2025/26"],
            "instructor_id": "p-nabil-youssef",
        }
    )
    sec5 = owned_id("sec", "s5", "A")
    plan.sections.append({"id": sec5, "offering_id": off5, "code": "A"})
    vet_pool = ctx["vet_students"][:60]
    emap5: dict[str, dict] = {}
    for st in vet_pool:
        eid = owned_id("enr", "s5", st["id"])
        row = {
            "id": eid,
            "student_id": st["id"],
            "offering_id": off5,
            "section_id": sec5,
        }
        plan.enrollments.append(row)
        emap5[st["id"]] = row
    exam5 = owned_id("exam", "s5", "2025")
    _add_exam_bundle(
        plan,
        exam_id=exam5,
        offering_id=off5,
        title="210VTM Final",
        year="2025/26",
        students=vet_pool,
        enrollments_by_student=emap5,
        pass_rate=S5_PASS,
        section_gap=None,
        weak_topics=False,
        stream="s5-2025",
    )
    # Vet needs ≥3 yearly averages for forecast (S5 course history).
    for year, rate in (("2023/24", 0.71), ("2024/25", 0.70), ("2025/26", S5_PASS)):
        r = rng(f"vet-hist-{year}")
        scores = scores_for_pass_rate(r, len(vet_pool), rate)
        for i, st in enumerate(vet_pool):
            plan.transcripts.append(
                {
                    "id": owned_id("tr", "vet", year, st["id"]),
                    "student_id": st["id"],
                    "course_id": S5_COURSE_ID,
                    "academic_year_id": year,
                    "average": scores[i],
                    "letter_grade": letter_for(scores[i]),
                    "credits": 2,
                    "is_synthetic": True,
                }
            )

    # --- Extra integrity flags: guarantee all five types, target ~45–55 total ---
    flag_types = [
        "multiple_attempts",
        "fast_submission",
        "late_start",
        "shared_ip",
        "similar_answers",
    ]
    attempt_ids = [a["id"] for a in plan.attempts]
    r = rng("flags-extra")
    # Always plant at least 3 of each type on demosb attempts.
    for i, ftype in enumerate(flag_types * 3):
        if not attempt_ids:
            break
        att = attempt_ids[(i * 7) % len(attempt_ids)]
        plan.flags.append(
            {
                "id": owned_id("flg", "cover", ftype, i),
                "attempt_id": att,
                "flag_type": ftype,
                "detail": f"Storyboard coverage {ftype}",
                "is_synthetic": True,
            }
        )
    # Fill toward ~50 total assuming ~21 pre-existing non-demosb flags remain.
    need = max(0, 28 - 15)  # coverage already added 15; add a few more
    for i in range(need):
        if not attempt_ids:
            break
        att = attempt_ids[i % len(attempt_ids)]
        ftype = flag_types[i % len(flag_types)]
        plan.flags.append(
            {
                "id": owned_id("flg", "extra", i, ftype),
                "attempt_id": att,
                "flag_type": ftype,
                "detail": f"Storyboard extra {ftype}",
                "is_synthetic": True,
            }
        )

    # --- S6 anomalies: YoY fail jump on a dedicated demosb Eng course ---
    yoy_course = {
        "id": owned_id("crs", "eng", "yoy"),
        "program_id": PROGRAMS["eng"],
        "code": "ENG 297",
        "name": "Applied Mechanics Review",
        "credits": 3,
        "year_level": 2,
    }
    plan.courses.append(yoy_course)
    r = rng("s6-yoy")
    for year, rate in (("2024/25", 0.85), ("2025/26", 0.55)):
        pool = eng_students[:50]
        scores = scores_for_pass_rate(r, len(pool), rate)
        for i, st in enumerate(pool):
            plan.transcripts.append(
                {
                    "id": owned_id("tr", "yoy", year, st["id"]),
                    "student_id": st["id"],
                    "course_id": yoy_course["id"],
                    "academic_year_id": year,
                    "average": scores[i],
                    "letter_grade": letter_for(scores[i]),
                    "credits": 3,
                    "is_synthetic": True,
                }
            )

    # Near-0% correct question on Architecture (keep other Architecture items strong).
    aim_arch = [
        q
        for q in plan.questions
        if q["exam_id"] == AIM303_EXAM_2025 and q["topic"] == "Architecture"
    ]
    if aim_arch:
        victim = aim_arch[0]["id"]
        for ans in plan.answers:
            if ans["question_id"] == victim:
                ans["is_correct"] = False
                ans["points"] = 0.0
        plan.notes.append(f"answer-key-victim:{victim}")

    plan.notes.append("s1:AIM303 under CS")
    plan.notes.append("s2:Engineering decline + sector link via AIM303")
    plan.notes.append("s4:Visual Arts 2 years only")
    plan.notes.append(f"s5:{S5_COURSE_CODE} target ~{S5_PASS:.0%}")
    return plan
