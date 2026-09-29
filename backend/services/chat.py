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
    r"\b(?:other|another|different|every|all)\s+sectors?\b|"
    r"\bsectors?\s+other\s+than\b|"
    r"خارج\s*قطاعي|قطاع\s*آخر",
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
    if re.search(r"\b(department|platform|institution|university-wide|term kpi)\b", q):
        return "institution_kpis"
    if asks_about_person:
        return "named_students"
    if re.search(r"\b(class average|cohort|compared to others|peers)\b", q):
        return "anonymized_cohort"
    if re.search(r"\b(course|section|exam|curriculum|college|program)\b", q):
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


async def get_chat_answer(
    ctx: UserContext,
    db: asyncpg.Connection,
    question: str,
    pool=None,
) -> dict:
    """Domain gate, then the RAG engine. There is one chat implementation."""
    from rag.chat_engine import answer_question

    reply = static_reply(question, name=ctx.name, display_role=ctx.display_role)
    if reply is not None:
        return {"text": reply, "blocked": False}

    sector_refusal = sector_dean_out_of_scope(ctx, question)
    if sector_refusal is not None:
        from rag.chat_engine import _log

        await _log(pool, ctx, question, None, None, "blocked", 0, True)
        return {"text": sector_refusal, "blocked": True}

    domain = classify(question, ctx.role)
    allowed = DOMAIN_ALLOW.get(ctx.role, set())
    if domain not in allowed:
        from rag.chat_engine import _log

        await _log(pool, ctx, question, None, None, "blocked", 0, True)
        return {"text": refusal_for(ctx.role, domain), "blocked": True}
    return await answer_question(ctx, db, question, pool)
