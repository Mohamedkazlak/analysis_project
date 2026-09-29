import asyncpg

from repositories.sql_filters import course_org_where
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters


async def get_item_analysis(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
):
    filters = filters or AnalyticsFilters()
    where_sql, args, next_i = course_org_where(filters)
    student_sql = "TRUE"
    if filters.student_id:
        student_sql = f"a.student_id = ${next_i}"
        args.append(filters.student_id)

    rows = await db.fetch(
        f"""
        WITH scored AS (
            SELECT
                q.id AS question_id,
                q.exam_id,
                q.number,
                q.topic,
                q.prompt,
                c.code || ' · ' || split_part(x.title, ' — ', 1) AS exam_label,
                ans.is_correct,
                percent_rank() OVER (PARTITION BY q.exam_id ORDER BY a.score) AS pr
            FROM questions q
            JOIN exams x ON x.id = q.exam_id
            JOIN course_offerings o ON o.id = x.offering_id
            JOIN courses c ON c.id = o.course_id
            JOIN org_units p ON p.id = c.program_id
            JOIN attempt_answers ans ON ans.question_id = q.id
            JOIN exam_attempts a ON a.id = ans.attempt_id
            WHERE a.score IS NOT NULL
              AND {where_sql}
              AND {student_sql}
        )
        SELECT
            question_id AS id,
            exam_id AS "examId",
            number,
            exam_label AS exam,
            topic,
            prompt,
            ROUND(100.0 * AVG(is_correct::int), 1)::float AS "pctCorrect",
            ROUND(1.0 * AVG(is_correct::int), 2)::float AS "difficultyIndex",
            ROUND(
                COALESCE(AVG(is_correct::int) FILTER (WHERE pr >= 0.73), 0)
                - COALESCE(AVG(is_correct::int) FILTER (WHERE pr <= 0.27), 0)
            , 2)::float AS "discriminationIndex"
        FROM scored
        GROUP BY question_id, exam_id, number, exam_label, topic, prompt
        ORDER BY "discriminationIndex"
        """,
        *args,
    )

    questions = []
    for r in rows:
        pct_correct = float(r["pctCorrect"])
        discrimination = float(r["discriminationIndex"])
        questions.append(
            {
                "id": r["id"],
                "examId": r["examId"],
                "number": r["number"],
                "exam": r["exam"],
                "topic": r["topic"],
                "prompt": r["prompt"],
                "pctCorrect": pct_correct,
                "pctIncorrect": round(100 - pct_correct, 1),
                "difficultyIndex": float(r["difficultyIndex"]),
                "discriminationIndex": discrimination,
                "flagged": discrimination < 0.2,
            }
        )

    needs_review = questions[:6]
    insight = (
        (
            f"Question {needs_review[0]['number']} on {needs_review[0]['exam']} has a discrimination index of "
            f"{needs_review[0]['discriminationIndex']}."
        )
        if needs_review
        else "No items in this scope yet."
    )
    return {"questions": questions, "needsReview": needs_review, "insight": insight}
