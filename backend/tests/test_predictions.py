import asyncio
from unittest.mock import AsyncMock

from schemas.filters import AnalyticsFilters
from services.predictions import (
    _scoped_offering_year_count,
    current_standing_from_context,
)


def test_management_output_is_current_standing_not_a_forecast():
    data = {
        "overview": {
            "passRateByCollege": [
                {
                    "college": "Engineering",
                    "passRate": 72,
                    "participants": 80,
                    "courses": 4,
                },
                {
                    "college": "Business",
                    "passRate": 64,
                    "participants": 50,
                    "courses": 3,
                },
            ]
        }
    }
    result = current_standing_from_context("senior_management", data)
    assert result is not None
    assert result["kind"] == "current_standing"
    assert "forecast" not in result["title"].lower()
    assert "prediction" not in result["title"].lower()
    assert "not a forecast" in result["summary"]


def test_university_landing_standing_uses_sql_totals():
    data = {
        "filters": AnalyticsFilters(),
        "overview": {
            "totals": {
                "exams": 40,
                "students": 900,
                "passRate": 74.2,
                "attendance": 88.5,
                "colleges": 9,
            },
            "passRateByCollege": [
                {"college": "Engineering", "passRate": 68.0, "participants": 100},
                {"college": "Medicine", "passRate": 81.0, "participants": 120},
            ],
        },
    }
    result = current_standing_from_context("senior_management", data)
    assert result["title"] == "Current standing · university"
    assert result["rows"][0] == {
        "label": "Student pass rate",
        "value": "74.2%",
        "tone": "mint",
    }
    assert result["rows"][2]["value"] == "900"
    assert "Engineering" not in result["rows"][0]["label"]


def test_sector_selection_keeps_college_standing():
    data = {
        "filters": AnalyticsFilters(sector_id="sec-eng"),
        "overview": {
            "totals": {
                "exams": 12,
                "students": 200,
                "passRate": 70.0,
                "attendance": 80.0,
                "colleges": 2,
            },
            "passRateByCollege": [
                {"college": "Engineering", "passRate": 68.0, "participants": 100},
                {"college": "Energy Sciences", "passRate": 74.0, "participants": 80},
            ],
        },
    }
    result = current_standing_from_context("senior_management", data)
    assert result["title"] == "Current standing · colleges in this sector"
    assert result["rows"][0]["label"] == "Engineering"


def test_empty_scope_returns_nothing_rather_than_inventing_numbers():
    assert current_standing_from_context("senior_management", {"overview": {}}) is None
    assert current_standing_from_context("student", {"dashboard": {}}) is None
    assert current_standing_from_context("professor", {"courses": {}}) is None


def test_student_and_professor_standing_use_recorded_scores_only():
    student = current_standing_from_context(
        "student",
        {"dashboard": {"average": 71, "classAverage": 68}},
    )
    assert student["kind"] == "current_standing"
    assert student["rows"][0]["value"] == "71"
    assert "forecast" not in student["title"].lower()
    professor = current_standing_from_context(
        "professor",
        {
            "courses": {
                "sections": [
                    {"section": "A", "average": 80, "passRate": 90},
                    {"section": "B", "average": 62, "passRate": 70},
                ]
            }
        },
    )
    assert professor["rows"][0]["label"] == "B"
    assert "62" in professor["rows"][0]["value"]


def test_offering_year_count_is_scoped_not_global():
    async def run():
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=1)
        filters = AnalyticsFilters(sector_id="sec-a", college_id="col-a")
        count = await _scoped_offering_year_count(db, filters)
        assert count == 1
        sql = db.fetchval.await_args.args[0]
        assert "parent_id" in sql
        assert "program_id" in sql
        assert db.fetchval.await_args.args[1:] == ("sec-a", "col-a")
        assert "FROM course_offerings" in sql.replace("\n", " ")

    asyncio.run(run())
