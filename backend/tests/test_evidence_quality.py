from services.evidence_quality import assess_evidence_quality


def test_strong_evidence():
    q = assess_evidence_quality(
        sample_size=120,
        has_historical=True,
        has_breakdown=True,
        has_comparison=True,
        rule_alert_count=2,
    )
    assert q["quality"] == "strong"


def test_limited_evidence():
    q = assess_evidence_quality(sample_size=5)
    assert q["quality"] == "limited"


def test_evidence_quality_arabic_label():
    q = assess_evidence_quality(
        sample_size=120,
        has_historical=True,
        has_breakdown=True,
        has_comparison=True,
        rule_alert_count=2,
        language="ar",
    )
    assert q["quality"] == "strong"
    assert q["label"] == "أدلة قوية"
