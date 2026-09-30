"""Phrase file and emergency list from SPEC.md §5."""

from saathi.config import emergency_phrase_path, load_config
from saathi.phrases import (
    SPEC_EMERGENCY_PHRASES,
    SPOKEN_WORD_LIMIT,
    load_emergency_phrases,
    load_phrases,
)

REQUIRED_SPOKEN = (
    "greet.reminder",
    "remind.dose",
    "remind.instructions",
    "ask.taken",
    "ack.taken",
    "ack.snooze",
    "clarify.taken",
    "ack.missed",
    "close.polite",
    "emergency.alert",
    "checkin.greet",
    "checkin.ask",
    "checkin.good",
    "checkin.okay",
    "checkin.unwell_offer",
    "checkin.notify_ack",
    "silence.repeat",
    "silence.end",
    "consent.ask",
    "consent.thanks",
)


def test_spoken_phrases_are_templates_within_word_limit() -> None:
    phrases = load_phrases()
    for phrase_id in REQUIRED_SPOKEN:
        phrase = phrases[phrase_id]
        assert phrase.spoken
        assert len(phrase.text.split()) <= SPOKEN_WORD_LIMIT
    assert phrases["checkin.unwell_offer"].text == "क्या आप परिवार से बात करना चाहेंगे?"
    assert phrases["summary.checkin"].spoken is False
    assert phrases["notify.missed"].spoken is False
    assert phrases["notify.emergency"].spoken is False


def test_emergency_phrase_list_includes_spec_examples() -> None:
    phrases = load_emergency_phrases(emergency_phrase_path(load_config()))
    assert set(SPEC_EMERGENCY_PHRASES) <= set(phrases)
    assert "दर्द" not in phrases
