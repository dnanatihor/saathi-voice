"""Every eval dialog script, and emergency that the model cannot suppress."""

from saathi.channels.text import TextChannel
from saathi.dialog.graph import Beat, DialogError, DialogSession, Persona
from saathi.dialog.nlu import IntentResult, Understanding
from saathi.eval_schema import Intent, load_dialog_scripts
from saathi.paths import REPO_ROOT
from saathi.phrases import Phrase, load_phrases, render


class _FixedModel:
    def __init__(self, intent: Intent) -> None:
        self.intent = intent

    def classify(self, text: str, dialog_state: str, prompt: str) -> IntentResult:
        del text, dialog_state, prompt
        return IntentResult(intent=self.intent, confidence=0.99, slots={})


def test_every_dialog_script_passes() -> None:
    phrases = load_phrases()
    persona = Persona()
    values = {
        "honorific": persona.honorific,
        "spoken_label": persona.spoken_label,
        "instructions": persona.instructions,
        "elder_words": "",
        "snippet": "",
    }
    for script in load_dialog_scripts(REPO_ROOT / "eval/dialogs"):
        session = DialogSession(script.flow, phrases, prior_snoozes=script.prior_snoozes)
        opening = session.start()
        _assert_beat(
            opening,
            script.opening.states,
            script.opening.phrase_ids,
            script.opening.events,
        )
        assert opening.notifications == script.opening.notifications
        assert opening.session_remains_open is script.opening.session_remains_open
        _assert_spoken(opening, phrases, values)
        for turn in script.turns:
            result = session.silence() if turn.kind == "silence" else session.user_turn(turn.user)
            _assert_beat(result, turn.states, turn.phrase_ids, turn.events, script.id)
            assert result.notifications == turn.notifications
            assert result.session_remains_open is turn.session_remains_open
            turn_values = {**values, "elder_words": turn.user[:80], "snippet": turn.user[:80]}
            _assert_spoken(result, phrases, turn_values)


def test_rules_are_not_suppressed_and_model_can_add_emergency() -> None:
    phrases = load_phrases()
    suppressed = DialogSession(
        "medication_reminder",
        phrases,
        understanding=Understanding(_FixedModel("taken")),
    )
    suppressed.start()
    beat = suppressed.user_turn("सीने में दर्द हो रहा है")
    assert beat.states == ["Emergency"]
    assert beat.events == ["emergency"]
    assert beat.session_remains_open is True

    added = DialogSession(
        "medication_reminder",
        phrases,
        understanding=Understanding(_FixedModel("emergency")),
    )
    added.start()
    beat = added.user_turn("बस यूँ ही हाल पूछ रहा हूँ")
    assert beat.states == ["Emergency"]

    text = TextChannel(DialogSession("daily_checkin", phrases))
    opening = text.start()
    assert opening
    assert all(line for line in opening)


def test_unknown_step_and_closed_session() -> None:
    phrases = load_phrases()
    session = DialogSession("daily_checkin", phrases)
    session.start()
    done = session.user_turn("आज बहुत अच्छा हूँ")
    assert done.states == ["Close"]
    try:
        session.user_turn("फिर से")
    except DialogError:
        pass
    else:
        raise AssertionError("closed session should reject another turn")
    other = DialogSession("daily_checkin", phrases)
    other.start()
    closed = other.user_turn("आज मौसम अच्छा है")
    assert closed.phrase_ids == ["close.polite"]
    assert closed.events == []


def _assert_beat(
    beat: Beat,
    states: list[str],
    phrase_ids: list[str],
    events: list[str],
    script_id: str = "",
) -> None:
    assert beat.states == states, script_id
    assert beat.phrase_ids == phrase_ids, script_id
    assert beat.events == events, script_id


def _assert_spoken(beat: Beat, phrases: dict[str, Phrase], values: dict[str, str]) -> None:
    rendered = [render(phrases[phrase_id].text, values) for phrase_id in beat.phrase_ids]
    assert beat.spoken == rendered
