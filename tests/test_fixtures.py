"""Utterances and dialogs validate against their schemas (SPEC.md §10 and §12)."""

import pytest
from pydantic import ValidationError

from saathi.eval_schema import (
    INTENTS,
    UtteranceSet,
    assert_phrase_ids_exist,
    load_dialog_scripts,
    load_utterance_set,
)
from saathi.paths import REPO_ROOT
from saathi.phrases import SPEC_EMERGENCY_PHRASES, load_emergency_phrases, load_phrases

_NEGATION_MARKERS = ("नहीं", "nahi", "nahin")


def test_utterances_validate_and_meet_section_10() -> None:
    loaded = load_utterance_set(REPO_ROOT / "eval/utterances.yaml")
    utterances = loaded.utterances
    assert len(utterances) >= 200
    assert {item.intent for item in utterances} == INTENTS
    assert {item.script for item in utterances} == {"devanagari", "roman", "dialect"}
    emergency = [item for item in utterances if item.intent == "emergency"]
    assert len(emergency) >= 40
    casual = [
        item for item in utterances if item.intent != "emergency" and item.mentions_pain_or_health
    ]
    assert len(casual) >= 40
    texts = {item.text for item in utterances}
    assert "दर्द नहीं है" in texts
    assert "सीने में दर्द नहीं है" in texts


def test_non_emergency_text_does_not_contain_phrase_without_negation() -> None:
    loaded = load_utterance_set(REPO_ROOT / "eval/utterances.yaml")
    for item in loaded.utterances:
        if item.intent == "emergency":
            continue
        folded = item.text.casefold()
        for phrase in SPEC_EMERGENCY_PHRASES:
            if phrase.casefold() in folded:
                assert any(marker in folded for marker in _NEGATION_MARKERS), item.text


def test_dialogs_validate_against_schema() -> None:
    phrases = load_phrases()
    scripts = load_dialog_scripts(REPO_ROOT / "eval/dialogs")
    assert {script.id for script in scripts} >= {
        "reminder_taken",
        "reminder_not_yet",
        "reminder_later",
        "reminder_second_snooze_missed",
        "reminder_clarify_then_taken",
        "reminder_clarify_twice_missed",
        "reminder_silence",
        "reminder_emergency",
        "checkin_good",
        "checkin_okay",
        "checkin_unwell_yes",
        "checkin_unwell_no",
    }
    assert_phrase_ids_exist(scripts, phrases)
    emergency = next(script for script in scripts if script.id == "reminder_emergency")
    assert emergency.turns[0].session_remains_open is True
    assert emergency.turns[0].events == ["emergency"]
    missed = next(script for script in scripts if script.id == "reminder_second_snooze_missed")
    assert missed.prior_snoozes == 1
    assert missed.turns[0].events == ["missed"]
    silence = next(script for script in scripts if script.id == "reminder_silence")
    assert [turn.kind for turn in silence.turns] == ["silence", "silence"]
    assert silence.turns[0].phrase_ids == ["silence.repeat"]
    assert silence.turns[1].phrase_ids == ["silence.end"]


def test_invalid_intent_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UtteranceSet.model_validate(
            {
                "schema_version": 1,
                "utterances": [
                    {
                        "id": "bad",
                        "text": "hello",
                        "intent": "diagnosis",
                        "script": "roman",
                        "mentions_pain_or_health": False,
                    }
                ],
            }
        )


def test_emergency_phrase_file_loads() -> None:
    phrases = load_emergency_phrases(REPO_ROOT / "src/saathi/dialog/phrases/emergency.yaml")
    assert len(phrases) >= len(SPEC_EMERGENCY_PHRASES)
