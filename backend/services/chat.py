"""Role gate for the single chat endpoint.

`classify()` runs before the RAG engine. The live UserContext, not the JWT
role claim, is what the engine and the database use.
"""

import re

import asyncpg
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


def classify(question: str, role: str) -> DataDomain:
    q = question.lower()
    asks_about_person = bool(
        re.search(
            r"\b(who|whose|which student|student s-?\d+|top student|name of)\b", q
        )
    )
    default = _DEFAULT_DOMAIN.get(role, "own_courses")
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
    if re.search(r"\b(course|section|exam|curriculum|curricula|college|program)\b", q):
        return default
    return default


def refusal_for(role: str, domain: DataDomain) -> str:
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

    domain = classify(question, ctx.role)
    allowed = DOMAIN_ALLOW.get(ctx.role, set())
    if domain not in allowed:
        from rag.chat_engine import _log

        await _log(pool, ctx, question, None, None, "blocked", 0, True)
        return {"text": refusal_for(ctx.role, domain), "blocked": True}
    return await answer_question(ctx, db, question, pool)
