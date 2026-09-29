from datetime import date

from repositories.student import (
    resolve_topic_scores,
    select_semester_attempts,
)


def _attempt(**kwargs):
    data = dict(
        exam_id="e1",
        term_id="term-fall",
        term_name="Fall 2025",
        start_date=date(2025, 9, 14),
        scheduled_at=date(2025, 12, 10),
        course_code="BAS121",
        course_name="Physics",
        score=90,
        is_current=True,
    )
    data.update(kwargs)
    return data


def test_current_semester_is_the_latest_term_sat_this_year():
    rows = select_semester_attempts(
        [
            _attempt(exam_id="fall", term_id="term-fall", start_date=date(2025, 9, 14)),
            _attempt(
                exam_id="spring",
                term_id="term-spring",
                term_name="Spring 2026",
                start_date=date(2026, 2, 1),
                course_code="CS201",
            ),
            _attempt(
                exam_id="old",
                term_id="term-old",
                start_date=date(2024, 9, 1),
                is_current=False,
            ),
        ]
    )
    assert [row["exam_id"] for row in rows] == ["spring"]


def test_semester_keeps_the_only_term_sat_in_the_current_year():
    rows = select_semester_attempts(
        [
            _attempt(exam_id="a", course_code="AIM303"),
            _attempt(exam_id="b", course_code="BAS121"),
            _attempt(
                exam_id="old",
                term_id="term-old",
                start_date=date(2024, 9, 1),
                is_current=False,
                course_code="OLD",
            ),
        ]
    )
    assert [row["exam_id"] for row in rows] == ["a", "b"]


def test_semester_falls_back_when_the_current_year_has_no_exams():
    rows = select_semester_attempts(
        [
            _attempt(
                exam_id="older",
                term_id="term-2023",
                start_date=date(2024, 2, 1),
                is_current=False,
                course_code="OLD1",
            ),
            _attempt(
                exam_id="newer",
                term_id="term-2024",
                term_name="Spring 2025",
                start_date=date(2025, 2, 2),
                is_current=False,
                course_code="OLD2",
            ),
        ]
    )
    assert [row["exam_id"] for row in rows] == ["newer"]


def test_single_question_topic_uses_course_scores():
    basis, topics = resolve_topic_scores(
        [{"topic": "Course assessment", "score": 70}],
        [
            _attempt(course_code="BAS121", course_name="Physics", score=95.98),
            _attempt(
                course_code="BCS311",
                course_name="الذكاء الاصطناعي",
                score=54.32,
            ),
        ],
    )
    assert basis == "courses"
    assert topics[0] == {"topic": "Physics", "score": 95.98}
    assert topics[-1]["topic"] == "الذكاء الاصطناعي"
    assert topics[-1]["score"] == 54.32


def test_distinct_question_topics_are_kept():
    basis, topics = resolve_topic_scores(
        [
            {"topic": "Recursion", "score": 80},
            {"topic": "Graphs", "score": 55},
        ],
        [_attempt(score=90)],
    )
    assert basis == "questions"
    assert [row["topic"] for row in topics] == ["Recursion", "Graphs"]
