"""Deterministic AI evidence, warnings, forecasts, and narration checks."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

from schemas.ai_insights import AiDecision
from schemas.filters import AnalyticsFilters
from services import ai_cache
from services.ai_evidence import build_evidence
from services.ai_rules import PASS_RATE_THRESHOLD, build_warnings
from services.ai_validation import narration_is_valid
from services.predictions import linear_forecast
from rag.narrative import apply_llm_narratives
from tests.helpers import make_scope, make_user


def test_evidence_uses_repository_metrics_and_scope_average():
    evidence = build_evidence(
        "senior_management",
        {
            "overview": {
                "passRateByCollege": [
                    {
                        "college": "Veterinary Medicine",
                        "passRate": 62,
                        "participants": 40,
                        "courses": 2,
                    },
                    {
                        "college": "Engineering",
                        "passRate": 80,
                        "participants": 50,
                        "courses": 3,
                    },
                ],
                "passRateByCourse": [
                    {"course": "VET101", "passRate": 61.4, "participants": 20}
                ],
            }
        },
    )
    vet = next(
        row
        for row in evidence
        if row["entity"] == "Veterinary Medicine" and row["name"] == "pass_rate"
    )
    assert vet["value"] == 62
    assert vet["source"] == "deterministic_sql"
    assert vet["comparison"]["scopeAverage"] == 71.0
    assert all(row["entity"] != "Law" for row in evidence)


def test_empty_scope_does_not_invent_metrics():
    assert build_evidence("senior_management", {"overview": {}}) == []
    assert build_evidence("professor", {"courses": {}}) == []
    assert (
        build_evidence("student", {"dashboard": {"average": 0, "scoreTimeline": []}})
        == []
    )
    warnings = build_warnings("senior_management", [], {})
    assert warnings == []


def test_pass_rate_warning_follows_threshold_and_stays_in_scope():
    low = build_evidence(
        "program_director",
        {
            "overview": {
                "passRateByCollege": [
                    {
                        "college": "Veterinary Medicine",
                        "passRate": 61.4,
                        "participants": 10,
                        "courses": 1,
                    }
                ],
                "passRateByCourse": [],
            }
        },
    )
    warnings = build_warnings("program_director", low, {})
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["rule"] == "pass_rate_below_threshold"
    assert warning["entity"] == "Veterinary Medicine"
    assert warning["value"] == 61.4
    assert warning["threshold"] == PASS_RATE_THRESHOLD
    assert warning["severity"] == "medium"
    assert "Law" not in warning["text"]

    healthy = build_evidence(
        "program_director",
        {
            "overview": {
                "passRateByCollege": [
                    {
                        "college": "Engineering",
                        "passRate": 88,
                        "participants": 10,
                        "courses": 1,
                    }
                ],
                "passRateByCourse": [],
            }
        },
    )
    assert build_warnings("program_director", healthy, {}) == []


def test_professor_warnings_do_not_include_other_roles_data():
    evidence = build_evidence(
        "professor",
        {
            "courses": {
                "sections": [
                    {"section": "A", "average": 80, "passRate": 90},
                    {"section": "B", "average": 55, "passRate": 48},
                ]
            },
            "participation": {
                "attendanceByCurriculum": [{"course": "CS201", "attendance": 74}]
            },
            "items": {
                "needsReview": [
                    {"exam": "Midterm", "number": 4, "discriminationIndex": 0.1}
                ]
            },
        },
    )
    warnings = build_warnings("professor", evidence, {})
    rules = {row["rule"] for row in warnings}
    assert "pass_rate_below_threshold" in rules
    assert "attendance_below_threshold" in rules
    assert "discrimination_below_threshold" in rules
    assert "integrity_signal_detected" not in rules
    attendance = next(
        row for row in warnings if row["rule"] == "attendance_below_threshold"
    )
    assert attendance["value"] == 74
    assert attendance["severity"] == "high"
    assert attendance["entity"] == "CS201"


def test_recommendation_confirmation_is_required_for_actions():
    from services.ai_insights import _recommendations_from_context

    result = _recommendations_from_context(
        "senior_management",
        {
            "overview": {
                "passRateByCollege": [
                    {
                        "college": "Veterinary Medicine",
                        "passRate": 61.4,
                        "participants": 12,
                        "courses": 1,
                    }
                ]
            },
            "integrity": {"flaggedCount": 2, "totalAttempts": 20},
        },
        "insight",
    )
    assert result is not None
    action = next(item for item in result["items"] if item["action"])
    assert action["confirmationRequired"] is True
    assert action["value"] == 61.4
    assert action["basedOn"]["evidence"]
    assert "study harder" not in action["text"].lower()


def test_linear_forecast_needs_three_observations_and_projects_upward():
    assert linear_forecast([71.2, 74.8]) is None
    forecast = linear_forecast([71.2, 74.8, 77.1])
    assert forecast is not None
    assert forecast["method"] == "ols_linear_v1"
    assert forecast["observations"] == 3
    assert forecast["direction"] == "rising"
    assert forecast["value"] > 77.1
    assert forecast["low"] <= forecast["value"] <= forecast["high"]
    assert 0 <= forecast["value"] <= 100


def test_two_years_stay_current_standing():
    from services.predictions import _apply_history, current_standing_from_context

    standing = current_standing_from_context(
        "senior_management",
        {
            "overview": {
                "passRateByCollege": [
                    {
                        "college": "Engineering",
                        "passRate": 72,
                        "participants": 10,
                        "courses": 1,
                    }
                ]
            }
        },
    )
    result = _apply_history(
        standing,
        [{"label": "2024", "avg": 70, "n": 4}, {"label": "2025", "avg": 74, "n": 4}],
    )
    assert result["kind"] == "current_standing"
    assert "not a forecast" in result["summary"]
    assert result["direction"] == "rising"


def test_narration_rejects_new_numbers_entities_causes_and_forecast_edits():
    corpus = "Veterinary Medicine pass_rate 61.4 scopeAverage 71"
    ok, reason = narration_is_valid(
        "Veterinary Medicine pass rate is 61.4%.",
        "Veterinary Medicine currently has a pass rate of 61.4%, below the scope average of 71.",
        corpus,
    )
    assert ok, reason

    ok, reason = narration_is_valid(
        "Veterinary Medicine pass rate is 61.4%.",
        "Veterinary Medicine pass rate is 64%.",
        corpus,
    )
    assert not ok and reason == "numbers"

    ok, reason = narration_is_valid(
        "Veterinary Medicine pass rate is 61.4%.",
        "Law School pass rate is 61.4%.",
        corpus,
    )
    assert not ok and reason == "entities"

    ok, reason = narration_is_valid(
        "Veterinary Medicine pass rate is 61.4%.",
        "Veterinary Medicine pass rate is 61.4% because the exam was too difficult.",
        corpus,
    )
    assert not ok and reason == "cause"

    prediction = {
        "kind": "forecast",
        "direction": "rising",
        "forecastValue": 80.3,
    }
    ok, reason = narration_is_valid(
        "A linear projection estimates the next period at 80.3.",
        "A linear projection estimates the next period at 90.",
        "80.3",
        prediction=prediction,
        summary=True,
    )
    assert not ok and reason == "numbers"

    ok, reason = narration_is_valid(
        "A linear projection estimates the next period at 80.3.",
        "Performance is declining and the next period is 80.3.",
        "80.3",
        prediction=prediction,
        summary=True,
    )
    assert not ok and reason == "direction"


def test_one_model_call_keeps_valid_wording_and_drops_new_numbers(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "AI_NARRATIVE_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://localhost")
    monkeypatch.setattr(settings, "LLM_MODEL", "test")

    async def fake_completion(messages, temperature=0.1, **_extra):
        assert len(messages) == 2
        return json.dumps(
            {
                "sentences": [
                    {
                        "id": "0",
                        "text": "Veterinary Medicine currently has a pass rate of 61.4%.",
                    },
                    {"id": "1", "text": "The pass rate is 99%."},
                ]
            }
        )

    async def run():
        with patch("rag.narrative.chat_completion", fake_completion):
            return await apply_llm_narratives(
                {
                    "insight": {
                        "headline": "Veterinary Medicine pass rate is 61.4%.",
                        "body": "Veterinary Medicine pass rate is 61.4%.",
                    },
                    "prediction": None,
                    "recommendations": None,
                    "evidence": [
                        {
                            "name": "pass_rate",
                            "entity": "Veterinary Medicine",
                            "value": 61.4,
                        }
                    ],
                    "warnings": [],
                    "status": "ok",
                }
            )

    result = asyncio.run(run())
    assert (
        result["insight"]["headline"]
        == "Veterinary Medicine currently has a pass rate of 61.4%."
    )
    assert result["insight"]["body"] == "Veterinary Medicine pass rate is 61.4%."
    assert result["validation"]["status"] == "fallback"
    assert result["validation"]["failures"] == 1


def test_llm_failure_keeps_deterministic_sentence(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "AI_NARRATIVE_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://localhost")
    monkeypatch.setattr(settings, "LLM_MODEL", "test")

    async def fake_completion(messages, temperature=0.1, **_extra):
        return "Law School pass rate is 99% because the exam was too difficult."

    async def run():
        with patch("rag.narrative.chat_completion", fake_completion):
            return await apply_llm_narratives(
                {
                    "insight": {
                        "headline": "Veterinary Medicine",
                        "body": "Veterinary Medicine pass rate is 61.4%.",
                    },
                    "prediction": None,
                    "recommendations": None,
                    "evidence": [
                        {
                            "name": "pass_rate",
                            "entity": "Veterinary Medicine",
                            "value": 61.4,
                        }
                    ],
                    "warnings": [],
                    "status": "ok",
                }
            )

    result = asyncio.run(run())
    assert result["insight"]["body"] == "Veterinary Medicine pass rate is 61.4%."
    assert result["validation"]["status"] == "fallback"


def test_cache_key_includes_data_version_and_user():
    user = make_user(make_scope(user_id="u1", role="professor"))
    other = make_user(make_scope(user_id="u2", role="professor"))
    filters = AnalyticsFilters(curriculum_id="course-1", professor_id="p-1")
    first = ai_cache.make_cache_key(user, filters, data_version="v1")
    second = ai_cache.make_cache_key(user, filters, data_version="v2")
    assert first != second
    assert first != ai_cache.make_cache_key(other, filters, data_version="v1")


def test_decision_schema_accepts_evidence_and_warning():
    decision = AiDecision.model_validate(
        {
            "insight": {
                "headline": "Veterinary Medicine has the lowest pass rate",
                "body": "Veterinary Medicine pass rate is 61.4%.",
                "action": None,
            },
            "prediction": {
                "title": "Current standing",
                "direction": "stable",
                "summary": "Not a forecast.",
                "rows": [],
                "action": None,
                "kind": "current_standing",
            },
            "recommendations": None,
            "warnings": [
                {
                    "id": "pass_rate_below_threshold:Veterinary Medicine:61.4",
                    "rule": "pass_rate_below_threshold",
                    "severity": "medium",
                    "tone": "amber",
                    "metric": "pass_rate",
                    "entity": "Veterinary Medicine",
                    "value": 61.4,
                    "threshold": 70,
                    "text": "Veterinary Medicine pass rate is 61.4%, below the 70% review threshold.",
                }
            ],
            "evidence": [
                {
                    "id": "passRateByCollege:pass_rate:Veterinary Medicine",
                    "name": "pass_rate",
                    "entity": "Veterinary Medicine",
                    "value": 61.4,
                    "unit": "percent",
                    "source": "deterministic_sql",
                    "dataset": "passRateByCollege",
                    "comparison": {"name": "pass_rate", "scopeAverage": 71},
                }
            ],
            "dataStatus": "ready",
            "status": "ok",
            "narrationStatus": "skipped",
        }
    )
    assert decision.evidence[0].value == 61.4
    assert decision.warnings[0].severity == "medium"
    assert decision.dataStatus == "ready"


def _overview():
    return {
        "totals": {
            "exams": 40,
            "students": 900,
            "passRate": 74.2,
            "attendance": 88.0,
            "colleges": 2,
        },
        "passRateByCollege": [
            {
                "college": "Engineering",
                "passRate": 68.0,
                "participants": 100,
                "courses": 4,
            },
            {
                "college": "Medicine",
                "passRate": 81.0,
                "participants": 120,
                "courses": 3,
            },
        ],
        "passRateByCourse": [{"course": "AIM422", "passRate": 0.0}],
    }


def test_university_landing_insight_is_overall():
    from services.ai_insights import _insight_from_context

    insight = _insight_from_context(
        "senior_management",
        {"filters": AnalyticsFilters(), "overview": _overview()},
    )
    assert insight["headline"] == "University student pass rate is 74.2%"
    assert "900 students sat exams" in insight["body"]
    assert "attendance is 88.0%" in insight["body"]
    assert "lowest pass rate" not in insight["headline"]


def test_sector_filter_insight_stays_on_the_weakest_college():
    from services.ai_insights import _insight_from_context

    insight = _insight_from_context(
        "senior_management",
        {
            "filters": AnalyticsFilters(sector_id="sec-eng"),
            "overview": _overview(),
        },
    )
    assert insight["headline"] == "Engineering has the lowest pass rate in this sector"
    assert "Across the 2 colleges in this sector" in insight["body"]


def test_university_landing_evidence_leads_with_totals():
    evidence = build_evidence(
        "senior_management",
        {"filters": AnalyticsFilters(), "overview": _overview()},
    )
    assert evidence[0]["entity"] == "University"
    assert evidence[0]["name"] == "pass_rate"
    assert evidence[0]["value"] == 74.2
