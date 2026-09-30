"""App UI / AI copy language. Facts stay SQL-derived; only wording changes."""

from __future__ import annotations

from typing import Literal

Language = Literal["en", "ar"]

# Demo org-unit display names. Facts stay keyed by English SQL names;
# Arabic is presentation-only.
_ORG_AR: dict[str, str] = {
    "Benha National University": "جامعة بنها الأهلية",
    "Engineering and Basic & Applied Sciences": "الهندسة والعلوم الأساسية والتطبيقية",
    "Health Sciences": "العلوم الصحية",
    "Literature, Arts and Humanities": "الآداب والفنون والعلوم الإنسانية",
    "Engineering": "الهندسة",
    "Energy Sciences": "علوم الطاقة",
    "Computer Science": "علوم الحاسب",
    "Medicine": "الطب",
    "Dentistry": "طب الأسنان",
    "Physical Therapy": "العلاج الطبيعي",
    "Veterinary": "الطب البيطري",
    "Visual Arts and Design": "الفنون البصرية والتصميم",
    "Economics and Business Administration": "الاقتصاد وإدارة الأعمال",
    "University": "الجامعة",
}


def normalize_language(value: str | None) -> Language:
    raw = (value or "en").strip().lower()
    if raw in {"ar", "arabic", "ar-eg", "ar_eg"}:
        return "ar"
    return "en"


def txt(language: Language, en: str, ar: str) -> str:
    return ar if language == "ar" else en


def entity(language: Language, name: str | None) -> str:
    """Localize a known org/curriculum label for display; passthrough otherwise."""
    if not name:
        return ""
    if language != "ar":
        return name
    return _ORG_AR.get(name, name)
