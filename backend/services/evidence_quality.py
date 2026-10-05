"""Deterministic evidence-quality labels (not fake confidence percentages)."""

from __future__ import annotations

from typing import Any, Literal

from core.locale import Language, txt

EvidenceQuality = Literal["strong", "moderate", "limited"]


def assess_evidence_quality(
    *,
    sample_size: int | None = None,
    has_historical: bool = False,
    has_breakdown: bool = False,
    has_comparison: bool = False,
    anomaly_count: int = 0,
    rule_alert_count: int = 0,
    language: Language = "en",
) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    if sample_size is not None and sample_size >= 50:
        score += 2
        reasons.append(f"sample_size={sample_size}")
    elif sample_size is not None and sample_size >= 15:
        score += 1
        reasons.append(f"sample_size={sample_size}")
    elif sample_size is not None:
        reasons.append(f"small_sample={sample_size}")

    if has_historical:
        score += 2
        reasons.append("historical_comparison")
    if has_breakdown:
        score += 1
        reasons.append("entity_breakdown")
    if has_comparison:
        score += 1
        reasons.append("peer_or_benchmark_comparison")
    if rule_alert_count:
        score += 1
        reasons.append(f"rule_alerts={rule_alert_count}")
    if anomaly_count:
        score += 1
        reasons.append(f"anomaly_candidates={anomaly_count}")

    if score >= 5:
        quality: EvidenceQuality = "strong"
    elif score >= 3:
        quality = "moderate"
    else:
        quality = "limited"

    labels = {
        "strong": txt(language, "Strong evidence", "أدلة قوية"),
        "moderate": txt(language, "Moderate evidence", "أدلة متوسطة"),
        "limited": txt(language, "Limited evidence", "أدلة محدودة"),
    }

    return {
        "quality": quality,
        "label": labels[quality],
        "score": score,
        "reasons": reasons,
    }
