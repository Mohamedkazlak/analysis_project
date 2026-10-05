"""Statistical anomaly detectors (no LLM)."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from core.locale import Language, topic as localize_topic, txt
from services.ai_facts.models import Anomaly


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    if len(values) < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return m, math.sqrt(var)


def detect_section_score_outlier(
    sections: list[dict], language: Language = "en"
) -> list[Anomaly]:
    """Flag a section whose mean is high and SD unusually tight vs siblings."""
    out: list[Anomaly] = []
    if len(sections) < 2:
        return out
    means = [float(s["mean"]) for s in sections if s.get("mean") is not None]
    if len(means) < 2:
        return out
    m, sd = _mean_std(means)
    for s in sections:
        mean = float(s.get("mean") or 0)
        spread = float(s.get("sd") or s.get("spread") or 999)
        sibling_spread = _mean_std(
            [float(x.get("sd") or x.get("spread") or 0) for x in sections if x is not s]
        )[0]
        if mean >= m + max(8.0, sd) and spread < max(3.0, sibling_spread * 0.45):
            section = s.get("section")
            out.append(
                Anomaly(
                    id=f"section_outlier:{section}",
                    detector="section_score_distribution",
                    severity="medium",
                    confidence=round(min(0.95, 0.55 + (mean - m) / 40), 2),
                    text=txt(
                        language,
                        (
                            f"Section {section} scores are unusually high and tight "
                            f"(mean {mean:g}, spread {spread:g}) versus sibling sections."
                        ),
                        (
                            f"درجات الشعبة {section} مرتفعة ومتقاربة بشكل غير معتاد "
                            f"(المتوسط {mean:g}، الانتشار {spread:g}) مقارنة بالشعب الشقيقة."
                        ),
                    ),
                    evidence=[
                        f"section_mean={mean:g}",
                        f"section_sd={spread:g}",
                        f"sibling_mean={m:g}",
                    ],
                    entity=str(section),
                )
            )
    return out


def detect_question_topic_outlier(
    questions: list[dict], language: Language = "en"
) -> list[Anomaly]:
    """Flag a question near 0% correct while same-topic peers are ~70%."""
    out: list[Anomaly] = []
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        topic = q.get("topic")
        if topic and q.get("correct_rate") is not None:
            by_topic[str(topic)].append(q)
    for topic, rows in by_topic.items():
        if len(rows) < 2:
            continue
        for r in rows:
            rate = float(r["correct_rate"])
            peers = [float(x["correct_rate"]) for x in rows if x is not r]
            if not peers:
                continue
            peer = sum(peers) / len(peers)
            if rate <= 0.05 and peer >= 0.55:
                topic_label = localize_topic(language, topic)
                out.append(
                    Anomaly(
                        id=f"question_outlier:{r.get('id') or r.get('question_id')}",
                        detector="question_correct_rate_vs_topic",
                        severity="high",
                        confidence=round(min(0.97, 0.6 + peer - rate), 2),
                        text=txt(
                            language,
                            (
                                f"Question on topic {topic_label} has near-0% correct "
                                f"({rate:g}) while peers on the same topic average {peer:g}."
                            ),
                            (
                                f"سؤال حول موضوع {topic_label} نسبة إجابته الصحيحة تقارب 0% "
                                f"({rate:g}) بينما متوسط أقران نفس الموضوع {peer:g}."
                            ),
                        ),
                        evidence=[
                            f"question_rate={rate:g}",
                            f"topic_peer_rate={peer:g}",
                            f"topic={topic}",
                        ],
                        entity=str(r.get("id") or topic),
                    )
                )
    return out


def detect_yoy_fail_jump(
    series: list[dict], language: Language = "en"
) -> list[Anomaly]:
    """Fail rate rose by ≥20 points versus prior year."""
    out: list[Anomaly] = []
    by_course: dict[str, list[dict]] = defaultdict(list)
    for row in series:
        course = row.get("course") or row.get("entity")
        if course and row.get("fail_rate") is not None and row.get("year"):
            by_course[str(course)].append(row)
    for course, rows in by_course.items():
        rows = sorted(rows, key=lambda r: str(r["year"]))
        for prev, cur in zip(rows, rows[1:]):
            jump = float(cur["fail_rate"]) - float(prev["fail_rate"])
            if jump >= 0.20:
                out.append(
                    Anomaly(
                        id=f"yoy_fail:{course}:{cur['year']}",
                        detector="yoy_fail_rate_jump",
                        severity="high",
                        confidence=round(min(0.95, 0.5 + jump), 2),
                        text=txt(
                            language,
                            (
                                f"{course} fail rate rose by {jump*100:.0f} points "
                                f"from {prev['year']} to {cur['year']}."
                            ),
                            (
                                f"معدل رسوب {course} ارتفع بمقدار {jump*100:.0f} نقطة "
                                f"من {prev['year']} إلى {cur['year']}."
                            ),
                        ),
                        evidence=[
                            f"prev_fail={float(prev['fail_rate']):g}",
                            f"cur_fail={float(cur['fail_rate']):g}",
                            f"jump={jump:g}",
                        ],
                        entity=course,
                    )
                )
    return out


def detect_ip_timing_clusters(
    attempts: list[dict], language: Language = "en"
) -> list[Anomaly]:
    """Cluster of attempts sharing IP with fast timing."""
    out: list[Anomaly] = []
    by_ip: dict[str, list[dict]] = defaultdict(list)
    for a in attempts:
        ip = a.get("ip")
        if ip:
            by_ip[str(ip)].append(a)
    for ip, rows in by_ip.items():
        if len(rows) < 5:
            continue
        fast = [r for r in rows if (r.get("time_taken_min") or 99) <= 15]
        if len(fast) >= 5:
            out.append(
                Anomaly(
                    id=f"ip_cluster:{ip}",
                    detector="ip_timing_cluster",
                    severity="high",
                    confidence=0.9,
                    text=txt(
                        language,
                        f"{len(fast)} attempts share IP {ip} with fast submission timing.",
                        f"{len(fast)} محاولات تشترك في عنوان IP {ip} مع تسليم سريع.",
                    ),
                    evidence=[f"ip={ip}", f"cluster_size={len(fast)}"],
                    entity=ip,
                )
            )
    return out


def run_detectors(signals: dict[str, Any], language: Language = "en") -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    anomalies.extend(
        detect_section_score_outlier(signals.get("sections") or [], language)
    )
    anomalies.extend(
        detect_question_topic_outlier(signals.get("questions") or [], language)
    )
    anomalies.extend(detect_yoy_fail_jump(signals.get("yoy") or [], language))
    anomalies.extend(detect_ip_timing_clusters(signals.get("attempts") or [], language))
    anomalies.sort(
        key=lambda a: (
            -{"high": 2, "medium": 1, "low": 0}.get(a.severity, 0),
            -a.confidence,
        )
    )
    return anomalies
