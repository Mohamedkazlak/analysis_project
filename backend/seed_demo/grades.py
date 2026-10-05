"""Deterministic helpers for storyboard scores and grades."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Iterable

from seed_demo.constants import (
    LETTER_BANDS,
    REAL_ATTEMPT_MEAN,
    REAL_ATTEMPT_SD,
    SEED_CONSTANT,
)


def rng(stream: str) -> random.Random:
    digest = hashlib.sha256(f"{SEED_CONSTANT}:{stream}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def letter_for(average: float) -> str:
    for cutoff, letter in LETTER_BANDS:
        if average >= cutoff:
            return letter
    return "Failed (Overall)"


def quality_points(average: float) -> float:
    """Calibrated QP used in answer key notes (0.06*avg - 2)."""
    return round(0.06 * average - 2.0, 2)


def sample_score(r: random.Random, mean: float, sd: float | None = None) -> float:
    """Normal-ish sample around mean; uses real-data spread by default."""
    spread = REAL_ATTEMPT_SD if sd is None else sd
    # Box-Muller
    u1 = max(1e-9, r.random())
    u2 = r.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return clamp(mean + z * (spread * 0.35))


def scores_for_pass_rate(
    r: random.Random,
    n: int,
    pass_rate: float,
    pass_mark: float = 60.0,
) -> list[float]:
    """Return n scores with approximately the requested pass rate."""
    if n <= 0:
        return []
    n_pass = int(round(pass_rate * n))
    n_pass = max(0, min(n, n_pass))
    out: list[float] = []
    for i in range(n_pass):
        out.append(sample_score(r, mean=72.0, sd=12.0))
    for i in range(n - n_pass):
        out.append(sample_score(r, mean=45.0, sd=10.0))
    r.shuffle(out)
    return [round(x, 1) for x in out]


def shift_scores(scores: Iterable[float], delta: float) -> list[float]:
    return [round(clamp(s + delta), 1) for s in scores]


def owned_id(*parts: str) -> str:
    from seed_demo.constants import OWNED_PREFIX

    body = "-".join(str(p).replace("/", "-") for p in parts)
    return f"{OWNED_PREFIX}{body}"
