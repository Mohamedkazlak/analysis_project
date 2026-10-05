"""Policy keyword retrieval helpers."""

from services.policy_rag import looks_like_policy_question, _tokens


def test_policy_question_detection():
    assert looks_like_policy_question("Does university policy allow a retake?")
    assert looks_like_policy_question("ما سياسة الغش؟")
    assert not looks_like_policy_question("What is the Engineering pass rate?")


def test_tokens_extract_keywords():
    tokens = _tokens("Does the retake policy allow students below 50%?")
    assert "retake" in tokens
    assert "policy" not in tokens  # stopworded
