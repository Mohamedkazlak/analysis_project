"""Template AI layer over shared, filter-scoped analytics.

Insights, standings, warnings, and recommendations are all computed from
repository numbers, deterministically. An LLM is never the source of any of
those numbers. When configured, an LLM may reword the sentences afterward —
see the "Narration" note below — but every fact still comes from SQL.

Narration: the configured model is slow (a shared, remote, always-reasoning
instance), too slow to sit in the request/response path without either
blocking every card load or silently failing under a tight timeout. So the
fast, deterministic decision is computed and cached first and returned right
away, and narration (`rag.narrative`) runs afterward as a background task
that rewords the cached copy in place once it finishes. The frontend polls
briefly while `narrationStatus` is `"pending"`.
"""

from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

from core.config import settings
from core.locale import Language, entity, normalize_language, txt
from core.utils import PASS_MARK
from repositories.sql_filters import attempt_where
from schemas.auth import UserContext
from schemas.filters import AnalyticsFilters
from services import ai_cache
from services.ai_context import load_ai_context
from services.ai_evidence import build_evidence
from services.ai_rules import build_warnings
from rag.narrative import apply_llm_narratives, has_narratable_text, narration_enabled
from services.predictions import (
    comparison_place,
    get_standing_or_forecast,
    is_university_landing,
)

logger = logging.getLogger(__name__)

# Cache keys with a narration task currently running. Guards against
# scheduling a second background rewrite for the same decision while the
# first one is still in flight (e.g. two tabs polling the same scope).
_NARRATION_INFLIGHT: set[str] = set()


def _structured_recommendation(
    rec_id: str,
    kind: str,
    metric: str,
    value: Any,
    threshold: Any,
    text: str,
    source: str,
    evidence: list[dict],
    action: Optional[dict],
) -> dict:
    return {
        "id": rec_id,
        "kind": kind,
        "text": text,
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "basedOn": {"source": source, "evidence": evidence},
        "action": action,
        "confirmationRequired": action is not None,
    }


def _insight_from_context(
    role: str, data: dict[str, Any], language: Language = "en"
) -> Optional[dict]:
    if role == "student":
        return None

    if role in ("senior_management", "program_director"):
        overview = data.get("overview") or {}
        colleges = overview.get("passRateByCollege") or []
        courses = overview.get("passRateByCourse") or []
        if not colleges:
            return {
                "headline": txt(
                    language,
                    "No exam data in this scope yet",
                    "لا توجد بيانات امتحانات في هذا النطاق بعد",
                ),
                "body": txt(
                    language,
                    "There are no recorded attempts in this scope yet, so there is nothing to report on.",
                    "لا توجد محاولات مسجّلة في هذا النطاق بعد، لذلك لا يوجد ما يمكن الإبلاغ عنه.",
                ),
                "action": None,
            }
        weakest = min(colleges, key=lambda c: c["passRate"])
        weakest_course = min(courses, key=lambda c: c["passRate"]) if courses else None
        totals = overview.get("totals") or {}
        if (
            is_university_landing(role, data)
            and totals.get("passRate") is not None
            and totals.get("students") is not None
            and totals.get("attendance") is not None
        ):
            headline = txt(
                language,
                f"University student pass rate is {totals['passRate']}%",
                f"معدل نجاح طلاب الجامعة هو {totals['passRate']}%",
            )
            body = txt(
                language,
                f"Across {len(colleges)} colleges, {int(totals['students'])} students sat exams",
                f"عبر {len(colleges)} كليات، أدى {int(totals['students'])} طالبًا الامتحانات",
            )
            if totals.get("exams") is not None:
                body += txt(
                    language,
                    f" and {int(totals['exams'])} exams were administered",
                    f" وأُجري {int(totals['exams'])} امتحانًا",
                )
            body += txt(
                language,
                (
                    f". The university student pass rate is {totals['passRate']}% "
                    f"and attendance is {totals['attendance']}%."
                ),
                (
                    f". معدل نجاح طلاب الجامعة هو {totals['passRate']}% "
                    f"والحضور {totals['attendance']}%."
                ),
            )
            if len(colleges) > 1:
                weak = entity(language, weakest["college"])
                body += txt(
                    language,
                    (f" {weak} is the lowest college at " f"{weakest['passRate']}%."),
                    (f" {weak} هي أدنى كلية بمعدل " f"{weakest['passRate']}%."),
                )
            return {
                "headline": headline,
                "body": body,
                "action": {
                    "label": txt(
                        language, "Drill into curriculum", "التفصيل حسب المقرر"
                    ),
                    "to": "/courses",
                },
            }
        if len(colleges) == 1:
            weak = entity(language, weakest["college"])
            headline = txt(
                language,
                f"{weak} pass rate is {weakest['passRate']}%",
                f"معدل نجاح {weak} هو {weakest['passRate']}%",
            )
            body = txt(
                language,
                (
                    f"{weak} spans {weakest['courses']} curriculum with "
                    f"{weakest['participants']} students who sat exams this term, at a "
                    f"{weakest['passRate']}% student pass rate."
                ),
                (
                    f"{weak} يشمل {weakest['courses']} مقررًا مع "
                    f"{weakest['participants']} طالبًا أدوا الامتحانات هذا الفصل، "
                    f"بمعدل نجاح طلابي {weakest['passRate']}%."
                ),
            )
        else:
            place = comparison_place(role, data, language)
            weak = entity(language, weakest["college"])
            headline = txt(
                language,
                f"{weak} has the lowest pass rate in {place}",
                f"{weak} لديها أدنى معدل نجاح في {place}",
            )
            body = txt(
                language,
                (
                    f"Across the {len(colleges)} colleges in {place}, {weak} sits at "
                    f"{weakest['passRate']}% student pass — the lowest here, from "
                    f"{weakest['participants']} students."
                ),
                (
                    f"عبر {len(colleges)} كليات في {place}، تبلغ {weak} "
                    f"{weakest['passRate']}% نجاحًا طلابيًا — الأدنى هنا، من "
                    f"{weakest['participants']} طالبًا."
                ),
            )
        if weakest_course:
            body += txt(
                language,
                (
                    f" The weakest curriculum overall is {weakest_course['course']} at "
                    f"{weakest_course['passRate']}% pass."
                ),
                (
                    f" أضعف مقرر إجمالًا هو {weakest_course['course']} بمعدل نجاح "
                    f"{weakest_course['passRate']}%."
                ),
            )
        return {
            "headline": headline,
            "body": body,
            "action": {
                "label": txt(language, "Drill into curriculum", "التفصيل حسب المقرر"),
                "to": "/courses",
            },
        }

    if role == "academic_affairs":
        participation = data.get("participation") or {}
        performance = data.get("performance") or {}
        curricula = participation.get("attendanceByCurriculum") or []
        weakest_att = (
            min(curricula, key=lambda c: c["attendance"]) if curricula else None
        )
        below_pass = [
            r for r in performance.get("ranked") or [] if r["status"] == "Fail"
        ]
        if not weakest_att and not below_pass:
            return {
                "headline": txt(
                    language,
                    "No performance data in this scope yet",
                    "لا توجد بيانات أداء في هذا النطاق بعد",
                ),
                "body": txt(
                    language,
                    "There are no recorded attempts in this college yet.",
                    "لا توجد محاولات مسجّلة في هذه الكلية بعد.",
                ),
                "action": None,
            }
        parts_en = []
        parts_ar = []
        if below_pass:
            parts_en.append(
                f"{len(below_pass)} student(s) are currently below the {PASS_MARK}% pass mark"
            )
            parts_ar.append(
                f"{len(below_pass)} طالبًا دون درجة النجاح {PASS_MARK}% حاليًا"
            )
        if weakest_att:
            parts_en.append(
                f"{weakest_att['course']} has the weakest attendance in the college at "
                f"{weakest_att['attendance']}%"
            )
            parts_ar.append(
                f"{weakest_att['course']} لديها أضعف حضور في الكلية بنسبة "
                f"{weakest_att['attendance']}%"
            )
        if language == "ar":
            body = ". ".join(parts_ar) + "."
            headline = (
                f"{len(below_pass)} طلاب دون درجة النجاح هذا الفصل"
                if below_pass
                else f"حضور {weakest_att['course']} يحتاج انتباهًا"
            )
        else:
            body = ". ".join(p[0].upper() + p[1:] for p in parts_en) + "."
            headline = (
                f"{len(below_pass)} students below the pass mark this term"
                if below_pass
                else f"{weakest_att['course']} attendance needs attention"
            )
        return {
            "headline": headline,
            "body": body,
            "action": {
                "label": txt(language, "Open student performance", "فتح أداء الطلاب"),
                "to": "/performance",
            },
        }

    if role == "professor":
        sections = (data.get("courses") or {}).get("sections") or []
        items = data.get("items") or {}
        if not sections:
            return {
                "headline": txt(
                    language,
                    "No exam data in this scope yet",
                    "لا توجد بيانات امتحانات في هذا النطاق بعد",
                ),
                "body": txt(
                    language,
                    "There are no recorded attempts in your assigned curriculum yet.",
                    "لا توجد محاولات مسجّلة في مقرراتك المعيّنة بعد.",
                ),
                "action": None,
            }
        weakest_section = min(sections, key=lambda s: s["average"])
        strongest_section = max(sections, key=lambda s: s["average"])
        gap = round(strongest_section["average"] - weakest_section["average"], 1)
        if gap > 0 and weakest_section["section"] != strongest_section["section"]:
            body = txt(
                language,
                (
                    f"{weakest_section['section']} averages {weakest_section['average']}, "
                    f"{gap} points behind {strongest_section['section']} at "
                    f"{strongest_section['average']} on the same curriculum."
                ),
                (
                    f"متوسط {weakest_section['section']} هو {weakest_section['average']}، "
                    f"أقل بـ {gap} نقطة عن {strongest_section['section']} عند "
                    f"{strongest_section['average']} في المقرر ذاته."
                ),
            )
            headline = txt(
                language,
                f"{weakest_section['section']} trails {strongest_section['section']} by {gap} points",
                f"{weakest_section['section']} تتأخر عن {strongest_section['section']} بـ {gap} نقطة",
            )
        else:
            body = txt(
                language,
                f"{weakest_section['section']} averages {weakest_section['average']} across your curriculum.",
                f"متوسط {weakest_section['section']} هو {weakest_section['average']} عبر مقرراتك.",
            )
            headline = txt(
                language,
                f"{weakest_section['section']} is your current baseline section",
                f"{weakest_section['section']} هي شعبك المرجعية الحالية",
            )
        needs_review = items.get("needsReview") or []
        if needs_review:
            top = needs_review[0]
            body += txt(
                language,
                (
                    f" {top['exam']} question {top['number']} has a discrimination index of "
                    f"{top['discriminationIndex']}, the weakest in your curriculum."
                ),
                (
                    f" السؤال {top['number']} في {top['exam']} بمؤشر تمييز "
                    f"{top['discriminationIndex']}، وهو الأضعف في مقرراتك."
                ),
            )
        else:
            body += txt(
                language,
                " No graded item-level answers are recorded yet, so item analysis has nothing to flag.",
                " لا توجد إجابات على مستوى البنود بعد، لذلك لا يوجد ما يشير إليه تحليل البنود.",
            )
        return {
            "headline": headline,
            "body": body,
            "action": {
                "label": txt(language, "Compare sections", "مقارنة الشعب"),
                "to": "/performance",
            },
        }

    if role == "it_academic_integrity":
        report = data.get("integrity") or {}
        cases_raw = data.get("flagged") or []
        if not cases_raw:
            return {
                "headline": txt(
                    language,
                    "No flagged attempts right now",
                    "لا توجد محاولات معلّمة الآن",
                ),
                "body": txt(
                    language,
                    "No monitored attempts in this scope currently show anomalies.",
                    "لا تُظهر المحاولات المراقَبة في هذا النطاق شذوذات حاليًا.",
                ),
                "action": None,
            }
        cases = []
        for i, c in enumerate(cases_raw):
            n = len(c["evidence"])
            share = round(100 / n) if n else 0
            evidence = [{**e, "weight": share} for e in c["evidence"]]
            score = min(100, share * n)
            level = "High" if n >= 3 else "Medium" if n == 2 else "Low"
            cases.append(
                {
                    "id": f"case-{i + 1}",
                    "subject": c["student"],
                    "exam": c["exam"],
                    "level": level,
                    "score": score,
                    "evidence": evidence,
                }
            )
        top = cases_raw[0]
        top_flags = ", ".join(e["label"] for e in top["evidence"]).lower()
        return {
            "headline": txt(
                language,
                f"{report.get('flaggedCount', 0)} of {report.get('totalAttempts', 0)} monitored attempts flagged",
                f"{report.get('flaggedCount', 0)} من {report.get('totalAttempts', 0)} محاولة مراقَبة معلّمة",
            ),
            "body": txt(
                language,
                (
                    f"{report.get('flaggedCount', 0)} attempts in this scope show at least one anomaly. "
                    f"The highest-signal case is {top['student']} on {top['exam']}, flagged for {top_flags}."
                ),
                (
                    f"{report.get('flaggedCount', 0)} محاولات في هذا النطاق تُظهر شذوذًا واحدًا على الأقل. "
                    f"أعلى حالة إشارة هي {top['student']} في {top['exam']}، معلّمة بسبب {top_flags}."
                ),
            ),
            "action": {
                "label": txt(language, "Open case detail", "فتح تفاصيل الحالة"),
                "to": "/integrity",
            },
            "cases": cases,
        }

    return None


def _insight_for_page(
    role: str,
    data: dict[str, Any],
    page: str,
    language: Language = "en",
) -> Optional[dict]:
    """SQL-backed insight tailored to the dashboard page the user is on."""
    from services.ai_pages import normalize_page

    page = normalize_page(page)
    if role == "student" and page != "my-progress":
        return None

    if page == "overview":
        return _overview_combined_insight(role, data, language)

    if page == "participation":
        return _participation_page_insight(data, language) or _insight_from_context(
            role, data, language
        )

    if page in ("courses", "exam-activity"):
        return _courses_page_insight(
            data, language, page=page
        ) or _insight_from_context(role, data, language)

    if page == "performance" or page == "students":
        return _performance_page_insight(data, language) or _insight_from_context(
            role, data, language
        )

    if page == "item-analysis":
        return _items_page_insight(data, language) or _insight_from_context(
            role, data, language
        )

    if page in ("integrity", "real-time"):
        # Prefer the integrity role template when flagged data is present.
        integrity_insight = _insight_from_context(
            (
                "it_academic_integrity"
                if data.get("integrity") or data.get("flagged")
                else role
            ),
            data,
            language,
        )
        if integrity_insight:
            return integrity_insight
        return _insight_from_context(role, data, language)

    if page in ("student", "my-progress"):
        return _insight_from_context(role, data, language)

    return _insight_from_context(role, data, language)


def _overview_combined_insight(
    role: str, data: dict[str, Any], language: Language
) -> Optional[dict]:
    """One-card summary across every dataset loaded for the role."""
    base = _insight_from_context(role, data, language)
    extras_en: list[str] = []
    extras_ar: list[str] = []

    participation = data.get("participation") or {}
    att = participation.get("attendanceRate")
    if att is None:
        att = (data.get("overview") or {}).get("totals", {}).get("attendance")
    curricula = participation.get("attendanceByCurriculum") or []
    if att is not None:
        extras_en.append(f"Attendance is {att}%")
        extras_ar.append(f"الحضور {att}%")
    if curricula:
        weakest_att = min(curricula, key=lambda c: c["attendance"])
        extras_en.append(
            f"weakest attendance is {weakest_att['course']} at {weakest_att['attendance']}%"
        )
        extras_ar.append(
            f"أضعف حضور هو {weakest_att['course']} بنسبة {weakest_att['attendance']}%"
        )

    performance = data.get("performance") or {}
    below_pass = [
        r for r in performance.get("ranked") or [] if r.get("status") == "Fail"
    ]
    if below_pass:
        extras_en.append(f"{len(below_pass)} student(s) are below the pass mark")
        extras_ar.append(f"{len(below_pass)} طالبًا دون درجة النجاح")

    items = data.get("items") or {}
    needs_review = items.get("needsReview") or []
    if needs_review:
        top = needs_review[0]
        extras_en.append(
            f"{top['exam']} Q{top['number']} needs item review "
            f"(discrimination {top['discriminationIndex']})"
        )
        extras_ar.append(
            f"السؤال {top['number']} في {top['exam']} يحتاج مراجعة بند "
            f"(تمييز {top['discriminationIndex']})"
        )

    integrity = data.get("integrity") or {}
    if integrity.get("totalAttempts"):
        extras_en.append(
            f"{integrity.get('flaggedCount', 0)} of {integrity['totalAttempts']} "
            "monitored attempts are flagged"
        )
        extras_ar.append(
            f"{integrity.get('flaggedCount', 0)} من {integrity['totalAttempts']} "
            "محاولة مراقَبة معلّمة"
        )

    if not base and not extras_en:
        return None
    if not base:
        return {
            "headline": txt(
                language,
                "Overview of current academic signals",
                "نظرة عامة على الإشارات الأكاديمية الحالية",
            ),
            "body": (
                ". ".join(p[0].upper() + p[1:] for p in extras_en) + "."
                if language != "ar"
                else ". ".join(extras_ar) + "."
            ),
            "action": None,
        }

    if extras_en:
        body = base.get("body") or ""
        addition = (
            " ".join(p[0].upper() + p[1:] + "." for p in extras_en)
            if language != "ar"
            else " ".join(p + "." for p in extras_ar)
        )
        base = {**base, "body": (body + " " + addition).strip()}
    return base


def _participation_page_insight(
    data: dict[str, Any], language: Language
) -> Optional[dict]:
    participation = data.get("participation") or {}
    curricula = participation.get("attendanceByCurriculum") or []
    att = participation.get("attendanceRate")
    if att is None:
        att = (data.get("overview") or {}).get("totals", {}).get("attendance")
    if not curricula and att is None:
        return None
    if curricula:
        weakest = min(curricula, key=lambda c: c["attendance"])
        return {
            "headline": txt(
                language,
                f"{weakest['course']} has the weakest attendance at {weakest['attendance']}%",
                f"{weakest['course']} لديها أضعف حضور بنسبة {weakest['attendance']}%",
            ),
            "body": txt(
                language,
                (
                    f"Across {len(curricula)} curricula, {weakest['course']} sits at "
                    f"{weakest['attendance']}% attendance"
                    + (
                        f" while the scope average is {att}%."
                        if att is not None
                        else "."
                    )
                ),
                (
                    f"عبر {len(curricula)} مقررًا، تبلغ {weakest['course']} "
                    f"{weakest['attendance']}% حضورًا"
                    + (f" بينما متوسط النطاق {att}%." if att is not None else ".")
                ),
            ),
            "action": {
                "label": txt(language, "Open attendance", "فتح الحضور"),
                "to": "/participation",
            },
        }
    return {
        "headline": txt(
            language,
            f"Attendance is {att}% in this scope",
            f"الحضور {att}% في هذا النطاق",
        ),
        "body": txt(
            language,
            f"Scope attendance is currently {att}%. Drill into curricula for detail.",
            f"حضور النطاق حاليًا {att}%. فصّل حسب المقررات للمزيد.",
        ),
        "action": {
            "label": txt(language, "Open attendance", "فتح الحضور"),
            "to": "/participation",
        },
    }


def _courses_page_insight(
    data: dict[str, Any], language: Language, *, page: str
) -> Optional[dict]:
    overview = data.get("overview") or {}
    courses = overview.get("passRateByCourse") or []
    sections = (data.get("courses") or {}).get("sections") or []
    totals = overview.get("totals") or {}

    if courses:
        weakest = min(courses, key=lambda c: c["passRate"])
        headline = txt(
            language,
            f"{weakest['course']} has the lowest pass rate at {weakest['passRate']}%",
            f"{weakest['course']} لديها أدنى معدل نجاح بنسبة {weakest['passRate']}%",
        )
        body = txt(
            language,
            (
                f"Among {len(courses)} curricula, {weakest['course']} is lowest at "
                f"{weakest['passRate']}% pass"
                + (
                    f" versus a scope pass rate of {totals['passRate']}%."
                    if totals.get("passRate") is not None
                    else "."
                )
            ),
            (
                f"من بين {len(courses)} مقررًا، {weakest['course']} الأدنى بمعدل "
                f"{weakest['passRate']}% نجاح"
                + (
                    f" مقابل معدل نجاح النطاق {totals['passRate']}%."
                    if totals.get("passRate") is not None
                    else "."
                )
            ),
        )
        if page == "exam-activity" and totals.get("exams") is not None:
            body += txt(
                language,
                f" {int(totals['exams'])} exams were administered in this scope.",
                f" أُجري {int(totals['exams'])} امتحانًا في هذا النطاق.",
            )
        return {
            "headline": headline,
            "body": body,
            "action": {
                "label": txt(language, "Drill into curriculum", "التفصيل حسب المقرر"),
                "to": "/courses",
            },
        }

    if sections:
        weakest = min(sections, key=lambda s: s.get("passRate", s.get("average", 0)))
        rate = weakest.get("passRate", weakest.get("average"))
        return {
            "headline": txt(
                language,
                f"{weakest.get('section') or weakest.get('course')} is the weakest section at {rate}",
                f"{weakest.get('section') or weakest.get('course')} هي أضعف شعبة عند {rate}",
            ),
            "body": txt(
                language,
                f"Compare sections in this curriculum; lowest currently is "
                f"{weakest.get('section') or weakest.get('course')} at {rate}.",
                f"قارن الشعب في هذا المقرر؛ الأدنى حاليًا "
                f"{weakest.get('section') or weakest.get('course')} عند {rate}.",
            ),
            "action": {
                "label": txt(language, "Compare sections", "مقارنة الشعب"),
                "to": "/performance",
            },
        }
    return None


def _performance_page_insight(
    data: dict[str, Any], language: Language
) -> Optional[dict]:
    performance = data.get("performance") or {}
    ranked = performance.get("ranked") or []
    below_pass = [r for r in ranked if r.get("status") == "Fail"]
    overview = data.get("overview") or {}
    totals = overview.get("totals") or {}
    if below_pass:
        return {
            "headline": txt(
                language,
                f"{len(below_pass)} students below the pass mark this term",
                f"{len(below_pass)} طالبًا دون درجة النجاح هذا الفصل",
            ),
            "body": txt(
                language,
                (
                    f"{len(below_pass)} of {len(ranked)} listed students are currently "
                    f"below the {PASS_MARK}% pass mark"
                    + (
                        f". Scope pass rate is {totals['passRate']}%."
                        if totals.get("passRate") is not None
                        else "."
                    )
                ),
                (
                    f"{len(below_pass)} من {len(ranked)} طالبًا مدرجًا دون درجة النجاح "
                    f"{PASS_MARK}% حاليًا"
                    + (
                        f". معدل نجاح النطاق {totals['passRate']}%."
                        if totals.get("passRate") is not None
                        else "."
                    )
                ),
            ),
            "action": {
                "label": txt(language, "Open student performance", "فتح أداء الطلاب"),
                "to": "/performance",
            },
        }
    if totals.get("passRate") is not None:
        return {
            "headline": txt(
                language,
                f"Student pass rate is {totals['passRate']}%",
                f"معدل نجاح الطلاب هو {totals['passRate']}%",
            ),
            "body": txt(
                language,
                "No students are flagged below the pass mark in the current list.",
                "لا يوجد طلاب دون درجة النجاح في القائمة الحالية.",
            ),
            "action": {
                "label": txt(language, "Open student performance", "فتح أداء الطلاب"),
                "to": "/performance",
            },
        }
    return None


def _items_page_insight(data: dict[str, Any], language: Language) -> Optional[dict]:
    items = data.get("items") or {}
    needs_review = items.get("needsReview") or []
    if not needs_review:
        return {
            "headline": txt(
                language,
                "No items flagged for review",
                "لا بنود معلّمة للمراجعة",
            ),
            "body": txt(
                language,
                "Item analysis has no discrimination flags in this scope yet.",
                "تحليل البنود بلا إشارات تمييز في هذا النطاق بعد.",
            ),
            "action": None,
        }
    top = needs_review[0]
    return {
        "headline": txt(
            language,
            f"{top['exam']} question {top['number']} needs review",
            f"السؤال {top['number']} في {top['exam']} يحتاج مراجعة",
        ),
        "body": txt(
            language,
            (
                f"Discrimination index is {top['discriminationIndex']} on "
                f"{top.get('topic') or 'this item'}; {len(needs_review)} item(s) "
                "are queued for review."
            ),
            (
                f"مؤشر التمييز هو {top['discriminationIndex']} في "
                f"{top.get('topic') or 'هذا البند'}؛ {len(needs_review)} بندًا "
                "في قائمة المراجعة."
            ),
        ),
        "action": {
            "label": txt(language, "Open item analysis", "فتح تحليل البنود"),
            "to": "/item-analysis",
        },
    }


def _recommendations_from_context(
    role: str,
    data: dict[str, Any],
    insight_id: str,
    language: Language = "en",
) -> Optional[dict]:
    items: list[dict] = []

    if role == "student":
        dashboard = data.get("dashboard") or {}
        timeline = dashboard.get("scoreTimeline") or []
        if timeline:
            worst = min(timeline, key=lambda r: r["score"])
            delta = round(dashboard["average"] - dashboard["classAverage"], 1)
            term = (dashboard.get("termName") or "").strip()
            overall = dashboard.get("overallAverage")
            semester_label = (
                txt(language, f"{term} average", f"متوسط {term}")
                if term
                else txt(language, "This semester average", "متوسط هذا الفصل")
            )
            evidence_rows = [
                {
                    "label": semester_label,
                    "detail": f"{dashboard['average']}",
                },
                {
                    "label": txt(language, "Class average", "متوسط الصف"),
                    "detail": f"{dashboard['classAverage']}",
                },
            ]
            if overall is not None:
                evidence_rows.append(
                    {
                        "label": txt(language, "All-years average", "متوسط كل السنوات"),
                        "detail": f"{overall}",
                    }
                )
            semester_phrase = (
                txt(
                    language,
                    f"This semester ({term}) your average is {dashboard['average']}",
                    f"هذا الفصل ({term}) متوسطك هو {dashboard['average']}",
                )
                if term
                else txt(
                    language,
                    f"This semester your average is {dashboard['average']}",
                    f"هذا الفصل متوسطك هو {dashboard['average']}",
                )
            )
            items.append(
                _structured_recommendation(
                    "s1",
                    "guidance" if delta >= 0 else "action",
                    "average_vs_class",
                    dashboard["average"],
                    dashboard["classAverage"],
                    (
                        f"{semester_phrase}, "
                        + txt(
                            language,
                            f"{'above' if delta >= 0 else 'below'} the class average of "
                            f"{dashboard['classAverage']} by {abs(delta)} points",
                            f"{'أعلى' if delta >= 0 else 'أدنى'} من متوسط الصف "
                            f"{dashboard['classAverage']} بمقدار {abs(delta)} نقطة",
                        )
                        + (
                            txt(
                                language,
                                f". All-years average is {overall}",
                                f". متوسط كل السنوات هو {overall}",
                            )
                            if overall is not None
                            else ""
                        )
                    ),
                    txt(language, "Your real score history", "سجل درجاتك الفعلي"),
                    evidence_rows,
                    None,
                )
            )
            items.append(
                _structured_recommendation(
                    "s2",
                    "guidance",
                    "weakest_exam",
                    worst["score"],
                    PASS_MARK,
                    txt(
                        language,
                        f"Your weakest recorded exam is {worst['exam']} at {worst['score']}",
                        f"أضعف امتحان مسجّل لديك هو {worst['exam']} بدرجة {worst['score']}",
                    ),
                    txt(
                        language,
                        "Your real score timeline",
                        "الجدول الزمني الفعلي لدرجاتك",
                    ),
                    [
                        {
                            "label": worst["exam"],
                            "detail": txt(
                                language,
                                f"Score {worst['score']} vs class {worst['classAverage']}",
                                f"الدرجة {worst['score']} مقابل الصف {worst['classAverage']}",
                            ),
                        }
                    ],
                    {
                        "label": txt(language, "Open my progress", "فتح تقدمي"),
                        "to": "/my-progress",
                        "confirmTitle": txt(
                            language,
                            "Open your progress page?",
                            "فتح صفحة تقدمك؟",
                        ),
                        "confirmBody": txt(
                            language,
                            "Opens your personal dashboard for this exam.",
                            "يفتح لوحتك الشخصية لهذا الامتحان.",
                        ),
                        "confirmLabel": txt(language, "Open", "فتح"),
                    },
                )
            )
        return {"insightId": insight_id, "items": items} if items else None

    if role in ("senior_management", "program_director"):
        overview = data.get("overview") or {}
        colleges = overview.get("passRateByCollege") or []
        if colleges:
            weakest = min(colleges, key=lambda c: c["passRate"])
            weak = entity(language, weakest["college"])
            items.append(
                _structured_recommendation(
                    "m1",
                    "action",
                    "college_pass_rate",
                    weakest["passRate"],
                    PASS_MARK,
                    txt(
                        language,
                        f"{weak} pass rate is {weakest['passRate']}% — review curriculum calibration",
                        f"معدل نجاح {weak} هو {weakest['passRate']}% — راجع معايرة المقرر",
                    ),
                    txt(
                        language,
                        "Current pass rate by college",
                        "معدل النجاح الحالي حسب الكلية",
                    ),
                    [
                        {
                            "label": weak,
                            "detail": txt(
                                language,
                                f"{weakest['passRate']}% pass, {weakest['participants']} participants",
                                f"{weakest['passRate']}% نجاح، {weakest['participants']} مشاركًا",
                            ),
                        }
                    ],
                    {
                        "label": txt(
                            language,
                            "Open curriculum drill-down",
                            "فتح تفصيل المقررات",
                        ),
                        "to": "/courses",
                        "confirmTitle": txt(
                            language,
                            f"Open the {weak} drill-down?",
                            f"فتح تفصيل {weak}؟",
                        ),
                        "confirmBody": txt(
                            language,
                            "Opens the curriculum performance view filtered to this college. Nothing is shared externally.",
                            "يفتح عرض أداء المقررات مفلترًا لهذه الكلية. لا يُشارك شيء خارجيًا.",
                        ),
                        "confirmLabel": txt(language, "Open drill-down", "فتح التفصيل"),
                    },
                )
            )
        if role == "senior_management":
            integrity = data.get("integrity") or {}
            if integrity.get("totalAttempts"):
                items.append(
                    _structured_recommendation(
                        "m2",
                        "action" if integrity["flaggedCount"] else "guidance",
                        "flagged_attempts",
                        integrity["flaggedCount"],
                        0,
                        txt(
                            language,
                            f"{integrity['flaggedCount']} of {integrity['totalAttempts']} monitored attempts are flagged",
                            f"{integrity['flaggedCount']} من {integrity['totalAttempts']} محاولة مراقَبة معلّمة",
                        ),
                        txt(
                            language,
                            "Current integrity monitoring",
                            "مراقبة النزاهة الحالية",
                        ),
                        [
                            {
                                "label": txt(language, "Flagged", "معلّمة"),
                                "detail": txt(
                                    language,
                                    f"{integrity['flaggedCount']} of {integrity['totalAttempts']} attempts",
                                    f"{integrity['flaggedCount']} من {integrity['totalAttempts']} محاولة",
                                ),
                            }
                        ],
                        (
                            {
                                "label": txt(
                                    language, "Open case list", "فتح قائمة الحالات"
                                ),
                                "to": "/integrity",
                                "confirmTitle": txt(
                                    language,
                                    "Open the case list?",
                                    "فتح قائمة الحالات؟",
                                ),
                                "confirmBody": txt(
                                    language,
                                    "Opens the monitoring log. No case status changes.",
                                    "يفتح سجل المراقبة. لا تتغير حالات الحالات.",
                                ),
                                "confirmLabel": txt(
                                    language, "Open case list", "فتح قائمة الحالات"
                                ),
                            }
                            if integrity["flaggedCount"]
                            else None
                        ),
                    )
                )
        else:
            items_report = data.get("items") or {}
            if items_report.get("needsReview"):
                top = items_report["needsReview"][0]
                items.append(
                    _structured_recommendation(
                        "p2",
                        "action",
                        "discrimination_index",
                        top["discriminationIndex"],
                        0.2,
                        txt(
                            language,
                            f"{top['exam']} question {top['number']} flagged — schedule an item review with faculty",
                            f"السؤال {top['number']} في {top['exam']} معلّم — جدولة مراجعة بند مع أعضاء هيئة التدريس",
                        ),
                        txt(language, "Current item analysis", "تحليل البنود الحالي"),
                        [
                            {
                                "label": f"Q{top['number']}",
                                "detail": txt(
                                    language,
                                    f"Discrimination {top['discriminationIndex']}",
                                    f"التمييز {top['discriminationIndex']}",
                                ),
                            }
                        ],
                        {
                            "label": txt(
                                language, "Open item analysis", "فتح تحليل البنود"
                            ),
                            "to": "/item-analysis",
                            "confirmTitle": txt(
                                language, "Open item analysis?", "فتح تحليل البنود؟"
                            ),
                            "confirmBody": txt(
                                language,
                                "Opens item analysis for flagged questions. No items are published or retired.",
                                "يفتح تحليل البنود للأسئلة المعلّمة. لا يُنشر أو يُستبعد أي بند.",
                            ),
                            "confirmLabel": txt(language, "Open", "فتح"),
                        },
                    )
                )
        return {"insightId": insight_id, "items": items} if items else None

    if role == "academic_affairs":
        performance = data.get("performance") or {}
        participation = data.get("participation") or {}
        below_pass = [
            r for r in performance.get("ranked") or [] if r["status"] == "Fail"
        ]
        if below_pass:
            items.append(
                _structured_recommendation(
                    "a1",
                    "action",
                    "students_below_pass",
                    len(below_pass),
                    0,
                    txt(
                        language,
                        f"Follow up with {len(below_pass)} student(s) below the pass mark",
                        f"تابع مع {len(below_pass)} طالبًا دون درجة النجاح",
                    ),
                    txt(
                        language,
                        "Current student performance",
                        "أداء الطلاب الحالي",
                    ),
                    [
                        {
                            "label": txt(language, "Below pass", "دون النجاح"),
                            "detail": txt(
                                language,
                                f"{len(below_pass)} students this term",
                                f"{len(below_pass)} طالبًا هذا الفصل",
                            ),
                        }
                    ],
                    {
                        "label": txt(
                            language, "Open student performance", "فتح أداء الطلاب"
                        ),
                        "to": "/performance",
                        "confirmTitle": txt(
                            language,
                            "Open student performance?",
                            "فتح أداء الطلاب؟",
                        ),
                        "confirmBody": txt(
                            language,
                            "Opens the college performance view. No messages are sent to students.",
                            "يفتح عرض أداء الكلية. لا تُرسل رسائل إلى الطلاب.",
                        ),
                        "confirmLabel": txt(language, "Open", "فتح"),
                    },
                )
            )
        curricula = participation.get("attendanceByCurriculum") or []
        if curricula:
            weakest_att = min(curricula, key=lambda c: c["attendance"])
            items.append(
                _structured_recommendation(
                    "a2",
                    "action",
                    "curriculum_attendance",
                    weakest_att["attendance"],
                    90,
                    txt(
                        language,
                        f"Review {weakest_att['course']} attendance ({weakest_att['attendance']}%)",
                        f"راجع حضور {weakest_att['course']} ({weakest_att['attendance']}%)",
                    ),
                    txt(
                        language,
                        "Current attendance by curriculum",
                        "الحضور الحالي حسب المقرر",
                    ),
                    [
                        {
                            "label": weakest_att["course"],
                            "detail": txt(
                                language,
                                f"{weakest_att['attendance']}% attendance",
                                f"{weakest_att['attendance']}% حضور",
                            ),
                        }
                    ],
                    {
                        "label": txt(language, "Open attendance", "فتح الحضور"),
                        "to": "/participation",
                        "confirmTitle": txt(
                            language, "Open attendance?", "فتح الحضور؟"
                        ),
                        "confirmBody": txt(
                            language,
                            "Opens participation and attendance for every curriculum in the college.",
                            "يفتح المشاركة والحضور لكل مقرر في الكلية.",
                        ),
                        "confirmLabel": txt(language, "Open", "فتح"),
                    },
                )
            )
        return {"insightId": insight_id, "items": items} if items else None

    if role == "professor":
        sections = (data.get("courses") or {}).get("sections") or []
        items_report = data.get("items") or {}
        if sections:
            weakest_section = min(sections, key=lambda s: s["average"])
            items.append(
                _structured_recommendation(
                    "f1",
                    "action",
                    "section_average",
                    weakest_section["average"],
                    PASS_MARK,
                    txt(
                        language,
                        f"{weakest_section['section']} averages {weakest_section['average']} — consider a review session",
                        f"متوسط {weakest_section['section']} هو {weakest_section['average']} — فكّر في جلسة مراجعة",
                    ),
                    txt(
                        language,
                        "Current section performance",
                        "أداء الشعب الحالي",
                    ),
                    [
                        {
                            "label": weakest_section["section"],
                            "detail": txt(
                                language,
                                f"{weakest_section['average']} avg, {weakest_section['passRate']}% pass",
                                f"{weakest_section['average']} متوسط، {weakest_section['passRate']}% نجاح",
                            ),
                        }
                    ],
                    {
                        "label": txt(language, "Compare sections", "مقارنة الشعب"),
                        "to": "/performance",
                        "confirmTitle": txt(
                            language,
                            "Open the section comparison?",
                            "فتح مقارنة الشعب؟",
                        ),
                        "confirmBody": txt(
                            language,
                            "This opens section performance for your curriculum. No message is sent to students.",
                            "يفتح أداء الشعب لمقررك. لا تُرسل رسالة إلى الطلاب.",
                        ),
                        "confirmLabel": txt(
                            language, "Open comparison", "فتح المقارنة"
                        ),
                    },
                )
            )
        if items_report.get("needsReview"):
            top = items_report["needsReview"][0]
            items.append(
                _structured_recommendation(
                    "f2",
                    "action",
                    "discrimination_index",
                    top["discriminationIndex"],
                    0.2,
                    txt(
                        language,
                        f"Question {top['number']} on {top['exam']} flagged for review — low discrimination index",
                        f"السؤال {top['number']} في {top['exam']} معلّم للمراجعة — مؤشر تمييز منخفض",
                    ),
                    txt(language, "Current item analysis", "تحليل البنود الحالي"),
                    [
                        {
                            "label": f"Q{top['number']}",
                            "detail": txt(
                                language,
                                f"Discrimination {top['discriminationIndex']}",
                                f"التمييز {top['discriminationIndex']}",
                            ),
                        }
                    ],
                    {
                        "label": txt(
                            language, "Open in Item Analysis", "فتح في تحليل البنود"
                        ),
                        "to": "/item-analysis",
                        "confirmTitle": txt(
                            language,
                            "Open the flagged question?",
                            "فتح السؤال المعلّم؟",
                        ),
                        "confirmBody": txt(
                            language,
                            "Item Analysis opens filtered to this question. Nothing is changed or published.",
                            "يفتح تحليل البنود مفلترًا لهذا السؤال. لا يُغيّر أو يُنشر شيء.",
                        ),
                        "confirmLabel": txt(language, "Open question", "فتح السؤال"),
                    },
                )
            )
        return {"insightId": insight_id, "items": items} if items else None

    if role == "it_academic_integrity":
        report = data.get("integrity") or {}
        cases_raw = data.get("flagged") or []
        if cases_raw:
            top = cases_raw[0]
            items.append(
                _structured_recommendation(
                    "i1",
                    "action",
                    "integrity_signals",
                    len(top["evidence"]),
                    1,
                    txt(
                        language,
                        f"Recommended for review: {top['student']} / {top['exam']}",
                        f"موصى بالمراجعة: {top['student']} / {top['exam']}",
                    ),
                    txt(
                        language,
                        f"Fused from {len(top['evidence'])} real signal(s)",
                        f"مدموج من {len(top['evidence'])} إشارة فعلية",
                    ),
                    top["evidence"],
                    {
                        "label": txt(language, "Create case", "إنشاء حالة"),
                        "to": "/integrity",
                        "confirmTitle": txt(
                            language,
                            "Create an investigation case?",
                            "إنشاء حالة تحقيق؟",
                        ),
                        "confirmBody": txt(
                            language,
                            "Opens the case with the evidence above pre-attached and marked recommended for review. No finding is recorded and no one is notified.",
                            "يفتح الحالة مع الأدلة أعلاه مرفقة ومعلّمة كموصى بالمراجعة. لا يُسجّل أي استنتاج ولا يُبلَّغ أحد.",
                        ),
                        "confirmLabel": txt(language, "Create case", "إنشاء حالة"),
                    },
                )
            )
        if report.get("totalAttempts"):
            items.append(
                _structured_recommendation(
                    "i2",
                    "guidance",
                    "flagged_attempts",
                    report["flaggedCount"],
                    0,
                    txt(
                        language,
                        f"{report['flaggedCount']} of {report['totalAttempts']} monitored attempts are currently flagged",
                        f"{report['flaggedCount']} من {report['totalAttempts']} محاولة مراقَبة معلّمة حاليًا",
                    ),
                    txt(
                        language,
                        "Current integrity monitoring",
                        "مراقبة النزاهة الحالية",
                    ),
                    [
                        {
                            "label": txt(language, "Flagged", "معلّمة"),
                            "detail": txt(
                                language,
                                f"{report['flaggedCount']} of {report['totalAttempts']}",
                                f"{report['flaggedCount']} من {report['totalAttempts']}",
                            ),
                        }
                    ],
                    None,
                )
            )
        return {"insightId": insight_id, "items": items} if items else None

    return None


def _unavailable(
    message: str, status: str = "unavailable", language: Language = "en"
) -> dict:
    return {
        "insight": None,
        "prediction": None,
        "recommendations": None,
        "warnings": None,
        "evidence": None,
        "metadata": None,
        "validation": {"status": "not_run", "failures": 0},
        "dataStatus": "insufficient",
        "status": status,
        "message": message,
        "narrationStatus": "skipped",
    }


async def _data_version(db: asyncpg.Connection, filters: AnalyticsFilters) -> str:
    """Changes when attempts in this authorized scope change."""
    try:
        where_sql, args, _ = attempt_where(filters)
        value = await db.fetchval(
            f"""
            SELECT COALESCE(MAX(a.ended_at)::text, 'none') || ':' || COUNT(*)::text
            FROM v_exam_attempts a
            WHERE {where_sql}
            """,
            *args,
        )
        return str(value or "none")
    except Exception:
        logger.warning("AI data version lookup failed", exc_info=True)
        return "unknown"


def _attach_warnings(insight: Optional[dict], warnings: list[dict]) -> Optional[dict]:
    if insight is None:
        return None
    insight["warnings"] = [
        {"id": row["id"], "text": row["text"], "tone": row["tone"]} for row in warnings
    ] or None
    return insight


async def _compute_decision(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    insight_id: str,
    data_version: str,
    language: Language = "en",
    page: str = "overview",
) -> dict:
    from services.ai_pages import normalize_page, page_focus as _page_focus
    from services.ai_page_focus import (
        apply_page_to_decision_fields,
        filter_evidence,
        filter_recommendations,
        filter_warnings,
        focus_packet,
    )

    page = normalize_page(page)
    data = await load_ai_context(ctx, db, filters, page=page)
    evidence = filter_evidence(build_evidence(ctx.role, data), page)
    warnings = filter_warnings(
        build_warnings(ctx.role, evidence, data, language=language), page
    )
    insight = _attach_warnings(
        _insight_for_page(ctx.role, data, page, language), warnings
    )
    prediction = await get_standing_or_forecast(
        ctx, db, filters, data, language=language
    )
    recommendations = filter_recommendations(
        _recommendations_from_context(ctx.role, data, insight_id, language),
        page,
    )

    from services.ai_facts.packet import build_fact_packet, packet_to_decision_fields
    from services.ai_facts.narration import template_narrative

    packet = await build_fact_packet(
        ctx,
        db,
        filters,
        data,
        warnings=warnings or [],
        prediction=prediction,
        data_version=data_version,
        card_id=f"{page}:{insight_id}",
        language=language,
    )
    packet = focus_packet(packet, page)
    narrative = template_narrative(packet, language=language, page=page)
    # Prefer causal narrative when page-relevant drivers exist. Otherwise keep
    # the page-local SQL insight and mirror it into narrative (UI reads narrative
    # first) so cards do not all collapse to a renamed overview sentence.
    if insight and packet.drivers and narrative.get("headline"):
        insight = {
            **insight,
            "headline": narrative["headline"],
            "body": narrative.get("story") or insight.get("body"),
        }
    elif insight and not packet.drivers:
        narrative = {
            **narrative,
            "headline": insight.get("headline") or narrative.get("headline"),
            "story": insight.get("body") or narrative.get("story"),
            "source": narrative.get("source") or "template",
        }
    elif not insight and narrative.get("headline"):
        insight = {
            "headline": narrative["headline"],
            "body": narrative.get("story") or "",
            "action": None,
        }
    fact_fields = apply_page_to_decision_fields(
        packet_to_decision_fields(packet, narrative, language=language),
        page,
        language=language,
    )

    show_forecast = bool(_page_focus(page).get("show_forecast", True))

    return {
        "insight": insight,
        "prediction": prediction if show_forecast else None,
        "recommendations": recommendations,
        "warnings": warnings or None,
        "evidence": evidence or None,
        "metadata": {
            "role": ctx.role,
            "scopeId": ctx.scope_id,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "dataVersion": data_version,
            "filters": filters.model_dump(),
            "language": language,
            "page": page,
        },
        "validation": {"status": "not_run", "failures": 0},
        "dataStatus": "ready" if evidence else "insufficient",
        "status": "ok",
        "message": None,
        "narrationStatus": "skipped",
        **fact_fields,
    }


async def _narrate_and_recache(key: str, snapshot: dict) -> None:
    """Reword `snapshot` in place, in the background, then recache it.

    Runs after the deterministic result was already returned to the caller,
    so it can take as long as `AI_NARRATIVE_BACKGROUND_BUDGET_SECONDS` allows
    without any card waiting on it. Whatever sentences the model manages to
    reword before that budget runs out are kept; anything left over simply
    stays as the original, already-correct SQL sentence — never blank, never
    wrong, always grounded.
    """
    try:
        await asyncio.wait_for(
            apply_llm_narratives(snapshot),
            timeout=settings.AI_NARRATIVE_BACKGROUND_BUDGET_SECONDS,
        )
        # Optional fact-packet narration (JSON, validated).
        packet_dict = snapshot.get("factPacket")
        if packet_dict and settings.AI_NARRATIVE_ENABLED:
            from services.ai_facts.models import (
                Anomaly,
                Driver,
                FactPacket,
                ForecastStatus,
                ImpactItem,
                Provenance,
                RuleAlert,
            )
            from services.ai_facts.narration import narrate_packet

            fp = packet_dict
            packet = FactPacket(
                card_id=fp.get("card_id") or "ai-decision",
                role=fp.get("role") or "",
                scope_id=fp.get("scope_id"),
                slice=fp.get("slice") or {},
                data_version=fp.get("data_version") or "",
                headline_metrics=fp.get("headline_metrics") or {},
                drivers=[Driver(**d) for d in fp.get("drivers") or []],
                rule_alerts=[RuleAlert(**a) for a in fp.get("rule_alerts") or []],
                anomalies=[Anomaly(**a) for a in fp.get("anomalies") or []],
                impact_items=[ImpactItem(**i) for i in fp.get("impact_items") or []],
                forecast=(
                    ForecastStatus(**fp["forecast"]) if fp.get("forecast") else None
                ),
                provenance=(
                    Provenance(**fp["provenance"]) if fp.get("provenance") else None
                ),
                story_template=fp.get("story_template") or "",
                no_structural_cause=bool(fp.get("no_structural_cause")),
            )
            language = (snapshot.get("metadata") or {}).get("language") or "en"
            narr = await narrate_packet(packet, language=language)
            snapshot["narrative"] = narr
            if snapshot.get("insight") and narr.get("headline"):
                snapshot["insight"] = {
                    **snapshot["insight"],
                    "headline": narr["headline"],
                    "body": narr.get("story") or snapshot["insight"].get("body"),
                }
    except Exception:
        logger.warning("background AI narration did not finish in time", exc_info=True)
    finally:
        snapshot["narrationStatus"] = "done"
        ai_cache.set(key, snapshot)
        _NARRATION_INFLIGHT.discard(key)


def _schedule_narration(key: str, result: dict) -> None:
    if key in _NARRATION_INFLIGHT:
        return
    _NARRATION_INFLIGHT.add(key)
    # A private, mutated-in-place copy for the background task. `result`
    # itself is what gets returned to this caller and must stay untouched.
    asyncio.create_task(_narrate_and_recache(key, copy.deepcopy(result)))


async def get_ai_decision(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters,
    insight_id: str = "insight",
    language: Language | str = "en",
    page: str | None = "overview",
) -> dict:
    from services.ai_pages import normalize_page

    language = normalize_language(str(language))
    page = normalize_page(page)
    year_id = (
        await db.fetchval("SELECT id FROM academic_years WHERE is_current LIMIT 1")
        or ""
    )
    term_id = ""
    if year_id:
        term_id = (
            await db.fetchval(
                """
                SELECT id FROM terms
                WHERE academic_year_id = $1
                ORDER BY start_date DESC
                LIMIT 1
                """,
                year_id,
            )
            or ""
        )
    data_version = await _data_version(db, filters)
    key = ai_cache.make_cache_key(
        ctx,
        filters,
        academic_year_id=year_id,
        term_id=term_id,
        data_version=data_version,
        language=language,
        page=page,
    )
    cached = ai_cache.get(key)
    if cached is not None:
        return cached
    try:
        result = await asyncio.wait_for(
            _compute_decision(
                ctx,
                db,
                filters,
                insight_id,
                data_version,
                language=language,
                page=page,
            ),
            timeout=settings.AI_BUDGET_SECONDS,
        )
    except asyncio.TimeoutError:
        return _unavailable(
            txt(
                language,
                "AI analysis is taking longer than expected.",
                "تحليل الذكاء الاصطناعي يستغرق وقتًا أطول من المتوقع.",
            ),
            status="timeout",
            language=language,
        )
    except Exception:
        return _unavailable(
            txt(
                language,
                "AI analysis is temporarily unavailable.",
                "تحليل الذكاء الاصطناعي غير متاح مؤقتًا.",
            ),
            language=language,
        )

    if narration_enabled() and has_narratable_text(result):
        result["narrationStatus"] = "pending"
        # The "pending" placeholder must outlive the narration budget, or a
        # normal-TTL cache eviction would make a second request in the same
        # window recompute the decision and schedule a duplicate rewrite.
        ai_cache.set(
            key,
            result,
            ttl=max(
                settings.AI_CACHE_TTL_SECONDS,
                int(settings.AI_NARRATIVE_BACKGROUND_BUDGET_SECONDS) + 5,
            ),
        )
        _schedule_narration(key, result)
    else:
        result["narrationStatus"] = "skipped"
        ai_cache.set(key, result)
    return result


async def get_insight(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language | str = "en",
):
    decision = await get_ai_decision(
        ctx, db, filters or AnalyticsFilters(), language=language
    )
    return decision.get("insight")


async def get_prediction(
    ctx: UserContext,
    db: asyncpg.Connection,
    filters: AnalyticsFilters | None = None,
    language: Language | str = "en",
):
    decision = await get_ai_decision(
        ctx, db, filters or AnalyticsFilters(), language=language
    )
    return decision.get("prediction")


async def get_recommendations(
    ctx: UserContext,
    db: asyncpg.Connection,
    insight_id: str,
    filters: AnalyticsFilters | None = None,
    language: Language | str = "en",
):
    decision = await get_ai_decision(
        ctx, db, filters or AnalyticsFilters(), insight_id, language=language
    )
    return decision.get("recommendations")
