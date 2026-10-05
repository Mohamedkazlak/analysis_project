"""Role gate for the single chat endpoint.

`classify()` runs before the RAG engine. The live UserContext, not the JWT
role claim, is what the engine and the database use.
"""

import re

import asyncpg
from rag.question_sql import static_reply
from schemas.auth import UserContext

DataDomain = str

DOMAIN_ALLOW: dict[str, set[str]] = {
    "student": {"own_performance", "anonymized_cohort"},
    "professor": {
        "own_courses",
        "item_analysis",
        "exam_content",
        "grading_rationale",
        "anonymized_cohort",
        "named_students",
    },
    "it_academic_integrity": {
        "integrity_monitoring",
        "named_students",
        "anonymized_cohort",
        "institution_kpis",
    },
    "academic_affairs": {
        "named_students",
        "anonymized_cohort",
        "own_courses",
        "all_courses",
        "institution_kpis",
        "item_analysis",
    },
    # Staff KPI domains (university / college / course aggregates)
    "program_director": {
        "institution_kpis",
        "all_courses",
        "item_analysis",
        "exam_content",
        "grading_rationale",
        "integrity_monitoring",
        "named_students",
        "anonymized_cohort",
        "own_performance",
    },
    "senior_management": {
        "institution_kpis",
        "all_courses",
        "item_analysis",
        "exam_content",
        "grading_rationale",
        "integrity_monitoring",
        "named_students",
        "anonymized_cohort",
        "own_performance",
    },
}


# Fallback domain per role when no keyword rule matches. This must always be
# a domain present in that role's DOMAIN_ALLOW set below, otherwise the most
# generic, in-scope questions (including this app's own suggested prompts)
# get wrongly refused. "own_courses" used to be a blanket default regardless
# of role, but it isn't in senior_management's or program_director's allow
# set (they only have "all_courses"), so e.g. "Which college is weakest?"
# or "Which curriculum is weakest?" were being refused outright.
_DEFAULT_DOMAIN: dict[str, DataDomain] = {
    "student": "own_performance",
    "professor": "own_courses",
    "academic_affairs": "own_courses",
    "program_director": "all_courses",
    "senior_management": "all_courses",
    "it_academic_integrity": "integrity_monitoring",
}

# Org-level questions are institution KPIs for a student. A scoped COUNT(*) would
# only count the caller's own row and look like a real university / college total.
_STUDENT_HEADCOUNT = re.compile(
    r"how many students|number of students|كم\s*عدد\s*الطلاب|عدد\s*الطلاب",
    re.IGNORECASE,
)
_ORG_SCOPE = re.compile(
    r"\b(university|institution|sector|college|program|faculty|department)\b|"
    r"الجامع[ةه]|القطاع|الكلي[ةه]|البرنامج",
    re.IGNORECASE,
)
_PERSONAL_RECORD = re.compile(
    r"\b("
    r"my score|my scores|my average|my grade|my grades|my performance|"
    r"my topics|how am i|am i doing|compared to (?:the )?class|"
    r"class average|my cohort"
    r")\b|درجاتي|معدلي|أدائي|نتائجي",
    re.IGNORECASE,
)

STUDENT_OUT_OF_SCOPE = (
    "You are only allowed to ask about your own data — your scores, topics, "
    "or how you compare with the anonymized class average."
)

# Named sectors in the org tree. Matching is deterministic so a sector dean's
# cross-sector question is refused before the model can treat it as smalltalk.
_SECTOR_ALIASES: dict[str, tuple[str, ...]] = {
    "sec-engineering": (
        "engineering and basic",
        "basic & applied sciences",
        "basic and applied sciences",
        "engineering sector",
        "eng sector",
        "sec-engineering",
        "eng-sec",
    ),
    "sec-health": (
        "health sciences",
        "health sector",
        "sec-health",
        "hlth-sec",
    ),
    "sec-humanities": (
        "literature, arts and humanities",
        "literature arts and humanities",
        "arts and humanities",
        "humanities sector",
        "literature sector",
        "sec-humanities",
        "hum-sec",
    ),
}
_BARE_SECTOR_WORD: dict[str, re.Pattern[str]] = {
    "sec-engineering": re.compile(r"\bengineering\b", re.IGNORECASE),
    "sec-health": re.compile(r"\bhealth\b", re.IGNORECASE),
    "sec-humanities": re.compile(r"\b(?:humanities|literature)\b", re.IGNORECASE),
}
_MENTIONS_SECTOR = re.compile(r"\bsectors?\b|القطاع", re.IGNORECASE)
_OTHER_SECTOR = re.compile(
    r"\b(?:other|another|different|every|all|each)\s+sectors?\b|"
    r"\bsectors?\s+other\s+than\b|"
    r"خارج\s*قطاعي|قطاع\s*آخر|"
    r"كل\s*(?:ال)?قطاع|"
    r"حالة\s*(?:كل|لكل)\s*(?:ال)?قطاع|"
    r"جميع\s*(?:ال)?قطاع",
    re.IGNORECASE,
)


def _norm_org(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _sectors_named_in(question: str) -> set[str]:
    """Sector ids explicitly named in the question (own or foreign)."""
    q = _norm_org(question)
    hits: set[str] = set()
    for sector_id, aliases in _SECTOR_ALIASES.items():
        if any(alias in q for alias in aliases):
            hits.add(sector_id)
    # Bare words like "engineering" count when the question is about a sector.
    if _MENTIONS_SECTOR.search(q):
        for sector_id, pattern in _BARE_SECTOR_WORD.items():
            if pattern.search(q):
                hits.add(sector_id)
    return hits


def sector_dean_out_of_scope(ctx: UserContext, question: str) -> str | None:
    """Refuse when a sector dean asks about another named sector."""
    if ctx.role != "senior_management" or ctx.scope_level != "sector":
        return None
    own = (ctx.sector_id or "").strip()
    if not own:
        return None
    own_name = (ctx.sector_name or "").strip() or "your own sector"
    if _OTHER_SECTOR.search(question or ""):
        return (
            f"I can only help with your sector — {own_name}. "
            "I can't share another sector's data."
        )
    foreign = _sectors_named_in(question) - {own}
    if not foreign:
        return None
    return (
        f"I can only help with your sector — {own_name}. "
        "I can't share another sector's data."
    )


def _student_org_level_question(question: str) -> bool:
    """True when a student asks about university / sector / college aggregates."""
    if not _ORG_SCOPE.search(question):
        return False
    if _PERSONAL_RECORD.search(question):
        return False
    return True


_REPORT_QUESTION = re.compile(
    r"("
    r"\breport\b|\boverview\b|\bsummary\b|\bstate of\b|\bhow is the university\b|"
    r"university (?:status|performance|health)|"
    r"تقرير|حالة\s*الجامعة|نظرة\s*عامة|ملخص|"
    r"كيف\s*(?:حال|أداء)?\s*الجامعة|وضع\s*الجامعة"
    r")",
    re.I,
)
_SECTOR_REPORT = re.compile(
    r"("
    r"\beach\s+sector\b|\bevery\s+sector\b|\ball\s+sectors?\b|"
    r"\bper\s+sector\b|\bby\s+sector\b|\bsector(?:s)?\s+(?:status|report|overview)\b|"
    r"\breport\b.*\bsectors?\b|\bsectors?\b.*\breport\b|"
    r"كل\s*(?:ال)?قطاع|لكل\s*(?:ال)?قطاع|حسب\s*(?:ال)?قطاع|"
    r"حالة\s*(?:كل|لكل)?\s*(?:ال)?قطاع|تقرير\b.*قطاع|قطاع.*تقرير|"
    r"جميع\s*(?:ال)?قطاع"
    r")",
    re.I,
)
_COLLEGE_REPORT = re.compile(
    r"("
    r"\beach\s+college\b|\bevery\s+college\b|\ball\s+colleges?\b|"
    r"\bper\s+college\b|\bby\s+college\b|"
    r"كل\s*(?:ال)?كلي(?:ة|ات)|لكل\s*(?:ال)?كلي(?:ة|ات)|حسب\s*(?:ال)?كلي(?:ة|ات)|"
    r"حالة\s*(?:كل|لكل)?\s*(?:ال)?كلي(?:ة|ات)"
    r")",
    re.I,
)


def looks_like_overview_report(question: str) -> bool:
    return bool(_REPORT_QUESTION.search(question or ""))


def report_focus(question: str) -> str:
    """Which grain a broad report question is asking for."""
    q = question or ""
    if _SECTOR_REPORT.search(q):
        return "sector"
    if _COLLEGE_REPORT.search(q):
        return "college"
    return "university"


async def _visible_sectors(
    ctx: UserContext, db: asyncpg.Connection
) -> list[dict[str, str]]:
    """Sectors the caller may see in a deterministic report."""
    if ctx.role == "senior_management" and ctx.scope_level == "sector":
        if not ctx.sector_id:
            return []
        return [
            {
                "id": ctx.sector_id,
                "name": (ctx.sector_name or ctx.sector_id),
            }
        ]
    rows = await db.fetch(
        """
        SELECT id, name
        FROM org_units
        WHERE level = 'sector'
        ORDER BY name
        """
    )
    return [{"id": r["id"], "name": r["name"]} for r in rows]


async def _overview_report_answer(
    ctx: UserContext,
    db: asyncpg.Connection,
    *,
    language: str = "en",
    focus: str = "university",
) -> dict | None:
    """Deterministic brief for broad report questions (university / sector / college)."""
    if ctx.role not in (
        "senior_management",
        "program_director",
        "academic_affairs",
    ):
        return None

    from core.locale import entity, normalize_language
    import repositories.management as mgmt_repo
    from schemas.filters import AnalyticsFilters

    lang = normalize_language(language)
    ar = lang == "ar"

    if focus == "sector":
        sectors = await _visible_sectors(ctx, db)
        if not sectors:
            return None
        lines: list[str] = [
            (
                "ملخص حالة كل قطاع ضمن نطاق صلاحياتك:"
                if ar
                else "Sector status brief in your authorized scope:"
            )
        ]
        sector_metrics: list[dict] = []
        for sector in sectors:
            overview = await mgmt_repo.get_management_overview(
                ctx,
                db,
                AnalyticsFilters(sector_id=sector["id"]),
                language=lang,
            )
            totals = overview.get("totals") or {}
            colleges = overview.get("passRateByCollege") or []
            name = entity(lang, sector.get("name"))
            pass_rate = totals.get("passRate")
            attendance = totals.get("attendance")
            students = totals.get("students")
            exams = totals.get("exams")
            ranked = sorted(
                [c for c in colleges if c.get("passRate") is not None],
                key=lambda c: float(c["passRate"]),
            )
            weakest = ranked[0] if ranked else None
            lines.append("")
            lines.append(f"**{name}**")
            if pass_rate is not None:
                lines.append(
                    f"- معدل النجاح: {pass_rate}%"
                    if ar
                    else f"- Pass rate: {pass_rate}%"
                )
            if attendance is not None:
                lines.append(
                    f"- الحضور: {attendance}%" if ar else f"- Attendance: {attendance}%"
                )
            if students is not None:
                lines.append(
                    f"- الطلاب المسجلون: {int(students)}"
                    if ar
                    else f"- Enrolled students: {int(students)}"
                )
            if exams is not None:
                lines.append(
                    f"- عدد الامتحانات: {int(exams)}"
                    if ar
                    else f"- Exams administered: {int(exams)}"
                )
            if weakest is not None:
                w_name = entity(lang, weakest.get("college") or weakest.get("name"))
                lines.append(
                    f"- أدنى كلية: {w_name} ({weakest['passRate']}%)"
                    if ar
                    else f"- Lowest college: {w_name} ({weakest['passRate']}%)"
                )
            sector_metrics.append(
                {
                    "sector": name,
                    "passRate": pass_rate,
                    "attendance": attendance,
                    "students": students,
                    "exams": exams,
                }
            )
        lines.append("")
        lines.append(
            "هذا ملخص من البيانات الحالية حسب القطاع، وليس تقريرًا تنفيذيًا رسميًا."
            if ar
            else "This is a current-data brief by sector, not a formal executive report."
        )
        return {
            "text": "\n".join(lines),
            "blocked": False,
            "objects": [
                {
                    "type": "comparison",
                    "title": "ملخص القطاعات" if ar else "Sector brief",
                    "data": {"sectors": sector_metrics},
                }
            ],
        }

    from services.ai_context import load_ai_context

    data = await load_ai_context(ctx, db, AnalyticsFilters(), page="overview")
    overview = data.get("overview") or {}
    totals = overview.get("totals") or {}
    colleges = overview.get("passRateByCollege") or []
    if totals.get("passRate") is None and not colleges:
        return None

    lines = []
    if focus == "college":
        lines.append(
            "ملخص حالة الكليات ضمن نطاق صلاحياتك:"
            if ar
            else "College status brief in your authorized scope:"
        )
    else:
        lines.append(
            "ملخص حالة الجامعة ضمن نطاق صلاحياتك:"
            if ar
            else "University status brief in your authorized scope:"
        )

    if focus != "college":
        if totals.get("passRate") is not None:
            lines.append(
                f"- معدل النجاح: {totals['passRate']}%"
                if ar
                else f"- Pass rate: {totals['passRate']}%"
            )
        if totals.get("attendance") is not None:
            lines.append(
                f"- الحضور: {totals['attendance']}%"
                if ar
                else f"- Attendance: {totals['attendance']}%"
            )
        if totals.get("students") is not None:
            lines.append(
                f"- الطلاب المسجلون: {int(totals['students'])}"
                if ar
                else f"- Enrolled students: {int(totals['students'])}"
            )
        if totals.get("exams") is not None:
            lines.append(
                f"- عدد الامتحانات: {int(totals['exams'])}"
                if ar
                else f"- Exams administered: {int(totals['exams'])}"
            )

    if colleges:
        ranked = sorted(
            [c for c in colleges if c.get("passRate") is not None],
            key=lambda c: float(c["passRate"]),
        )
        if ranked and focus != "college":
            weakest = ranked[0]
            strongest = ranked[-1]
            w_name = entity(lang, weakest.get("college") or weakest.get("name"))
            s_name = entity(lang, strongest.get("college") or strongest.get("name"))
            lines.append(
                f"- أدنى كلية: {w_name} ({weakest['passRate']}%)"
                if ar
                else f"- Lowest college: {w_name} ({weakest['passRate']}%)"
            )
            if strongest is not weakest:
                lines.append(
                    f"- أعلى كلية: {s_name} ({strongest['passRate']}%)"
                    if ar
                    else f"- Highest college: {s_name} ({strongest['passRate']}%)"
                )
        lines.append("حسب الكلية:" if ar else "By college:")
        for row in ranked:
            name = entity(lang, row.get("college") or row.get("name"))
            extra = ""
            if focus == "college":
                attendance = row.get("attendance")
                students = row.get("students")
                bits = [f"{row['passRate']}%"]
                if attendance is not None:
                    bits.append(
                        f"حضور {attendance}%" if ar else f"attendance {attendance}%"
                    )
                if students is not None:
                    bits.append(
                        f"{int(students)} طالب" if ar else f"{int(students)} students"
                    )
                extra = " · ".join(bits)
                lines.append(f"  · {name}: {extra}")
            else:
                lines.append(f"  · {name}: {row['passRate']}%")

    lines.append(
        "هذا ملخص من البيانات الحالية، وليس تقريرًا تنفيذيًا رسميًا."
        if ar
        else "This is a current-data brief, not a formal executive report."
    )
    title = (
        ("ملخص الكليات" if ar else "College brief")
        if focus == "college"
        else ("ملخص الجامعة" if ar else "University brief")
    )
    return {
        "text": "\n".join(lines),
        "blocked": False,
        "objects": [
            {
                "type": "metric",
                "title": title,
                "data": {
                    "passRate": totals.get("passRate"),
                    "attendance": totals.get("attendance"),
                    "students": totals.get("students"),
                    "exams": totals.get("exams"),
                    "focus": focus,
                },
            }
        ],
    }


def classify(question: str, role: str) -> DataDomain:
    q = question.lower()
    asks_about_person = bool(
        re.search(
            r"\b(who|whose|which student|student s-?\d+|top student|name of)\b", q
        )
    )
    default = _DEFAULT_DOMAIN.get(role, "own_courses")
    if role == "student" and _student_org_level_question(q):
        return "institution_kpis"
    if role == "student" and re.search(
        r"\b(all students|every student|other students|another student|all grades)\b",
        q,
    ):
        return "named_students"
    if re.search(
        r"\b(ip|login|device|anomal|cheat|similar|flag|suspicio|monitor)\b", q
    ):
        return "integrity_monitoring"
    if re.search(r"\b(rubric|marking|grading rationale|model answer|answer key)\b", q):
        return "grading_rationale"
    if re.search(r"\b(question text|item bank|exam content|show me the question)\b", q):
        return "exam_content"
    if re.search(r"\b(discrimination|difficulty|item analysis|distractor)\b", q):
        return "item_analysis"
    if looks_like_overview_report(question) or re.search(
        r"\b(department|platform|institution|university-wide|term kpi|university|جامعة|كليات)\b",
        q,
    ):
        return "institution_kpis"
    if asks_about_person:
        return "named_students"
    if re.search(r"\b(class average|cohort|compared to others|peers)\b", q):
        return "anonymized_cohort"
    if re.search(r"\b(course|section|exam|curriculum|college|program|كلية|مقرر)\b", q):
        return default
    return default


def refusal_for(role: str, domain: DataDomain) -> str:
    if role == "student" and domain == "institution_kpis":
        return STUDENT_OUT_OF_SCOPE
    if role == "student" and domain == "named_students":
        return (
            "I can't share another student's name, score or personal data. I can "
            "compare you against the anonymized class average instead — want that?"
        )
    if role == "professor" and domain == "all_courses":
        return (
            "That covers courses outside the sections assigned to you. Ask your "
            "administrator to enable platform-wide access if you need it."
        )
    if role == "it_academic_integrity" and domain in (
        "exam_content",
        "grading_rationale",
    ):
        return (
            "Integrity access covers monitoring signals only — raw exam content "
            "and grading rationale aren't available here."
        )
    return "That data is outside what your role is authorized to see, so I can't answer it."


def _activity(step_id: str, label: str) -> dict:
    return {"id": step_id, "label": label, "done": True}


async def get_chat_answer(
    ctx: UserContext,
    db: asyncpg.Connection,
    question: str,
    pool=None,
    *,
    card_id: str | None = None,
    slice_ids: dict | None = None,
    item_id: str | None = None,
    language: str | None = None,
) -> dict:
    """Domain gate, then analytics / policy / RAG. There is one chat path.

    Handoff fields are ids only. The server never trusts client-supplied facts.
    """
    from rag.chat_engine import answer_question
    from services.policy_rag import (
        format_policy_context,
        looks_like_policy_question,
        retrieve_policies,
    )
    from services.what_if import (
        explain_what_if,
        localize_what_if_result,
        parse_what_if_intent,
        run_what_if_from_overview,
    )

    activities: list[dict] = [_activity("question", "Analyzing your question")]
    objects: list[dict] = []
    sources: list[dict] = []
    open_issues: list[str] = []
    from core.locale import normalize_language, txt

    lang = normalize_language(language)

    filters = None
    if card_id or item_id or slice_ids:
        from repositories.accounts import validate_analytics_filters
        from schemas.filters import AnalyticsFilters

        filters = AnalyticsFilters.from_query(
            (slice_ids or {}).get("sectorId"),
            (slice_ids or {}).get("collegeId"),
            (slice_ids or {}).get("curriculumId"),
            (slice_ids or {}).get("studentId"),
            (slice_ids or {}).get("professorId"),
            (slice_ids or {}).get("academicYearId"),
            (slice_ids or {}).get("termId"),
        )
        try:
            await validate_analytics_filters(ctx, db, filters, require_complete=False)
            activities.append(_activity("scope", "Validated card scope"))
        except Exception:
            return {
                "text": txt(
                    lang,
                    "That card slice is outside your authorized scope.",
                    "نطاق هذه البطاقة خارج صلاحياتك.",
                ),
                "blocked": True,
                "activities": activities,
                "openIssues": open_issues or None,
            }

    reply = static_reply(
        question,
        name=ctx.name,
        display_role=ctx.display_role,
        language=lang,
    )
    if reply is not None:
        return {
            "text": reply,
            "blocked": False,
            "activities": activities,
            "openIssues": open_issues or None,
        }

    sector_refusal = sector_dean_out_of_scope(ctx, question)
    if sector_refusal is not None:
        from rag.chat_engine import _log

        await _log(pool, ctx, question, None, None, "blocked", 0, True)
        return {
            "text": sector_refusal,
            "blocked": True,
            "activities": activities,
            "openIssues": open_issues or None,
        }

    # Policy / document questions: retrieve corpus before (or instead of) SQL.
    policy_docs: list[dict] = []
    if looks_like_policy_question(question):
        try:
            policy_docs = await retrieve_policies(db, ctx, question, language=lang)
            if policy_docs:
                activities.append(_activity("policy", "Retrieved relevant policy"))
                for doc in policy_docs:
                    objects.append(
                        {
                            "type": "policy",
                            "title": doc["title"],
                            "data": doc,
                        }
                    )
                    sources.append(
                        {
                            "type": "rag_document",
                            "id": doc["id"],
                            "title": doc["title"],
                        }
                    )
        except Exception:
            open_issues.append("Policy retrieval unavailable for this request.")

    # What-if: deterministic simulation from authorized overview metrics.
    intent = parse_what_if_intent(question, language=lang)
    if intent and intent.get("kind") != "unsupported":
        from schemas.filters import AnalyticsFilters
        from services.ai_context import load_ai_context

        scope_filters = filters or AnalyticsFilters()
        try:
            data = await load_ai_context(ctx, db, scope_filters, page="overview")
            activities.append(_activity("metrics", "Calculated performance metrics"))
            overview = data.get("overview") or {}
            sim = run_what_if_from_overview(intent, overview)
            if sim is None:
                return {
                    "text": txt(
                        lang,
                        (
                            "I could not run that what-if with the authorized data in "
                            "this scope. Name a known course code and a target pass rate "
                            "(for example: What if AIM303 reaches 70%?)."
                        ),
                        (
                            "تعذّر تشغيل سيناريو ماذا لو بالبيانات المصرّح بها في هذا النطاق. "
                            "اذكر رمز مقرر معروف ومعدل نجاح مستهدف "
                            "(مثال: ماذا لو وصل AIM303 إلى 70%؟)."
                        ),
                    ),
                    "blocked": False,
                    "activities": activities,
                    "objects": objects or None,
                    "sources": sources or None,
                    "openIssues": open_issues or None,
                }
            activities.append(
                _activity(
                    "whatif",
                    txt(lang, "Calculated what-if impact", "تم حساب أثر ماذا لو"),
                )
            )
            sim = localize_what_if_result(sim, language=lang)
            text = explain_what_if(sim, language=lang)
            objects.append(
                {
                    "type": "what_if",
                    "title": txt(lang, "What-if simulation", "محاكاة ماذا لو"),
                    "data": sim,
                }
            )
            activities.append(_activity("analysis", "Preparing analysis"))
            return {
                "text": text,
                "blocked": False,
                "activities": activities,
                "objects": objects,
                "sources": sources or None,
                "openIssues": open_issues or None,
            }
        except Exception:
            open_issues.append("What-if calculation failed; falling back to chat.")

    if intent and intent.get("kind") == "unsupported":
        return {
            "text": (
                intent.get("reason")
                or txt(
                    lang,
                    (
                        "That what-if scenario is not supported. Try a course pass-rate "
                        "target, weakest-course-to-average, or college uplift in points."
                    ),
                    (
                        "سيناريو ماذا لو هذا غير مدعوم. جرّب هدف معدل نجاح لمقرر، "
                        "أو أضعف مقرر إلى المتوسط، أو رفع نقاط للكلية."
                    ),
                )
            ),
            "blocked": False,
            "activities": activities,
            "objects": objects or None,
            "sources": sources or None,
            "openIssues": open_issues or None,
        }

    # Broad report questions: answer from authorized overview SQL by grain
    # (university / sector / college), not free-form LLM SQL.
    focus = report_focus(question)
    if looks_like_overview_report(question) or focus in ("sector", "college"):
        brief = await _overview_report_answer(ctx, db, language=lang, focus=focus)
        if brief is not None:
            activities.append(_activity("metrics", "Calculated performance metrics"))
            activities.append(_activity("analysis", "Preparing analysis"))
            return {
                **brief,
                "activities": activities,
                "objects": (objects or []) + (brief.get("objects") or []),
                "sources": sources or None,
                "openIssues": open_issues or None,
            }

    domain = classify(question, ctx.role)
    allowed = DOMAIN_ALLOW.get(ctx.role, set())
    if domain not in allowed:
        from rag.chat_engine import _log

        await _log(pool, ctx, question, None, None, "blocked", 0, True)
        # Policy-only answers are still allowed when documents were retrieved.
        if policy_docs:
            text = "Based on retrieved policy documents:\n\n" + "\n\n".join(
                f"**{d['title']}** ({d.get('effectiveDate')})\n{d['snippet']}"
                for d in policy_docs
            )
            activities.append(_activity("analysis", "Preparing analysis"))
            return {
                "text": text,
                "blocked": False,
                "activities": activities,
                "objects": objects,
                "sources": sources,
                "openIssues": open_issues or None,
            }
        return {
            "text": refusal_for(ctx.role, domain),
            "blocked": True,
            "activities": activities,
            "openIssues": open_issues or None,
        }

    # Enrich the question with policy excerpts when both SQL and docs apply.
    enriched = question
    if policy_docs:
        enriched = f"{question}\n\n{format_policy_context(policy_docs)}"

    if card_id or filters is not None:
        activities.append(_activity("card", "Loaded card analytical context"))
        # Re-derive deterministic story for this slice so chat continues the card.
        try:
            from schemas.filters import AnalyticsFilters
            from services.ai_context import load_ai_context
            from services.ai_evidence import build_evidence
            from services.ai_facts.narration import template_narrative
            from services.ai_facts.packet import build_fact_packet
            from services.ai_rules import build_warnings

            scope_filters = filters or AnalyticsFilters()
            data = await load_ai_context(ctx, db, scope_filters)
            evidence = build_evidence(ctx.role, data)
            warnings = build_warnings(ctx.role, evidence, data, language=lang)
            packet = await build_fact_packet(
                ctx,
                db,
                scope_filters,
                data,
                warnings=warnings or [],
                prediction=None,
                data_version="chat-handoff",
                card_id=card_id or "chat",
            )
            narr = template_narrative(packet, language=lang)
            activities.append(_activity("metrics", "Calculated performance metrics"))
            if packet.drivers:
                activities.append(
                    _activity("drivers", "Compared structural performance drivers")
                )
            if packet.anomalies:
                activities.append(_activity("patterns", "Checked relevant patterns"))
            # Prefixed context for the SQL/LLM path — facts only, from packet.
            card_ctx = (
                f"Active AI card context (verified facts):\n"
                f"headline={narr.get('headline')}\n"
                f"story={narr.get('story')}\n"
                f"metrics={packet.headline_metrics}\n"
                f"drivers={[d.label + ':' + str(d.contribution_points) for d in packet.drivers[:5]]}\n"
                f"item_id={item_id or ''}\n"
            )
            enriched = f"{card_ctx}\nUser question: {enriched}"
            if packet.impact_items:
                objects.append(
                    {
                        "type": "evidence",
                        "title": "Impact ranking",
                        "data": {
                            "items": [i.__dict__ for i in packet.impact_items[:5]]
                        },
                    }
                )
        except Exception:
            open_issues.append(
                "Card context re-derivation failed; answering from question alone."
            )

    result = await answer_question(ctx, db, enriched, pool=pool, language=lang)
    activities.append(_activity("sql", "Retrieved academic data"))
    activities.append(_activity("analysis", "Preparing analysis"))

    # Attach policy objects even when SQL answered.
    if objects:
        result = {**result, "objects": (result.get("objects") or []) + objects}
    if sources:
        result = {**result, "sources": sources}
    result = {**result, "activities": activities}
    if open_issues:
        result = {**result, "openIssues": open_issues}
    return result
