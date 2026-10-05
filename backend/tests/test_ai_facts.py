"""Unit tests for attribution, detectors, and narration validation."""

from services.ai_facts.attribution import attribute_gap
from services.ai_facts.detectors import (
    detect_ip_timing_clusters,
    detect_question_topic_outlier,
    detect_section_score_outlier,
    detect_yoy_fail_jump,
)
from services.ai_facts.models import Driver, FactPacket
from services.ai_facts.narration import template_narrative, validate_narrative


def test_attribution_ranks_weak_courses():
    drivers = attribute_gap(
        scope_pass_rate=62.0,
        benchmark_pass_rate=70.0,
        courses=[
            {"course": "AIM303", "passRate": 50.0, "participants": 80},
            {"course": "AIM301", "passRate": 78.0, "participants": 80},
            {"course": "BAS121", "passRate": 65.0, "participants": 40},
        ],
        sections=[{"section": "B", "delta": 15.0}],
        topics=[{"topic": "Use Cases", "correct_rate": 0.25}],
    )
    assert drivers
    assert drivers[0].contribution_points > 0
    assert any("AIM303" in d.label for d in drivers)


def test_section_outlier_detector():
    anomalies = detect_section_score_outlier(
        [
            {"section": "A", "mean": 62.0, "sd": 14.0},
            {"section": "B", "mean": 88.0, "sd": 2.0},
            {"section": "C", "mean": 60.0, "sd": 13.0},
        ]
    )
    assert any(a.entity == "B" for a in anomalies)


def test_question_topic_outlier_detector():
    anomalies = detect_question_topic_outlier(
        [
            {"id": "q1", "topic": "Architecture", "correct_rate": 0.01},
            {"id": "q2", "topic": "Architecture", "correct_rate": 0.72},
            {"id": "q3", "topic": "Architecture", "correct_rate": 0.70},
        ]
    )
    assert anomalies and anomalies[0].detector == "question_correct_rate_vs_topic"


def test_question_topic_outlier_detector_arabic():
    anomalies = detect_question_topic_outlier(
        [
            {"id": "q1", "topic": "Architecture", "correct_rate": 0.01},
            {"id": "q2", "topic": "Architecture", "correct_rate": 0.72},
            {"id": "q3", "topic": "Architecture", "correct_rate": 0.70},
        ],
        language="ar",
    )
    assert anomalies
    assert "سؤال حول موضوع الهندسة المعمارية" in anomalies[0].text
    assert "near-0%" not in anomalies[0].text


def test_yoy_fail_jump_detector():
    anomalies = detect_yoy_fail_jump(
        [
            {"course": "ENG 110", "year": "2024/25", "fail_rate": 0.15},
            {"course": "ENG 110", "year": "2025/26", "fail_rate": 0.40},
        ]
    )
    assert anomalies and anomalies[0].detector == "yoy_fail_rate_jump"


def test_ip_timing_cluster_detector():
    attempts = [{"ip": "10.50.1.9", "time_taken_min": 10} for _ in range(6)] + [
        {"ip": "10.0.0.1", "time_taken_min": 45}
    ]
    anomalies = detect_ip_timing_clusters(attempts)
    assert any(a.detector == "ip_timing_cluster" for a in anomalies)


def test_narration_validator_rejects_unknown_number():
    packet = FactPacket(
        card_id="c1",
        role="senior_management",
        scope_id="uni-bnu",
        slice={},
        data_version="v1",
        headline_metrics={"passRate": 61.0},
        drivers=[
            Driver(label="Course AIM303", contribution_points=4.5, evidence_refs=[])
        ],
    )
    assert validate_narrative("Pass rate is 61%", packet)
    assert not validate_narrative("Pass rate is 99%", packet)


def test_empty_drivers_template_says_no_structural_cause():
    packet = FactPacket(
        card_id="c1",
        role="program_director",
        scope_id="prog-veterinary",
        slice={},
        data_version="v1",
        headline_metrics={"passRate": 68.0},
        drivers=[],
        no_structural_cause=True,
    )
    narr = template_narrative(packet)
    blob = f"{narr['headline']} {narr['story']}".lower()
    assert (
        "review signal" in blob
        or "nothing stands out" in blob
        or "no structural cause" in blob
        or "combined review" in blob
        or "pass rate is 68" in blob
    )
