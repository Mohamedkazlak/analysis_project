from services.chat import classify, looks_like_overview_report, report_focus


def test_arabic_university_report_is_detected():
    q = "أكتب لي تقرير عن حالة الجامعة"
    assert looks_like_overview_report(q)
    assert report_focus(q) == "university"
    assert classify(q, "senior_management") == "institution_kpis"


def test_english_university_report_is_detected():
    q = "Write me a report on the state of the university"
    assert looks_like_overview_report(q)
    assert report_focus(q) == "university"
    assert classify(q, "program_director") == "institution_kpis"


def test_arabic_sector_report_uses_sector_focus():
    q = "أكتب تقرير آخر عن حالة كل قطاع"
    assert looks_like_overview_report(q)
    assert report_focus(q) == "sector"


def test_english_sector_report_uses_sector_focus():
    assert report_focus("Write a report on the status of each sector") == "sector"
    assert report_focus("Sector overview by sector") == "sector"


def test_college_report_focus():
    assert report_focus("تقرير عن حالة كل كلية") == "college"
    assert report_focus("Report on every college") == "college"


def test_unrelated_question_is_not_report():
    assert not looks_like_overview_report("Which college has the lowest pass rate?")
    assert report_focus("Which college has the lowest pass rate?") == "university"
