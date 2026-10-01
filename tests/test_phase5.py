from saathi.channels.phone import ScriptedLeg, run_reminder_call
from saathi.phrases import load_phrases


def test_a_call_with_speech_finishes_the_reminder() -> None:
    phrases = load_phrases()
    leg = ScriptedLeg(speech=["हाँ, ले ली"], digits=[])
    beat = run_reminder_call(leg, phrases)
    assert "क्या आपने बीपी की दवा ले ली?" in leg.said
    assert phrases["ask.dtmf"].text not in leg.said
    assert "बहुत अच्छा बाबूजी। धन्यवाद।" in beat.spoken
    assert "Close" in beat.states


def test_dtmf_one_counts_as_taken_when_speech_fails() -> None:
    phrases = load_phrases()
    leg = ScriptedLeg(speech=[None], digits=["1"])
    beat = run_reminder_call(leg, phrases)
    assert phrases["ask.dtmf"].text in leg.said
    assert "बहुत अच्छा बाबूजी। धन्यवाद।" in beat.spoken
    assert "ठीक है बाबूजी। अपना ख्याल रखिए।" in beat.spoken
