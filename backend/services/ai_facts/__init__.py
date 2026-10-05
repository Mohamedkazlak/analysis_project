"""Fact packet / attribution / anomaly / narration for AI cards."""

from services.ai_facts.packet import build_fact_packet, packet_to_decision_fields
from services.ai_facts.narration import narrate_packet, template_narrative, validate_narrative
from services.ai_facts.attribution import attribute_gap
from services.ai_facts.detectors import (
    detect_ip_timing_clusters,
    detect_question_topic_outlier,
    detect_section_score_outlier,
    detect_yoy_fail_jump,
    run_detectors,
)

__all__ = [
    "build_fact_packet",
    "packet_to_decision_fields",
    "narrate_packet",
    "template_narrative",
    "validate_narrative",
    "attribute_gap",
    "run_detectors",
    "detect_section_score_outlier",
    "detect_question_topic_outlier",
    "detect_yoy_fail_jump",
    "detect_ip_timing_clusters",
]
