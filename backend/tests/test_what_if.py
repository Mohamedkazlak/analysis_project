"""Unit tests for deterministic what-if simulations."""

from services.what_if import (
    explain_what_if,
    parse_what_if_intent,
    run_what_if_from_overview,
    simulate_course_pass_rate,
    simulate_weakest_to_benchmark,
)


def test_course_what_if_improves_scope():
    courses = [
        {"course": "AIM303", "passRate": 50.0, "participants": 40},
        {"course": "CS201", "passRate": 80.0, "participants": 60},
    ]
    result = simulate_course_pass_rate(
        courses=courses,
        course_code="AIM303",
        target_pass_rate=70.0,
        university_pass_rate=76.8,
        university_students=500,
    )
    assert result is not None
    assert result["currentValue"] == 50.0
    assert result["targetValue"] == 70.0
    scope = result["estimatedChange"]["scopePassRate"]
    assert scope["to"] > scope["from"]
    uni = result["estimatedChange"]["universityPassRate"]
    assert uni is not None
    assert uni["to"] > uni["from"]
    assert (
        "ceteris" in explain_what_if(result).lower()
        or "estimate" in explain_what_if(result).lower()
    )


def test_weakest_to_university_average():
    courses = [
        {"course": "AIM303", "passRate": 50.0, "participants": 40},
        {"course": "CS201", "passRate": 80.0, "participants": 60},
    ]
    result = simulate_weakest_to_benchmark(
        courses=courses,
        benchmark_pass_rate=76.8,
        university_pass_rate=76.8,
        university_students=500,
    )
    assert result is not None
    assert result["entity"] == "AIM303"
    assert result["targetValue"] == 76.8


def test_parse_what_if_aim303():
    intent = parse_what_if_intent("What if AIM303 reaches 70%?")
    assert intent is not None
    assert intent["kind"] == "course_pass_rate"
    assert intent["course_code"] == "AIM303"
    assert intent["target"] == 70.0


def test_parse_arabic_weakest_to_university_average():
    """Matches the Arabic UI chip: ماذا لو وصل أضعف مقرر إلى متوسط الجامعة؟"""
    intent = parse_what_if_intent(
        "ماذا لو وصل أضعف مقرر إلى متوسط الجامعة؟", language="ar"
    )
    assert intent is not None
    assert intent["kind"] == "weakest_to_benchmark"


def test_parse_arabic_course_to_target():
    intent = parse_what_if_intent("ماذا لو وصل AIM303 إلى 70%؟", language="ar")
    assert intent is not None
    assert intent["kind"] == "course_pass_rate"
    assert intent["course_code"] == "AIM303"
    assert intent["target"] == 70.0


def test_explain_what_if_arabic():
    courses = [
        {"course": "AIM303", "passRate": 50.0, "participants": 40},
        {"course": "CS201", "passRate": 80.0, "participants": 60},
    ]
    result = simulate_weakest_to_benchmark(
        courses=courses,
        benchmark_pass_rate=76.8,
        university_pass_rate=76.8,
        university_students=500,
    )
    text = explain_what_if(result, language="ar")
    assert "محاكاة" in text
    assert "AIM303" in text
    assert "ceteris" not in text.lower()
    assert "ادّعاء سببية" in text or "ثبات" in text


def test_run_from_overview():
    overview = {
        "totals": {"passRate": 76.8, "students": 500},
        "passRateByCourse": [
            {"course": "AIM303", "passRate": 50.0, "participants": 40},
            {"course": "CS201", "passRate": 80.0, "participants": 60},
        ],
        "passRateByCollege": [
            {"college": "Engineering", "passRate": 68.0, "students": 200}
        ],
    }
    intent = parse_what_if_intent("What if AIM303 reaches 70%?")
    result = run_what_if_from_overview(intent, overview)
    assert result is not None
    assert result["estimatedChange"]["collegePassRate"]["to"] > 68.0

    ar_intent = parse_what_if_intent(
        "ماذا لو وصل أضعف مقرر إلى متوسط الجامعة؟", language="ar"
    )
    ar_result = run_what_if_from_overview(ar_intent, overview)
    assert ar_result is not None
    assert ar_result["entity"] == "AIM303"
    assert ar_result["targetValue"] == 76.8
