"""Seed package smoke tests (no live DB required)."""

from seed_demo.constants import SEED_CONSTANT, S1_PASS_2025, OWNED_PREFIX
from seed_demo.grades import letter_for, owned_id, rng, scores_for_pass_rate
from seed_demo.policies import load_policies


def test_seed_constant_stable():
    assert SEED_CONSTANT == 20250930


def test_owned_id_prefix():
    assert owned_id("x", "y").startswith(OWNED_PREFIX)


def test_scores_for_pass_rate_deterministic():
    a = scores_for_pass_rate(rng("t"), 40, S1_PASS_2025)
    b = scores_for_pass_rate(rng("t"), 40, S1_PASS_2025)
    assert a == b
    passed = sum(1 for s in a if s >= 60)
    assert abs(passed / len(a) - S1_PASS_2025) <= 0.08


def test_letter_for_bands():
    assert letter_for(96) == "A+"
    assert letter_for(61) == "D+"
    assert letter_for(40).startswith("Failed")


def test_policies_load():
    rows = load_policies()
    assert len(rows) >= 8
    assert all(r["language"] in ("en", "ar") for r in rows)
    assert all(r["id"].startswith(OWNED_PREFIX) for r in rows)
