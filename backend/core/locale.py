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

# Demo question-topic labels (presentation only; SQL keys stay English).
_TOPIC_AR: dict[str, str] = {
    "Physics": "الفيزياء",
    "Mathematics": "الرياضيات",
    "Programming": "البرمجة",
    "Databases": "قواعد البيانات",
    "Database Systems": "قواعد البيانات",
    "Artificial Intelligence": "الذكاء الاصطناعي",
    "Software Engineering": "هندسة البرمجيات",
    "Computer Science": "علوم الحاسب",
    "Information Security": "أمن المعلومات",
    "Cybersecurity": "الأمن السيبراني",
    "Web Development": "تطوير الويب",
    "Networks": "الشبكات",
    "Algorithms": "الخوارزميات",
    "Data Structures": "هياكل البيانات",
    "Operating Systems": "نظم التشغيل",
    "Course assessment": "تقييم المقرر",
    "Architecture": "الهندسة المعمارية",
    "Use Cases": "حالات الاستخدام",
    "Sequence Diagrams": "مخططات التسلسل",
    "Requirements": "المتطلبات",
    "Data Modeling": "نمذجة البيانات",
    "UI Flows": "تدفقات الواجهة",
    "General": "عام",
    "None": "لا يوجد",
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


def topic(language: Language, name: str | None) -> str:
    """Localize a known question-topic label for display; passthrough otherwise."""
    if not name:
        return ""
    if language != "ar":
        return name
    return _TOPIC_AR.get(name, name)
