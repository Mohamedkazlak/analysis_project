"""LLM narration over a fact packet with number validation + template fallback."""

from __future__ import annotations

import json
import re
from typing import Any

from services.ai_facts.models import FactPacket

_NUMBER = re.compile(r"(?<![A-Za-z0-9_/])(\d+(?:\.\d+)?)%?")


def _empty_driver_narrative(
    packet: FactPacket, page: str, label: str, language: str
) -> dict[str, Any]:
    """Page-distinct fallback when no structural driver is available."""
    ar = language == "ar" or str(language).startswith("ar")
    metrics = packet.headline_metrics or {}
    pr = metrics.get("passRate")
    att = metrics.get("attendance")
    students = metrics.get("students")
    exams = metrics.get("exams")
    alerts = packet.rule_alerts
    anomalies = packet.anomalies
    captions = {a.id: a.text for a in alerts[:4]}

    if page == "overview":
        parts = []
        if pr is not None:
            parts.append(
                f"Pass rate is {pr:g}%." if not ar else f"معدل النجاح {pr:g}%."
            )
        if att is not None:
            parts.append(f"Attendance is {att:g}%." if not ar else f"الحضور {att:g}%.")
        if students is not None:
            parts.append(
                f"{int(students)} students are in scope."
                if not ar
                else f"{int(students)} طالبًا في النطاق."
            )
        if alerts:
            parts.append(
                f"{len(alerts)} threshold alert(s) need review."
                if not ar
                else f"{len(alerts)} تنبيه عتبة يحتاج مراجعة."
            )
        if anomalies:
            parts.append(
                f"{len(anomalies)} unusual pattern(s) were detected."
                if not ar
                else f"تم رصد {len(anomalies)} نمطًا غير معتاد."
            )
        if not parts:
            parts.append(
                "No strong structural driver stands out in this overview yet."
                if not ar
                else "لا يظهر سائق هيكلي واضح في هذه النظرة العامة بعد."
            )
        return {
            "headline": (
                f"{label}: combined review of this scope"
                if not ar
                else f"{label}: مراجعة مجمّعة لهذا النطاق"
            ),
            "story": " ".join(parts),
            "captions": captions,
            "source": "template",
        }

    if page == "participation":
        if att is not None:
            headline = (
                f"Attendance is {att:g}% in this scope"
                if not ar
                else f"الحضور {att:g}% في هذا النطاق"
            )
            story = (
                f"Focus on curricula with the weakest attendance. "
                f"Current attendance is {att:g}%."
                if not ar
                else f"ركّز على المقررات ذات أضعف حضور. الحضور الحالي {att:g}%."
            )
        else:
            headline = (
                "Participation needs attention" if not ar else "المشاركة تحتاج انتباهاً"
            )
            story = (
                "Attendance or completion is below the review line in this scope."
                if not ar
                else "الحضور أو الإكمال دون خط المراجعة في هذا النطاق."
            )
        if alerts:
            story += (
                f" {len(alerts)} attendance alert(s) are open."
                if not ar
                else f" يوجد {len(alerts)} تنبيه حضور مفتوح."
            )
        return {
            "headline": headline,
            "story": story,
            "captions": captions,
            "source": "template",
        }

    if page == "courses":
        if pr is not None:
            headline = (
                f"Course pass rate is {pr:g}% in this scope"
                if not ar
                else f"معدل نجاح المقررات {pr:g}% في هذا النطاق"
            )
            story = (
                "Review the weakest courses and sections; no single course "
                "clearly explains the whole gap yet."
                if not ar
                else "راجع أضعف المقررات والشعب؛ لا يفسر مقرر واحد الفجوة بوضوح بعد."
            )
        else:
            headline = (
                f"{label}: review course outcomes"
                if not ar
                else f"{label}: راجع نتائج المقررات"
            )
            story = (
                "Course-level pass rates need a closer look in this scope."
                if not ar
                else "معدلات النجاح على مستوى المقررات تحتاج مراجعة في هذا النطاق."
            )
        return {
            "headline": headline,
            "story": story,
            "captions": captions,
            "source": "template",
        }

    if page == "exam-activity":
        headline = (
            f"{int(exams)} exams in scope"
            if exams is not None and not ar
            else (
                f"{int(exams)} امتحانًا في النطاق"
                if exams is not None
                else (
                    "Exam activity needs review"
                    if not ar
                    else "نشاط الامتحانات يحتاج مراجعة"
                )
            )
        )
        story_parts = []
        if pr is not None:
            story_parts.append(
                f"Pass rate across monitored exams is {pr:g}%."
                if not ar
                else f"معدل النجاح عبر الامتحانات المراقَبة {pr:g}%."
            )
        if students is not None:
            story_parts.append(
                f"{int(students)} students sat exams in this slice."
                if not ar
                else f"{int(students)} طالبًا أدوا الامتحانات في هذا النطاق."
            )
        if not story_parts:
            story_parts.append(
                "Look at recent exam volume and outcomes in this scope."
                if not ar
                else "راجع حجم الامتحانات الأخيرة ونتائجها في هذا النطاق."
            )
        return {
            "headline": str(headline),
            "story": " ".join(story_parts),
            "captions": captions,
            "source": "template",
        }

    if page == "performance":
        headline = (
            f"Student pass rate is {pr:g}%"
            if pr is not None and not ar
            else (
                f"معدل نجاح الطلاب {pr:g}%"
                if pr is not None
                else (
                    "Student performance needs review"
                    if not ar
                    else "أداء الطلاب يحتاج مراجعة"
                )
            )
        )
        story = (
            "Prioritize students and courses furthest below the pass mark."
            if not ar
            else "أعطِ الأولوية للطلاب والمقررات الأبعد عن درجة النجاح."
        )
        if alerts:
            story += (
                f" {len(alerts)} performance alert(s) are open."
                if not ar
                else f" يوجد {len(alerts)} تنبيه أداء مفتوح."
            )
        return {
            "headline": str(headline),
            "story": story,
            "captions": captions,
            "source": "template",
        }

    if page == "item-analysis":
        headline = (
            "Question patterns need review" if not ar else "أنماط الأسئلة تحتاج مراجعة"
        )
        story = (
            "Look at weak topics and unusual item difficulty in this scope."
            if not ar
            else "راجع الموضوعات الضعيفة وصعوبة البنود غير المعتادة."
        )
        if alerts:
            story += (
                f" {len(alerts)} item(s) are below the discrimination review line."
                if not ar
                else f" يوجد {len(alerts)} بندًا دون خط مراجعة التمييز."
            )
        if anomalies:
            story += (
                f" {len(anomalies)} unusual item pattern(s) accompany this."
                if not ar
                else f" تصاحب ذلك {len(anomalies)} نمط بند غير معتاد."
            )
        return {
            "headline": headline,
            "story": story,
            "captions": captions,
            "source": "template",
        }

    if page in ("integrity", "real-time"):
        headline = (
            "Integrity signals need review" if not ar else "إشارات النزاهة تحتاج مراجعة"
        )
        story = (
            "Focus on flagged attempts and unusual exam patterns in this scope."
            if not ar
            else "ركّز على المحاولات المعلّمة والأنماط غير المعتادة في هذا النطاق."
        )
        if anomalies:
            story += (
                f" {len(anomalies)} unusual pattern(s) were detected."
                if not ar
                else f" تم رصد {len(anomalies)} نمطًا غير معتاد."
            )
        return {
            "headline": headline,
            "story": story,
            "captions": captions,
            "source": "template",
        }

    if page in ("students", "student"):
        headline = (
            f"Student outcomes at {pr:g}% pass"
            if pr is not None and not ar
            else (
                f"نتائج الطلاب بمعدل نجاح {pr:g}%"
                if pr is not None
                else (
                    "Student directory needs review"
                    if not ar
                    else "دليل الطلاب يحتاج مراجعة"
                )
            )
        )
        story = (
            "Review students furthest below the pass mark in this scope."
            if not ar
            else "راجع الطلاب الأبعد عن درجة النجاح في هذا النطاق."
        )
        return {
            "headline": str(headline),
            "story": story,
            "captions": captions,
            "source": "template",
        }

    if page == "my-progress":
        return {
            "headline": ("Your progress snapshot" if not ar else "لمحة عن تقدمك"),
            "story": (
                "Review your weakest exams and topics against the class baseline."
                if not ar
                else "راجع أضعف امتحاناتك وموضوعاتك مقابل خط الأساس للصف."
            ),
            "captions": captions,
            "source": "template",
        }

    # Generic page fallback (still page-labeled, not a shared overview sentence).
    return {
        "headline": (
            f"{label}: review this surface" if not ar else f"{label}: راجع هذه الصفحة"
        ),
        "story": (
            "Thresholds or patterns need human review; no single driver stood out."
            if not ar
            else "العتبات أو الأنماط تحتاج مراجعة بشرية؛ لم يبرز سائق واحد."
        ),
        "captions": captions,
        "source": "template",
    }


def template_narrative(
    packet: FactPacket, language: str = "en", page: str = "overview"
) -> dict[str, Any]:
    from services.ai_pages import normalize_page, page_label

    page = normalize_page(page)
    label = page_label(page, language)

    if packet.no_structural_cause or not packet.drivers:
        return _empty_driver_narrative(packet, page, label, language)

    top = packet.drivers[0]
    metrics = packet.headline_metrics
    pr = metrics.get("passRate")
    att = metrics.get("attendance")
    ar = language == "ar" or str(language).startswith("ar")
    if page == "participation" and att is not None:
        headline = (
            f"Attendance is {att:g}% in this scope"
            if not ar
            else f"الحضور {att:g}% في هذا النطاق"
        )
    elif page == "courses":
        headline = (
            f"{top.label} is the main course-level concern"
            if not ar
            else f"{top.label} هو أبرز مقرر يحتاج انتباهاً"
        )
    elif page == "item-analysis":
        headline = (
            f"{top.label} is the weakest topic signal"
            if not ar
            else f"{top.label} هو أضعف إشارة موضوع"
        )
    else:
        headline = (
            f"{top.label} explains about {top.contribution_points:g} pts of the gap"
            if not ar
            else f"{top.label} يفسر حوالي {top.contribution_points:g} نقطة من الفجوة"
        )
    parts = []
    if page == "participation" and att is not None:
        parts.append(
            f"Attendance in this slice is {att:g}%."
            if not ar
            else f"الحضور في هذا النطاق {att:g}%."
        )
    elif pr is not None:
        parts.append(
            f"Pass rate in this slice is {pr:g}%."
            if not ar
            else f"معدل النجاح في هذا النطاق {pr:g}%."
        )
    parts.append(
        (
            f"The leading driver is {top.label} "
            f"({top.contribution_points:g} points contribution)."
        )
        if not ar
        else (
            f"المحرك الرئيسي هو {top.label} "
            f"(مساهمة {top.contribution_points:g} نقطة)."
        )
    )
    if len(packet.drivers) > 1:
        second = packet.drivers[1]
        parts.append(
            f"Next is {second.label} ({second.contribution_points:g} points)."
            if not ar
            else f"يليه {second.label} ({second.contribution_points:g} نقطة)."
        )
    if packet.anomalies and page in (
        "integrity",
        "real-time",
        "item-analysis",
        "exam-activity",
        "overview",
    ):
        parts.append(
            f"{len(packet.anomalies)} unusual patterns accompany these findings."
            if not ar
            else f"تصاحب هذه النتائج {len(packet.anomalies)} أنماط غير معتادة."
        )
    captions = {}
    for item in packet.impact_items[:6]:
        captions[item.id] = (
            f"About +{item.uplift_university:g} pts university pass rate if fixed"
            if not ar
            else (
                f"حوالي +{item.uplift_university:g} نقطة في معدل نجاح الجامعة "
                f"إذا عولج الأمر"
            )
        )
    return {
        "headline": headline,
        "story": " ".join(parts),
        "captions": captions,
        "source": "template",
    }


def validate_narrative(text: str, packet: FactPacket) -> bool:
    allowed = packet.all_numbers()
    # Also allow small integers like ranks and counts already in packet.
    for match in _NUMBER.finditer(text):
        raw = match.group(1)
        if raw in allowed:
            continue
        # Allow trailing .0 variants
        try:
            as_float = float(raw)
        except ValueError:
            return False
        if f"{as_float:g}" in allowed or str(int(as_float)) in allowed:
            continue
        return False
    return True


async def narrate_packet(
    packet: FactPacket,
    *,
    language: str = "en",
    style: str = "causal",
    page: str = "overview",
) -> dict[str, Any]:
    fallback = template_narrative(packet, language=language, page=page)
    try:
        from core.config import settings
        from rag.llm_client import chat_completion
    except Exception:
        return fallback
    if not settings.AI_NARRATIVE_ENABLED:
        return fallback

    payload = {
        "role": packet.role,
        "page": page,
        "style": style,
        "language": language,
        "metrics": packet.headline_metrics,
        "drivers": [d.__dict__ for d in packet.drivers],
        "rule_alerts": [a.__dict__ for a in packet.rule_alerts],
        "anomalies": [a.__dict__ for a in packet.anomalies],
        "impact": [i.__dict__ for i in packet.impact_items[:8]],
        "no_structural_cause": packet.no_structural_cause,
    }
    lang_note = (
        "Write every string in Arabic."
        if language == "ar" or str(language).startswith("ar")
        else "Write every string in English."
    )
    prompt = (
        "Return JSON only with keys headline, story (2-4 sentences), captions "
        "(object id->short caption). Use ONLY numbers present in the fact packet. "
        "Do not invent causes beyond drivers. Stay focused on the page topic. "
        "If no_structural_cause is true or drivers is empty, say plainly that no "
        "structural cause was found for this page. "
        f"{lang_note}\n"
        f"FACT_PACKET={json.dumps(payload, default=str)}"
    )
    for _ in range(2):
        try:
            raw = await chat_completion(
                [
                    {
                        "role": "system",
                        "content": "You narrate verified analytics. Never invent numbers.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end < 0:
                continue
            data = json.loads(raw[start : end + 1])
            text = f"{data.get('headline','')} {data.get('story','')} " + " ".join(
                str(v) for v in (data.get("captions") or {}).values()
            )
            if not validate_narrative(text, packet):
                continue
            data["source"] = "llm"
            return data
        except Exception:
            continue
    return fallback
