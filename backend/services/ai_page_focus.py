"""Apply page focus to a fact packet / decision fields."""

from __future__ import annotations

from typing import Any, Optional

from services.ai_facts.models import FactPacket
from services.ai_pages import normalize_page, page_focus, page_label


def focus_packet(packet: FactPacket, page: str) -> FactPacket:
    focus = page_focus(page)
    page = normalize_page(page)
    kinds = tuple(focus.get("driver_kinds") or ())
    # Overview keeps every driver. Other pages hard-filter; empty is OK.
    if page != "overview" and "driver_kinds" in focus:
        if kinds:
            packet.drivers = [d for d in packet.drivers if d.kind in kinds]
        else:
            packet.drivers = []

    rule_metrics = focus.get("rule_metrics") or focus.get("warning_metrics")
    if rule_metrics:
        wanted = set(rule_metrics)
        filtered = [
            a
            for a in packet.rule_alerts
            if any(
                m in (a.rule or "") or m in (a.id or "") or m in (a.text or "").lower()
                for m in wanted
            )
        ]
        # Attendance pages: also match plain "attendance" wording.
        if "attendance_rate" in wanted:
            filtered = filtered or [
                a
                for a in packet.rule_alerts
                if "attendance" in (a.rule or "")
                or "attendance" in (a.text or "").lower()
            ]
        packet.rule_alerts = filtered

    if not focus.get("show_anomalies", True):
        packet.anomalies = []
    if not focus.get("show_rules", True):
        packet.rule_alerts = []
    if not focus.get("show_impact", True):
        packet.impact_items = []
    if not focus.get("show_forecast", True):
        packet.forecast = None

    # Keep headline metrics relevant to the page.
    wanted_metrics = focus.get("metrics") or ()
    if wanted_metrics and packet.headline_metrics:
        narrowed = {
            k: v
            for k, v in packet.headline_metrics.items()
            if k in wanted_metrics and v is not None
        }
        if narrowed:
            packet.headline_metrics = narrowed

    # Recompute no_structural after focus: alerts without page drivers.
    packet.no_structural_cause = bool(packet.rule_alerts) and not packet.drivers

    return packet


def filter_evidence(evidence: list[dict], page: str) -> list[dict]:
    focus = page_focus(page)
    page = normalize_page(page)
    if page == "overview":
        return evidence
    datasets = set(focus.get("evidence_datasets") or ())
    metrics = set(focus.get("warning_metrics") or ())
    if not datasets and not metrics:
        return evidence
    out = []
    for row in evidence:
        ds = str(row.get("dataset") or "")
        name = str(row.get("name") or "")
        if datasets and ds in datasets:
            out.append(row)
            continue
        if metrics and name in metrics:
            out.append(row)
            continue
    return out


def filter_warnings(warnings: list[dict], page: str) -> list[dict]:
    focus = page_focus(page)
    page = normalize_page(page)
    if page == "overview":
        return warnings
    metrics = set(focus.get("warning_metrics") or ())
    if not metrics:
        return warnings
    filtered = [
        w
        for w in warnings
        if str(w.get("metric") or "") in metrics
        or any(m in str(w.get("rule") or "") for m in metrics)
    ]
    return filtered


def filter_recommendations(
    recommendations: Optional[dict], page: str
) -> Optional[dict]:
    if not recommendations:
        return recommendations
    focus = page_focus(page)
    page = normalize_page(page)
    if page == "overview":
        return recommendations
    routes = tuple(focus.get("recommendation_routes") or ())
    if not routes:
        return recommendations
    items = recommendations.get("items") or []
    kept = []
    for item in items:
        action = item.get("action") or {}
        to = str(action.get("to") or "")
        topic = str(item.get("topic") or item.get("metric") or "")
        if any(to == r or to.endswith(r) for r in routes):
            kept.append(item)
            continue
        # Topic/metric hints when action is missing.
        if page == "participation" and "attendance" in topic.lower():
            kept.append(item)
        elif page == "item-analysis" and "discrimination" in topic.lower():
            kept.append(item)
        elif page in ("integrity", "real-time") and "flagged" in topic.lower():
            kept.append(item)
    if not kept:
        return recommendations
    return {**recommendations, "items": kept}


def page_narrative_prefix(page: str, language: str = "en") -> str:
    page = normalize_page(page)
    label = page_label(page, language)
    if language.startswith("ar"):
        return f"{label}: "
    return f"{label}: "


def apply_page_to_decision_fields(
    fields: dict[str, Any],
    page: str,
    language: str = "en",
) -> dict[str, Any]:
    focus = page_focus(page)
    if not focus.get("show_anomalies", True):
        fields["anomalies"] = []
    if not focus.get("show_rules", True):
        fields["ruleAlerts"] = []
    if not focus.get("show_impact", True):
        fields["impactItems"] = []
    if not focus.get("show_forecast", True):
        fields["forecastStatus"] = None
    fields["page"] = normalize_page(page)
    fields["pageLabel"] = page_label(page, language)
    return fields
