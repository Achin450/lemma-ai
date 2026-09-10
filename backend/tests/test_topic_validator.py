import pytest
from app.services.topic_validator import TopicValidator


def test_topic_validator_heuristics():
    # 1. Short input
    res = TopicValidator.check_heuristics("ai")
    assert res is not None
    assert res.is_valid is False
    assert res.error_code == "TOO_SHORT"

    # 2. Single word
    res = TopicValidator.check_heuristics("robotics")
    assert res is not None
    assert res.is_valid is False
    assert res.error_code == "TOO_VAGUE"

    # 3. Repeated characters
    res = TopicValidator.check_heuristics("deep learning aaaaaaa")
    assert res is not None
    assert res.is_valid is False
    assert res.error_code == "REPEATED_CHARS"

    # 4. Keyboard mash / consonant cluster
    res = TopicValidator.check_heuristics("quantum asdfghjk analysis")
    assert res is not None
    assert res.is_valid is False
    assert res.error_code in ("KEYBOARD_MASH", "KEYBOARD_WALK")

    # 5. Non-academic colloquial query
    res = TopicValidator.check_heuristics("how to make maggi easily")
    assert res is not None
    assert res.is_valid is False
    assert res.error_code == "NON_ACADEMIC_CONTENT"

    # 6. Valid scholarly topic passes heuristics
    res = TopicValidator.check_heuristics("Deep Reinforcement Learning in Autonomous Robotics")
    assert res is None


@pytest.mark.anyio
async def test_topic_validator_end_to_end():
    # Test valid topic
    res = await TopicValidator.validate_topic("Deep Reinforcement Learning in Autonomous Robotics")
    assert res.is_valid is True

    # Test invalid topic
    res = await TopicValidator.validate_topic("how to cook tea bhai")
    assert res.is_valid is False
    assert len(res.suggestions) > 0
