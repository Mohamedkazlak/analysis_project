"""Pull a SELECT out of a chat turn. Question wording is the model's job.

A SELECT the user already wrote is returned as-is. Any other wording is left
for the model, which maps it onto the schema. The SQL guard still scopes the
statement before it runs.
"""

import re

from core.locale import Language, normalize_language, txt

_SELECT = re.compile(r"^\s*select\b", re.IGNORECASE)
_FENCED_SELECT = re.compile(
    r"```(?:sql)?\s*(select\b.+?)```", re.IGNORECASE | re.DOTALL
)
_SELECT_AT = re.compile(r"(?is)\bselect\b")


def _norm(text: str) -> str:
    return (
        text.lower()
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
    )


def _direct_select(question: str) -> str | None:
    fenced = _FENCED_SELECT.search(question)
    if fenced:
        return fenced.group(1).strip().rstrip(";").strip()
    stripped = question.strip()
    if _SELECT.match(stripped):
        return stripped.rstrip(";").strip()
    return None


def extract_select(raw: str) -> str:
    """The first SELECT in a model reply, without a sentence wrapped around it."""
    text = (raw or "").strip()
    fenced = _FENCED_SELECT.search(text)
    if fenced:
        return fenced.group(1).strip().rstrip(";").strip()
    match = _SELECT_AT.search(text)
    if not match:
        return text.rstrip(";").strip()
    statement = text[match.start() :].split("```", 1)[0]
    statement = re.split(r"\n\s*\n", statement, maxsplit=1)[0]
    return statement.strip().rstrip(";").strip()


# Keep English constants for older imports/tests; prefer the helpers below.
NOT_UNDERSTOOD = "I did not understand the question. Can you repeat it again?"
OUT_OF_CONTEXT = (
    "Hi, I'm a chatbot built to help you navigate the system. "
    "What can I do to help you?"
)


def not_understood_reply(language: Language | str = "en") -> str:
    lang = normalize_language(str(language))
    return txt(
        lang,
        NOT_UNDERSTOOD,
        "لم أفهم السؤال. هل يمكنك إعادة صياغته؟",
    )


def out_of_context_reply(language: Language | str = "en") -> str:
    lang = normalize_language(str(language))
    return txt(
        lang,
        OUT_OF_CONTEXT,
        "مرحباً، أنا المساعد الذكي. دوري هو مساعدتك على التنقل في النظام. كيف يمكنني المساعدة ؟",
    )


_WHO = re.compile(
    r"^(?:please\s+|can you tell me\s+|tell me\s+)?" r"(who am i|whoami|من انا)\s*\??$"
)
_SMALLTALK = re.compile(
    r"^(hi|hello|hey|thanks|thank you|how are you|good morning|good evening|"
    r"what(?:'s| is) up|help|"
    r"سلام|مرحبا|اهلا|هلا|السلام عليكم|كيف حالك|كيف الحال|شكرا|شكرًا|"
    r"صباح الخير|مساء الخير|مساعدة)\s*[!?.؟]*$"
)
_UNSUPPORTED_SQL = re.compile(
    r"select\s+1\s+as\s+unsupported\s+where\s+false",
    re.IGNORECASE,
)


def _bare(question: str) -> str:
    return re.sub(r"[?!.,؟]+$", "", _norm(question).strip()).strip()


def identity_reply(
    name: str | None,
    display_role: str | None,
    language: Language | str = "en",
) -> str:
    """Name and role come from the signed-in account, not from the model."""
    lang = normalize_language(str(language))
    who = (name or "").strip()
    role = (display_role or "").strip()
    if who and role:
        return txt(lang, f"You're {who}, {role}.", f"أنت {who}، {role}.")
    if who:
        return txt(lang, f"You're {who}.", f"أنت {who}.")
    if role:
        return txt(lang, f"You're {role}.", f"أنت {role}.")
    return txt(lang, "You're signed in.", "أنت مسجّل الدخول.")


def static_reply(
    question: str,
    *,
    name: str | None = None,
    display_role: str | None = None,
    language: Language | str = "en",
) -> str | None:
    """A fixed answer, or None when the question still needs SQL."""
    text = _bare(question)
    if _WHO.fullmatch(text):
        return identity_reply(name, display_role, language=language)
    if _SMALLTALK.fullmatch(text):
        return out_of_context_reply(language)
    return None


def is_out_of_context_sql(raw_sql: str) -> bool:
    """The model uses this statement when the question is not about the database."""
    text = (raw_sql or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.lower().startswith("sql"):
            text = text[3:]
    text = text.strip().rstrip(";").strip()
    return _UNSUPPORTED_SQL.fullmatch(text) is not None


def sql_for_question(question: str) -> str | None:
    """A SELECT the user wrote, or None so the model can interpret the wording."""
    return _direct_select(question)
