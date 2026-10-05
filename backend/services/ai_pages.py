"""Page-scoped AI analysis topics.

Each dashboard page asks for insights about *that* surface, not a single
role-wide narrative. Datasets are still role-gated in load_ai_context.
"""

from __future__ import annotations

from typing import Any, Optional

# Stable page ids used by the frontend `AiDecisionSection page=` prop.
AI_PAGES = frozenset(
    {
        "overview",
        "courses",
        "exam-activity",
        "performance",
        "participation",
        "item-analysis",
        "integrity",
        "real-time",
        "students",
        "student",
        "my-progress",
    }
)

PAGE_LABELS_EN: dict[str, str] = {
    "overview": "Overview analysis",
    "courses": "Course performance analysis",
    "exam-activity": "Exam activity analysis",
    "performance": "Student performance analysis",
    "participation": "Participation analysis",
    "item-analysis": "Item analysis",
    "integrity": "Integrity analysis",
    "real-time": "Live monitoring analysis",
    "students": "Student directory analysis",
    "student": "Student analysis",
    "my-progress": "My progress analysis",
}

PAGE_LABELS_AR: dict[str, str] = {
    "overview": "تحليل النظرة العامة",
    "courses": "تحليل أداء المقررات",
    "exam-activity": "تحليل نشاط الامتحانات",
    "performance": "تحليل أداء الطلاب",
    "participation": "تحليل المشاركة",
    "item-analysis": "تحليل البنود",
    "integrity": "تحليل النزاهة",
    "real-time": "تحليل المراقبة المباشرة",
    "students": "تحليل دليل الطلاب",
    "student": "تحليل الطالب",
    "my-progress": "تحليل تقدمي",
}

# Which analytic slices to emphasize when shaping the packet / story.
PAGE_FOCUS: dict[str, dict[str, Any]] = {
    "overview": {
        "metrics": ("passRate", "attendance", "students", "exams"),
        "driver_kinds": ("course", "section", "topic", "yoy"),
        "warning_metrics": (),
        "evidence_datasets": (),
        "recommendation_routes": (),
        "show_forecast": True,
        "show_impact": True,
        "show_rules": True,
        "show_anomalies": True,
    },
    "courses": {
        "metrics": ("passRate", "students"),
        "driver_kinds": ("course", "section"),
        "warning_metrics": ("pass_rate",),
        "evidence_datasets": (
            "passRateByCourse",
            "passRateByCollege",
            "sections",
            "totals",
        ),
        "recommendation_routes": ("/courses", "/performance"),
        "show_forecast": True,
        "show_impact": True,
        "show_rules": True,
        "show_anomalies": False,
    },
    "exam-activity": {
        "metrics": ("passRate", "exams", "students"),
        "driver_kinds": ("course", "section"),
        "warning_metrics": ("pass_rate",),
        "evidence_datasets": (
            "passRateByCourse",
            "passRateByCollege",
            "sections",
            "totals",
        ),
        "recommendation_routes": ("/courses", "/exam-activity", "/performance"),
        "show_forecast": False,
        "show_impact": True,
        "show_rules": True,
        "show_anomalies": True,
    },
    "performance": {
        "metrics": ("passRate", "students"),
        "driver_kinds": ("course", "yoy"),
        "warning_metrics": ("pass_rate", "students_below_pass"),
        "evidence_datasets": (
            "passRateByCourse",
            "student_performance",
            "totals",
            "sections",
        ),
        "recommendation_routes": ("/performance", "/students", "/courses"),
        "show_forecast": True,
        "show_impact": True,
        "show_rules": True,
        "show_anomalies": False,
    },
    "participation": {
        "metrics": ("attendance", "students"),
        # Pass-rate gap drivers are not attendance drivers; keep empty so the
        # card narrates attendance metrics / alerts instead.
        "driver_kinds": (),
        "warning_metrics": ("attendance_rate",),
        "evidence_datasets": (
            "participation",
            "attendanceByCurriculum",
            "totals",
        ),
        "recommendation_routes": ("/participation",),
        "show_forecast": False,
        "show_impact": True,
        "show_rules": True,
        "show_anomalies": False,
        "rule_metrics": ("attendance_rate",),
    },
    "item-analysis": {
        "metrics": ("passRate",),
        "driver_kinds": ("topic",),
        "warning_metrics": ("discrimination_index",),
        "evidence_datasets": ("item_analysis",),
        "recommendation_routes": ("/item-analysis",),
        "show_forecast": False,
        "show_impact": False,
        "show_rules": True,
        "show_anomalies": True,
    },
    "integrity": {
        "metrics": ("students", "exams"),
        "driver_kinds": (),
        "warning_metrics": ("flagged_attempts", "integrity_signals"),
        "evidence_datasets": ("integrity", "flagged_attempts"),
        "recommendation_routes": ("/integrity", "/real-time"),
        "show_forecast": False,
        "show_impact": True,
        "show_rules": False,
        "show_anomalies": True,
    },
    "real-time": {
        "metrics": ("students", "exams"),
        "driver_kinds": (),
        "warning_metrics": ("flagged_attempts", "integrity_signals"),
        "evidence_datasets": ("integrity", "flagged_attempts"),
        "recommendation_routes": ("/real-time", "/integrity"),
        "show_forecast": False,
        "show_impact": False,
        "show_rules": False,
        "show_anomalies": True,
    },
    "students": {
        "metrics": ("passRate", "students"),
        "driver_kinds": ("course",),
        "warning_metrics": ("pass_rate", "students_below_pass"),
        "evidence_datasets": ("student_performance", "passRateByCourse", "totals"),
        "recommendation_routes": ("/students", "/performance"),
        "show_forecast": False,
        "show_impact": True,
        "show_rules": True,
        "show_anomalies": False,
    },
    "student": {
        "metrics": ("passRate",),
        "driver_kinds": ("course",),
        "warning_metrics": ("pass_rate",),
        "evidence_datasets": ("student_performance", "student_dashboard"),
        "recommendation_routes": ("/students", "/performance", "/my-progress"),
        "show_forecast": False,
        "show_impact": False,
        "show_rules": True,
        "show_anomalies": False,
    },
    "my-progress": {
        "metrics": ("passRate",),
        "driver_kinds": ("course",),
        "warning_metrics": ("average", "exam_score", "topic_score"),
        "evidence_datasets": (
            "student_dashboard",
            "scoreTimeline",
            "topics",
            "transcript_entries",
        ),
        "recommendation_routes": ("/my-progress",),
        "show_forecast": False,
        "show_impact": False,
        "show_rules": True,
        "show_anomalies": False,
    },
}


def normalize_page(page: Optional[str]) -> str:
    value = (page or "overview").strip().lower()
    return value if value in AI_PAGES else "overview"


def page_label(page: str, language: str = "en") -> str:
    page = normalize_page(page)
    if language.startswith("ar"):
        return PAGE_LABELS_AR.get(page, PAGE_LABELS_EN[page])
    return PAGE_LABELS_EN[page]


def page_focus(page: str) -> dict[str, Any]:
    return PAGE_FOCUS.get(normalize_page(page), PAGE_FOCUS["overview"])
