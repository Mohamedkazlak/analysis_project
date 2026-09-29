import asyncpg

from core.utils import PASS_MARK, avg, round1
from repositories.transcript import build_profile_years
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from services.gpa import standing_from_gpa


def select_semester_attempts(attempts: list[dict]) -> list[dict]:
    """Exams in this student's current semester.

    That semester is the latest term of the current academic year they sat.
    If they sat nothing in the current year, it is the latest term they did sit.
    """
    if not attempts:
        return []
    current_year = [row for row in attempts if row.get("is_current")]
    pool = current_year or list(attempts)
    chosen = max(pool, key=lambda row: (row["start_date"], row["term_id"]))
    selected = [row for row in pool if row["term_id"] == chosen["term_id"]]
    selected.sort(
        key=lambda row: (
            row.get("scheduled_at") or row["start_date"],
            row.get("course_code") or "",
            row.get("exam_id") or "",
        )
    )
    return selected


def course_topic_rows(attempts: list[dict]) -> list[dict]:
    """One score per course: the mean of this semester's exam scores."""
    buckets: dict[str, list[float]] = {}
    names: dict[str, str] = {}
    for row in attempts:
        code = (row.get("course_code") or "").strip()
        name = (row.get("course_name") or "").strip() or code or "Course"
        key = code or name
        names[key] = name
        buckets.setdefault(key, []).append(float(row["score"]))
    topics = []
    for key, scores in buckets.items():
        mean = avg(scores)
        score = round(mean, 2) if len(scores) == 1 else round1(mean)
        topics.append({"topic": names[key], "score": score})
    topics.sort(key=lambda row: (-row["score"], row["topic"]))
    return topics


def resolve_topic_scores(
    question_topics: list[dict], course_rows: list[dict]
) -> tuple[str, list[dict]]:
    """Question topics when they actually differ; otherwise course scores.

    Synthetic questions are often one shared topic, which would make the
    strongest and weakest topic the same label. Course scores are still
    SQL facts for this semester.
    """
    distinct = {row["topic"] for row in question_topics if row.get("topic")}
    ranked_questions = sorted(
        question_topics,
        key=lambda row: (-float(row["score"]), row["topic"]),
    )
    if len(distinct) >= 2:
        return "questions", ranked_questions
    courses = course_topic_rows(course_rows)
    if courses:
        return "courses", courses
    return "questions", ranked_questions


def _chart_labels(rows: list[dict]) -> None:
    seen: dict[str, int] = {}
    for row in rows:
        base = row["courseCode"] or row["exam"]
        seen[base] = seen.get(base, 0) + 1
        row["chartLabel"] = base if seen[base] == 1 else f"{base} · {seen[base]}"


async def get_student_dashboard(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
) -> dict:
    student_id = ctx.student_id
    if filters and filters.student_id and ctx.role != "student":
        student_id = filters.student_id
    student = await db.fetchrow(
        """
        SELECT id, name, program, sector
        FROM v_students
        WHERE id = $1
        """,
        student_id,
    )
    if not student:
        return {
            "studentName": "Unknown",
            "college": "Unknown",
            "sector": "",
            "termName": "",
            "average": 0,
            "gpa": None,
            "classAverage": 0,
            "bestTopic": "None",
            "weakestTopic": "None",
            "bestTopicScore": None,
            "weakestTopicScore": None,
            "topicsFrom": "questions",
            "scoreTimeline": [],
            "topics": [],
            "insight": "No data found.",
        }

    attempt_rows = await db.fetch(
        """
        SELECT
            a.exam_id,
            a.exam_title,
            a.score,
            x.scheduled_at,
            c.name AS course_name,
            c.code AS course_code,
            t.id AS term_id,
            t.name AS term_name,
            t.start_date,
            y.is_current
        FROM v_exam_attempts a
        JOIN exams x ON x.id = a.exam_id
        JOIN course_offerings o ON o.id = x.offering_id
        JOIN courses c ON c.id = o.course_id
        JOIN terms t ON t.id = o.term_id
        JOIN academic_years y ON y.id = t.academic_year_id
        WHERE a.student_id = $1 AND a.participated AND a.score IS NOT NULL
        ORDER BY x.scheduled_at ASC, c.code ASC
        """,
        student["id"],
    )
    semester = select_semester_attempts([dict(row) for row in attempt_rows])
    exam_ids = [row["exam_id"] for row in semester]
    class_avgs = {}
    if exam_ids:
        avgs = await db.fetch(
            "SELECT exam_id, avg_score FROM get_exam_averages($1::text[])",
            exam_ids,
        )
        class_avgs = {r["exam_id"]: r["avg_score"] for r in avgs}

    timeline = []
    student_scores = []
    class_scores = []
    for row in semester:
        title = (row["exam_title"] or "").split("—")[0].strip()
        score = round(float(row["score"]), 2)
        c_avg = round1(class_avgs.get(row["exam_id"], score))
        student_scores.append(float(row["score"]))
        class_scores.append(c_avg)
        timeline.append(
            {
                "exam": title,
                "course": row["course_name"] or "",
                "courseCode": row["course_code"] or "",
                "date": row["scheduled_at"].isoformat() if row["scheduled_at"] else "",
                "score": score,
                "classAverage": c_avg,
            }
        )
    _chart_labels(timeline)

    average = round1(avg(student_scores))
    class_average = round1(avg(class_scores))
    term_name = semester[0]["term_name"] if semester else ""

    question_topics: list[dict] = []
    if exam_ids:
        topic_rows = await db.fetch(
            """
            SELECT q.topic, ROUND(100.0 * AVG(ans.is_correct::int), 1)::float AS score
            FROM attempt_answers ans
            JOIN questions q ON q.id = ans.question_id
            JOIN exam_attempts a ON a.id = ans.attempt_id
            WHERE a.student_id = $1 AND a.exam_id = ANY($2::text[])
            GROUP BY q.topic
            ORDER BY 2 DESC
            """,
            student["id"],
            exam_ids,
        )
        question_topics = [
            {"topic": r["topic"], "score": float(r["score"])} for r in topic_rows
        ]
    topics_from, topics = resolve_topic_scores(question_topics, semester)
    if topics:
        best_topic = topics[0]["topic"]
        weakest_topic = topics[-1]["topic"]
        best_score = topics[0]["score"]
        weakest_score = topics[-1]["score"]
    else:
        best_topic = "None"
        weakest_topic = "None"
        best_score = None
        weakest_score = None

    transcript = await build_profile_years(db, student["id"])
    gpa = transcript["gpa"] if transcript["totalCredits"] else None
    college = student["program"] or "Unknown"
    compared = "above" if average >= class_average else "below"
    if semester and gpa is not None:
        insight = (
            f"You are in {college}. This semester ({term_name}) your average is "
            f"{average}, {compared} the class average of {class_average}. "
            f"Cumulative GPA is {gpa}."
        )
    elif semester:
        insight = (
            f"You are in {college}. This semester ({term_name}) your average is "
            f"{average}, {compared} the class average of {class_average}."
        )
    else:
        insight = (
            f"You are in {college}. No exams are recorded for the current semester."
        )

    return {
        "studentName": student["name"],
        "college": college,
        "sector": student["sector"] or "",
        "termName": term_name,
        "average": average,
        "gpa": gpa,
        "classAverage": class_average,
        "bestTopic": best_topic,
        "weakestTopic": weakest_topic,
        "bestTopicScore": best_score,
        "weakestTopicScore": weakest_score,
        "topicsFrom": topics_from,
        "scoreTimeline": timeline,
        "topics": topics,
        "insight": insight,
    }


async def get_student_profile(
    student_id: str,
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
) -> dict:
    student = await db.fetchrow(
        """
        SELECT id, name, program, section
        FROM v_students
        WHERE id = $1
        """,
        student_id,
    )
    if not student:
        raise Exception("Student not found or not accessible")

    attempts = await db.fetch(
        """
        SELECT a.exam_id, a.exam_title, a.score, x.scheduled_at, c.name as course_name,
               c.code as course_code, a.time_taken_min
        FROM v_exam_attempts a
        JOIN exams x ON x.id = a.exam_id
        JOIN course_offerings o ON o.id = x.offering_id
        JOIN courses c ON c.id = o.course_id
        WHERE a.student_id = $1 AND a.participated = true
        ORDER BY x.scheduled_at DESC
        """,
        student_id,
    )
    scores = [float(a["score"]) for a in attempts]
    overall_from_exams = round1(avg(scores)) if scores else 0.0
    recent = []
    for a in attempts[:5]:
        s = float(a["score"])
        recent.append(
            {
                "exam": a["exam_title"],
                "course": a["course_name"],
                "date": a["scheduled_at"].isoformat() if a["scheduled_at"] else "",
                "score": s,
                "minutes": a["time_taken_min"] or 0,
                "status": "Pass" if s >= PASS_MARK else "Fail",
            }
        )

    attendance_row = await db.fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE participated) AS taken
        FROM v_exam_attempts
        WHERE student_id = $1
        """,
        student_id,
    )
    attendance = (
        round1(attendance_row["taken"] / attendance_row["total"] * 100)
        if attendance_row and attendance_row["total"]
        else 0.0
    )

    transcript = await build_profile_years(db, student_id)
    overall = transcript["overallAverage"] or overall_from_exams
    gpa = transcript["gpa"]
    standing = transcript["standing"] or standing_from_gpa(gpa, overall)

    topic_rows = await db.fetch(
        """
        SELECT q.topic, ROUND(100.0 * AVG(ans.is_correct::int), 1)::float AS score
        FROM attempt_answers ans
        JOIN questions q ON q.id = ans.question_id
        JOIN exam_attempts a ON a.id = ans.attempt_id
        WHERE a.student_id = $1
        GROUP BY q.topic
        ORDER BY 2 DESC
        """,
        student_id,
    )
    topics = [{"topic": r["topic"], "score": float(r["score"])} for r in topic_rows]
    if not topics:
        topics = [{"topic": "General", "score": overall}]

    cohort = await db.fetchrow(
        """
        SELECT COUNT(*)::int AS size
        FROM v_students
        WHERE program = $1
        """,
        student["program"],
    )

    return {
        "studentId": student["id"],
        "name": student["name"],
        "program": student["program"] or "Unknown",
        "section": student["section"] or "A",
        "cohortRank": 1,
        "cohortSize": cohort["size"] if cohort else 0,
        "overallAverage": overall,
        "gpa": gpa,
        "classAverage": overall,
        "attendance": attendance,
        "totalCredits": transcript["totalCredits"],
        "standing": standing,
        "years": transcript["years"],
        "yearTrend": transcript["yearTrend"],
        "courseMatrix": transcript["courseMatrix"],
        "recentAttempts": recent,
        "topics": topics,
        "insight": (
            f"Student is performing at {overall}% average with a cumulative GPA of {gpa}."
        ),
    }
