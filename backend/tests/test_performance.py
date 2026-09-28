from datetime import date

from repositories.performance import build_semester_pass_rates


def _row(term_id, name, start, course, college_id, passed, scored, exam=None):
    return {
        "term_id": term_id,
        "term_name": name,
        "start_date": start,
        "exam": exam or course,
        "course": course,
        "college": college_id,
        "college_id": college_id,
        "passed": passed,
        "scored": scored,
    }


def test_pass_rates_compare_latest_term_with_the_one_before():
    result = build_semester_pass_rates(
        [
            _row("fall", "Fall 2025", date(2025, 9, 1), "AIM301", "prog-cs", 1, 2),
            _row(
                "spring", "Spring 2026", date(2026, 2, 1), "MED 101", "prog-med", 9, 10
            ),
            _row("old", "Spring 2024", date(2024, 2, 1), "OLD", "prog-cs", 1, 1),
        ]
    )
    assert result["currentTerm"] == "Spring 2026"
    assert result["previousTerm"] == "Fall 2025"
    by_course = {row["course"]: row for row in result["semesterComparison"]}
    assert "OLD" not in by_course
    assert by_course["MED 101"]["current"] == 90.0
    assert by_course["MED 101"]["previous"] is None
    assert by_course["AIM301"]["current"] is None
    assert by_course["AIM301"]["previous"] == 50.0


def test_pass_rates_are_empty_without_scored_exams():
    assert build_semester_pass_rates([]) == {
        "semesterComparison": [],
        "currentTerm": None,
        "previousTerm": None,
    }
