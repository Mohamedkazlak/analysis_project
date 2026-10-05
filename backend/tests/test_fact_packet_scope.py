"""Scope framing expectations for fact packets (unit-level)."""

from services.ai_facts.models import FactPacket
from services.ai_facts.narration import template_narrative
from tests.helpers import make_scope, make_user


def test_professor_packet_slice_keeps_curriculum_only():
    packet = FactPacket(
        card_id="ai-decision",
        role="professor",
        scope_id="prog-computer-science",
        slice={"curriculumId": "crs-cs-aim303", "collegeId": None},
        data_version="v",
        headline_metrics={"passRate": 50.0},
        no_structural_cause=False,
    )
    assert packet.slice.get("curriculumId") == "crs-cs-aim303"
    assert packet.role == "professor"


def test_student_packet_has_no_peer_anomalies_by_convention():
    packet = FactPacket(
        card_id="ai-decision",
        role="student",
        scope_id="prog-computer-science",
        slice={"studentId": "s7"},
        data_version="v",
        headline_metrics={"passRate": 55.0},
        anomalies=[],
    )
    narr = template_narrative(packet)
    assert narr["source"] == "template"


def test_make_user_helper_roles():
    user = make_user(
        make_scope(
            user_id="u-prof-cs",
            role="professor",
            scope_id="prog-computer-science",
            person_id="p-tomas-oyelaran",
            scope_level="program",
            college_id="prog-computer-science",
            course_ids=["crs-cs-aim303"],
        )
    )
    assert user.role == "professor"
