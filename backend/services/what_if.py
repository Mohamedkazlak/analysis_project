"""Deterministic what-if simulations.

The LLM may explain results. It must never calculate them.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from services.ai_thresholds import PASS_RATE_THRESHOLD


def _weighted_pass_rate(
    rows: list[dict], key: str = "passRate"
) -> tuple[Optional[float], int]:
    total_n = 0
    weighted = 0.0
    for row in rows:
        rate = row.get(key)
        n = int(row.get("participants") or row.get("students") or row.get("n") or 0)
        if rate is None or n <= 0:
            continue
        total_n += n
        weighted += float(rate) * n
    if total_n <= 0:
        return None, 0
    return round(weighted / total_n, 1), total_n


def simulate_course_pass_rate(
    *,
    courses: list[dict],
    course_code: str,
    target_pass_rate: float,
    college_pass_rate: Optional[float] = None,
    university_pass_rate: Optional[float] = None,
    college_students: Optional[int] = None,
    university_students: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Estimate college/university pass-rate change if one course reaches a target.

    Assumptions are stated in the result. Aggregation uses attempt/participant
    weights already present on course rows.
    """
    target = float(target_pass_rate)
    if target < 0 or target > 100:
        return None

    code = course_code.strip().upper()
    matched = None
    for row in courses:
        label = str(row.get("course") or row.get("code") or row.get("entity") or "")
        if label.upper() == code or code in label.upper():
            matched = row
            break
    if matched is None:
        return None

    current = matched.get("passRate")
    n = int(
        matched.get("participants") or matched.get("students") or matched.get("n") or 0
    )
    if current is None or n <= 0:
        return None

    current_f = float(current)
    scope_before, scope_n = _weighted_pass_rate(courses)
    if scope_before is None or scope_n <= 0:
        return None

    # Rebuild weighted average with the target course substituted.
    adjusted = []
    for row in courses:
        label = str(row.get("course") or row.get("code") or row.get("entity") or "")
        if (
            matched is row
            or label.upper()
            == str(matched.get("course") or matched.get("code") or "").upper()
        ):
            adjusted.append({**row, "passRate": target})
        else:
            adjusted.append(row)
    scope_after, _ = _weighted_pass_rate(adjusted)
    if scope_after is None:
        return None

    # University uplift: scale course participant share of university students
    # when university totals are known; otherwise report scope-only.
    uni_before = university_pass_rate
    uni_after = None
    if uni_before is not None and university_students and university_students > 0:
        delta_passed = (target - current_f) / 100.0 * n
        uni_after = round(
            float(uni_before) + 100.0 * delta_passed / float(university_students),
            1,
        )

    college_before = (
        college_pass_rate if college_pass_rate is not None else scope_before
    )
    college_after = scope_after
    if (
        college_pass_rate is not None
        and college_students
        and college_students > 0
        and college_students != scope_n
    ):
        delta_passed = (target - current_f) / 100.0 * n
        college_after = round(
            float(college_pass_rate) + 100.0 * delta_passed / float(college_students),
            1,
        )

    course_label = str(matched.get("course") or matched.get("code") or code)
    return {
        "kind": "course_pass_rate",
        "entity": course_label,
        "metric": "pass_rate",
        "currentValue": round(current_f, 1),
        "targetValue": round(target, 1),
        "assumption": (
            f"If {course_label} pass rate moves from {current_f:g}% to {target:g}% "
            f"with the same {n} participants, holding other courses fixed."
        ),
        "scopeAffected": {
            "courseParticipants": n,
            "scopeParticipants": scope_n,
            "collegeStudents": college_students,
            "universityStudents": university_students,
        },
        "estimatedChange": {
            "scopePassRate": {
                "from": scope_before,
                "to": scope_after,
                "delta": round(scope_after - scope_before, 1),
            },
            "collegePassRate": {
                "from": round(float(college_before), 1),
                "to": round(float(college_after), 1),
                "delta": round(float(college_after) - float(college_before), 1),
            },
            "universityPassRate": (
                {
                    "from": round(float(uni_before), 1),
                    "to": uni_after,
                    "delta": round(float(uni_after) - float(uni_before), 1),
                }
                if uni_before is not None and uni_after is not None
                else None
            ),
        },
        "evidence": [
            f"course={course_label}",
            f"current_pass_rate={current_f:g}",
            f"target_pass_rate={target:g}",
            f"participants={n}",
            f"scope_pass_rate_before={scope_before}",
            f"scope_pass_rate_after={scope_after}",
        ],
        "provenance": "deterministic_calculation",
    }


def simulate_weakest_to_benchmark(
    *,
    courses: list[dict],
    benchmark_pass_rate: Optional[float] = None,
    college_pass_rate: Optional[float] = None,
    university_pass_rate: Optional[float] = None,
    college_students: Optional[int] = None,
    university_students: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    if not courses:
        return None
    scored = [
        row
        for row in courses
        if row.get("passRate") is not None
        and int(row.get("participants") or row.get("students") or row.get("n") or 0) > 0
    ]
    if not scored:
        return None
    weakest = min(scored, key=lambda r: float(r["passRate"]))
    target = float(
        benchmark_pass_rate
        if benchmark_pass_rate is not None
        else (
            university_pass_rate
            if university_pass_rate is not None
            else PASS_RATE_THRESHOLD
        )
    )
    code = str(weakest.get("course") or weakest.get("code") or "")
    return simulate_course_pass_rate(
        courses=courses,
        course_code=code,
        target_pass_rate=target,
        college_pass_rate=college_pass_rate,
        university_pass_rate=university_pass_rate,
        college_students=college_students,
        university_students=university_students,
    )


def simulate_college_pass_uplift(
    *,
    college_pass_rate: float,
    university_pass_rate: float,
    college_students: int,
    university_students: int,
    uplift_points: float,
) -> Optional[dict[str, Any]]:
    if college_students <= 0 or university_students <= 0:
        return None
    target = float(college_pass_rate) + float(uplift_points)
    if target < 0 or target > 100:
        return None
    delta_passed = (target - float(college_pass_rate)) / 100.0 * college_students
    uni_after = round(
        float(university_pass_rate) + 100.0 * delta_passed / float(university_students),
        1,
    )
    return {
        "kind": "college_pass_uplift",
        "entity": "college",
        "metric": "pass_rate",
        "currentValue": round(float(college_pass_rate), 1),
        "targetValue": round(target, 1),
        "assumption": (
            f"If college pass rate rises by {uplift_points:g} points "
            f"({college_pass_rate:g}% → {target:g}%) with fixed enrollment "
            f"({college_students}), holding other colleges fixed."
        ),
        "scopeAffected": {
            "collegeStudents": college_students,
            "universityStudents": university_students,
        },
        "estimatedChange": {
            "collegePassRate": {
                "from": round(float(college_pass_rate), 1),
                "to": round(target, 1),
                "delta": round(float(uplift_points), 1),
            },
            "universityPassRate": {
                "from": round(float(university_pass_rate), 1),
                "to": uni_after,
                "delta": round(uni_after - float(university_pass_rate), 1),
            },
        },
        "evidence": [
            f"college_pass_rate={college_pass_rate:g}",
            f"uplift_points={uplift_points:g}",
            f"college_students={college_students}",
            f"university_pass_rate_before={university_pass_rate:g}",
            f"university_pass_rate_after={uni_after}",
        ],
        "provenance": "deterministic_calculation",
    }


_WHAT_IF = re.compile(r"\bwhat\s*if\b|ماذا\s*لو|ماذا\s*إذا|ماذا\s*اذا", re.I)
_COURSE_CODE = re.compile(r"\b([A-Z]{2,5}\s?\d{2,4}[A-Z]?)\b", re.I)
# UI Arabic copy uses past-tense وصل … إلى N%; English uses reaches/to.
_TARGET_PCT = re.compile(
    r"(?:reaches?\s+(?:to\s*)?|to\s+|at\s+|"
    r"وصل(?:ت)?\s+(?:إلى\s*|الى\s*)?|"
    r"يصل(?:ون)?\s+(?:إلى\s*|الى\s*)?|"
    r"(?:إلى|الى)\s*)"
    r"(\d{1,3}(?:\.\d+)?)\s*%?",
    re.I,
)
_UPLIFT = re.compile(
    r"(?:improves?|rises?|increases?|by|يرتفع|يتحسن|ارتفع|تحسّن|تحسن)"
    r"\s*(?:by\s*|بـ?\s*)?(\d{1,2}(?:\.\d+)?)\s*(?:points?|نقاط|نقطة)?",
    re.I,
)
# Arabic UI uses أضعف (without ال); also accept الأسوأ / الأدنى / الضعيف.
_WEAKEST = re.compile(
    r"weakest|lowest[- ]performing|"
    r"أضعف|الأضعف|اضعف|الاضعف|"
    r"أسوأ|الأسوأ|اسوا|الاسوا|"
    r"أدنى|الأدنى|ادنى|الادنى|"
    r"أقل\s+مقرر|اقل\s+مقرر",
    re.I,
)


def parse_what_if_intent(
    question: str, language: str = "en"
) -> Optional[dict[str, Any]]:
    if not _WHAT_IF.search(question):
        return None
    if _WEAKEST.search(question):
        return {"kind": "weakest_to_benchmark"}
    code_m = _COURSE_CODE.search(question)
    target_m = _TARGET_PCT.search(question)
    if code_m and target_m:
        return {
            "kind": "course_pass_rate",
            "course_code": code_m.group(1).replace(" ", "").upper(),
            "target": float(target_m.group(1)),
        }
    uplift_m = _UPLIFT.search(question)
    if uplift_m and re.search(r"college|engineering|كلية|هندس", question, re.I):
        return {"kind": "college_pass_uplift", "uplift": float(uplift_m.group(1))}
    if code_m:
        # Course named but no target — default to review threshold.
        return {
            "kind": "course_pass_rate",
            "course_code": code_m.group(1).replace(" ", "").upper(),
            "target": PASS_RATE_THRESHOLD,
        }
    ar = language.startswith("ar")
    return {
        "kind": "unsupported",
        "reason": (
            "تعذّر فهم سيناريو ماذا لو مدعوم."
            if ar
            else "Could not parse a supported what-if scenario."
        ),
    }


def run_what_if_from_overview(
    intent: dict[str, Any],
    overview: dict[str, Any],
) -> Optional[dict[str, Any]]:
    totals = overview.get("totals") or {}
    courses = overview.get("passRateByCourse") or []
    colleges = overview.get("passRateByCollege") or []
    uni_rate = totals.get("passRate")
    uni_students = int(totals.get("students") or 0) or None
    college_rate = None
    college_students = None
    if len(colleges) == 1:
        college_rate = colleges[0].get("passRate")
        college_students = int(colleges[0].get("students") or 0) or None
    elif colleges and uni_rate is not None:
        # Prefer lowest college when talking about a gap scenario.
        weak = min(colleges, key=lambda c: float(c.get("passRate") or 0))
        college_rate = weak.get("passRate")
        college_students = int(weak.get("students") or 0) or None

    kind = intent.get("kind")
    if kind == "course_pass_rate":
        return simulate_course_pass_rate(
            courses=courses,
            course_code=str(intent["course_code"]),
            target_pass_rate=float(intent["target"]),
            college_pass_rate=float(college_rate) if college_rate is not None else None,
            university_pass_rate=float(uni_rate) if uni_rate is not None else None,
            college_students=college_students,
            university_students=uni_students,
        )
    if kind == "weakest_to_benchmark":
        return simulate_weakest_to_benchmark(
            courses=courses,
            benchmark_pass_rate=float(uni_rate) if uni_rate is not None else None,
            college_pass_rate=float(college_rate) if college_rate is not None else None,
            university_pass_rate=float(uni_rate) if uni_rate is not None else None,
            college_students=college_students,
            university_students=uni_students,
        )
    if kind == "college_pass_uplift":
        if (
            college_rate is None
            or uni_rate is None
            or not college_students
            or not uni_students
        ):
            return None
        return simulate_college_pass_uplift(
            college_pass_rate=float(college_rate),
            university_pass_rate=float(uni_rate),
            college_students=college_students,
            university_students=uni_students,
            uplift_points=float(intent["uplift"]),
        )
    return None


def localize_what_if_result(
    result: dict[str, Any], language: str = "en"
) -> dict[str, Any]:
    """Return a copy with assumption text in the requested language."""
    out = dict(result)
    if not language.startswith("ar"):
        return out
    entity = out.get("entity")
    cur = out.get("currentValue")
    tgt = out.get("targetValue")
    participants = (out.get("scopeAffected") or {}).get("courseParticipants")
    if out.get("kind") == "college_pass_uplift":
        out["assumption"] = (
            f"بافتراض ارتفاع معدل نجاح الكلية من {cur}% إلى {tgt}% "
            f"مع ثبات أعداد القيد والكليات الأخرى."
        )
    elif participants is not None:
        out["assumption"] = (
            f"بافتراض انتقال معدل نجاح {entity} من {cur}% إلى {tgt}% "
            f"لنفس عدد المشاركين ({participants}) مع ثبات المقررات الأخرى."
        )
    else:
        out["assumption"] = (
            f"بافتراض انتقال {entity} من {cur}% إلى {tgt}% مع ثبات باقي العوامل."
        )
    return out


def explain_what_if(result: dict[str, Any], language: str = "en") -> str:
    """Deterministic explanation fallback (LLM may reword later)."""
    entity = result.get("entity")
    cur = result.get("currentValue")
    tgt = result.get("targetValue")
    change = result.get("estimatedChange") or {}
    college = change.get("collegePassRate") or {}
    uni = change.get("universityPassRate") or {}
    scope = result.get("scopeAffected") or {}
    participants = scope.get("courseParticipants")
    ar = language.startswith("ar")
    if ar:
        if result.get("kind") == "college_pass_uplift":
            assumption = (
                f"بافتراض ارتفاع معدل نجاح الكلية من {cur}% إلى {tgt}% "
                f"مع ثبات أعداد القيد والكليات الأخرى."
            )
        elif participants is not None:
            assumption = (
                f"بافتراض انتقال معدل نجاح {entity} من {cur}% إلى {tgt}% "
                f"لنفس عدد المشاركين ({participants}) مع ثبات المقررات الأخرى."
            )
        else:
            assumption = (
                f"بافتراض انتقال {entity} من {cur}% إلى {tgt}% مع ثبات باقي العوامل."
            )
        parts = [
            f"محاكاة: {entity} من {cur}% إلى {tgt}%.",
            assumption,
        ]
        if college:
            parts.append(
                f"تقدير الكلية: {college.get('from')}% → {college.get('to')}% "
                f"(Δ {college.get('delta')} نقطة)."
            )
        if uni:
            parts.append(
                f"تقدير الجامعة: {uni.get('from')}% → {uni.get('to')}% "
                f"(Δ {uni.get('delta')} نقطة)."
            )
        parts.append("هذا تقدير مع ثبات العوامل الأخرى، وليس ادّعاء سببية.")
        return " ".join(parts)
    assumption = result.get("assumption") or ""
    parts = [
        f"Simulation: {entity} from {cur}% to {tgt}%.",
        assumption,
    ]
    if college:
        parts.append(
            f"Estimated college pass rate: {college.get('from')}% → {college.get('to')}% "
            f"(Δ {college.get('delta')} pts)."
        )
    if uni:
        parts.append(
            f"Estimated university pass rate: {uni.get('from')}% → {uni.get('to')}% "
            f"(Δ {uni.get('delta')} pts)."
        )
    parts.append("This is a ceteris-paribus estimate, not a causal claim.")
    return " ".join(parts)
