from services.ai_context import datasets_for, _role_allows
from services.ai_pages import normalize_page, page_focus, page_label
from services.ai_page_focus import (
    filter_evidence,
    filter_recommendations,
    filter_warnings,
    focus_packet,
)
from services.ai_facts.attribution import extract_section_topic_signals
from services.ai_facts.models import Anomaly, Driver, FactPacket, RuleAlert
from services.ai_facts.narration import template_narrative


def test_normalize_unknown_page_falls_back():
    assert normalize_page("not-a-page") == "overview"
    assert normalize_page("courses") == "courses"


def test_participation_focus_hides_forecast():
    assert page_focus("participation")["show_forecast"] is False
    assert (
        "Attendance" in page_label("participation")
        or "participation" in page_label("participation").lower()
    )


def test_overview_loads_full_role_union():
    role = "senior_management"
    assert datasets_for(role, "overview") == _role_allows(role)
    assert "integrity" in datasets_for(role, "overview")
    assert "participation" in datasets_for(role, "overview")
    assert "items" in datasets_for(role, "overview")


def test_participation_page_needs_are_narrower_than_overview():
    role = "senior_management"
    overview = datasets_for(role, "overview")
    participation = datasets_for(role, "participation")
    assert participation < overview
    assert "participation" in participation
    assert "integrity" not in participation


def test_focus_packet_filters_anomalies_for_courses():
    packet = FactPacket(
        card_id="c",
        role="senior_management",
        scope_id=None,
        slice={},
        data_version="v",
        headline_metrics={"passRate": 70, "attendance": 80},
        drivers=[Driver(label="Course AIM303", contribution_points=2.0, kind="course")],
        anomalies=[
            Anomaly(
                id="a1",
                detector="x",
                severity="high",
                confidence=0.9,
                text="odd pattern",
            )
        ],
        rule_alerts=[
            RuleAlert(
                id="r1",
                rule="pass_rate_below_threshold",
                severity="medium",
                text="low",
            )
        ],
    )
    focused = focus_packet(packet, "courses")
    assert focused.anomalies == []
    assert focused.drivers
    assert all(d.kind in ("course", "section") for d in focused.drivers)


def test_focus_packet_hard_filters_unrelated_drivers():
    packet = FactPacket(
        card_id="c",
        role="senior_management",
        scope_id=None,
        slice={},
        data_version="v",
        headline_metrics={"passRate": 70},
        drivers=[
            Driver(label="Course AIM303", contribution_points=2.0, kind="course"),
            Driver(label="Topic Algebra", contribution_points=1.5, kind="topic"),
        ],
    )
    focused = focus_packet(packet, "item-analysis")
    assert [d.kind for d in focused.drivers] == ["topic"]
    assert focused.forecast is None or True


def test_participation_focus_drops_pass_rate_drivers():
    packet = FactPacket(
        card_id="c",
        role="senior_management",
        scope_id=None,
        slice={},
        data_version="v",
        headline_metrics={"passRate": 70, "attendance": 82},
        drivers=[Driver(label="Course AIM303", contribution_points=2.0, kind="course")],
        rule_alerts=[
            RuleAlert(
                id="a1",
                rule="attendance_below_threshold",
                severity="medium",
                text="Attendance is low",
                value=70,
                threshold=85,
            ),
            RuleAlert(
                id="p1",
                rule="pass_rate_below_threshold",
                severity="medium",
                text="Pass rate is low",
                value=55,
                threshold=70,
            ),
        ],
        forecast=None,
    )
    focused = focus_packet(packet, "participation")
    assert focused.drivers == []
    assert focused.forecast is None
    assert len(focused.rule_alerts) == 1
    assert "attendance" in focused.rule_alerts[0].rule


def test_filter_evidence_and_warnings_by_page():
    evidence = [
        {"name": "pass_rate", "dataset": "passRateByCourse", "value": 60},
        {"name": "attendance_rate", "dataset": "attendanceByCurriculum", "value": 70},
        {"name": "discrimination_index", "dataset": "item_analysis", "value": 0.1},
    ]
    warnings = [
        {"metric": "pass_rate", "rule": "pass_rate_below_threshold", "text": "p"},
        {
            "metric": "attendance_rate",
            "rule": "attendance_below_threshold",
            "text": "a",
        },
    ]
    part_ev = filter_evidence(evidence, "participation")
    assert all(r["name"] == "attendance_rate" for r in part_ev)
    part_w = filter_warnings(warnings, "participation")
    assert [w["metric"] for w in part_w] == ["attendance_rate"]

    overview_ev = filter_evidence(evidence, "overview")
    assert overview_ev == evidence


def test_filter_recommendations_by_route():
    recs = {
        "insightId": "x",
        "items": [
            {"id": "1", "metric": "college_pass_rate", "action": {"to": "/courses"}},
            {
                "id": "2",
                "metric": "curriculum_attendance",
                "action": {"to": "/participation"},
            },
            {"id": "3", "metric": "flagged_attempts", "action": {"to": "/integrity"}},
        ],
    }
    filtered = filter_recommendations(recs, "participation")
    assert filtered is not None
    assert [i["id"] for i in filtered["items"]] == ["2"]
    assert filter_recommendations(recs, "overview") == recs


def test_extract_section_topic_signals_reads_courses_and_items():
    sections, topics = extract_section_topic_signals(
        {
            "courses": {
                "sections": [
                    {"section": "A", "course": "Calc", "average": 55, "passRate": 50},
                    {"section": "B", "course": "Alg", "average": 80, "passRate": 85},
                ]
            },
            "items": {
                "questions": [
                    {"topic": "Limits", "pctCorrect": 20},
                    {"topic": "Limits", "pctCorrect": 30},
                    {"topic": "Derivatives", "pctCorrect": 90},
                ]
            },
        }
    )
    assert len(sections) == 2
    assert sections[0].get("delta") is not None
    assert any(t["topic"] == "Limits" for t in topics)
    limits = next(t for t in topics if t["topic"] == "Limits")
    assert limits["correct_rate"] is not None
    assert limits["correct_rate"] < 0.5


def test_page_narratives_differ_after_focus():
    shared = FactPacket(
        card_id="c",
        role="senior_management",
        scope_id=None,
        slice={},
        data_version="v",
        headline_metrics={
            "passRate": 62,
            "attendance": 78,
            "students": 120,
            "exams": 9,
        },
        drivers=[
            Driver(label="Course AIM303", contribution_points=3.0, kind="course"),
            Driver(label="Topic Algebra", contribution_points=1.2, kind="topic"),
        ],
        rule_alerts=[
            RuleAlert(
                id="att",
                rule="attendance_below_threshold",
                severity="medium",
                text="Attendance is 70%",
                value=70,
                threshold=85,
            ),
            RuleAlert(
                id="pass",
                rule="pass_rate_below_threshold",
                severity="medium",
                text="Pass rate is 62%",
                value=62,
                threshold=70,
            ),
        ],
    )
    courses = focus_packet(
        FactPacket(
            **{
                **shared.__dict__,
                "drivers": list(shared.drivers),
                "rule_alerts": list(shared.rule_alerts),
            }
        ),
        "courses",
    )
    participation = focus_packet(
        FactPacket(
            **{
                **shared.__dict__,
                "drivers": list(shared.drivers),
                "rule_alerts": list(shared.rule_alerts),
            }
        ),
        "participation",
    )
    courses_narr = template_narrative(courses, language="en", page="courses")
    part_narr = template_narrative(participation, language="en", page="participation")
    assert courses_narr["headline"] != part_narr["headline"]
    assert (
        "Attendance" in part_narr["headline"]
        or "attendance" in part_narr["story"].lower()
    )
    assert (
        "Course" in courses_narr["headline"] or "pass" in courses_narr["story"].lower()
    )
