"""Stub NLU: keywords when the model fails, and low confidence becomes confused."""

from saathi.dialog.nlu import (
    FailingModel,
    IntentResult,
    NluUnavailable,
    Understanding,
    apply_confidence_floor,
    keyword_fallback,
    load_prompt,
)


class _RecordingModel:
    def __init__(self, result: IntentResult | None, fail: bool = False) -> None:
        self.result = result
        self.fail = fail
        self.prompt = ""

    def classify(self, text: str, dialog_state: str, prompt: str) -> IntentResult:
        del text, dialog_state
        self.prompt = prompt
        if self.fail or self.result is None:
            raise NluUnavailable("down")
        return self.result


def test_prompt_lists_intents_and_forbids_advice() -> None:
    prompt = load_prompt()
    for name in (
        "taken",
        "not_yet",
        "later",
        "confused",
        "wellbeing_good",
        "wellbeing_okay",
        "wellbeing_unwell",
        "emergency",
        "other",
    ):
        assert name in prompt
    assert "medical advice" in prompt
    assert "Awadhi" in prompt


def test_model_failure_uses_keywords() -> None:
    model = _RecordingModel(None, fail=True)
    understanding = Understanding(model)
    result = understanding.understand("हाँ, ले ली", "AskTaken")
    assert result.intent == "taken"
    assert "medical advice" in model.prompt
    assert keyword_fallback("बाद में याद दिलाना", "AskTaken").intent == "later"
    assert keyword_fallback("अभी नहीं", "AskTaken").intent == "not_yet"
    assert keyword_fallback("क्या कहा?", "AskTaken").intent == "other"
    assert keyword_fallback("तबियत ठीक नहीं है", "AskWellbeing").intent == "wellbeing_unwell"
    assert keyword_fallback("आज बहुत अच्छा हूँ", "AskWellbeing").intent == "wellbeing_good"
    assert keyword_fallback("ठीक हूँ, चल रहा है", "AskWellbeing").intent == "wellbeing_okay"
    assert keyword_fallback("हाँ", "FollowUpUnwell").slots["family"] == "yes"
    assert keyword_fallback("नहीं", "FollowUpUnwell").slots["family"] == "no"


def test_confidence_below_floor_is_confused() -> None:
    raw = IntentResult(intent="taken", confidence=0.59, slots={"x": "y"})
    lowered = apply_confidence_floor(raw)
    assert lowered.intent == "confused"
    assert lowered.slots == {}
    model = _RecordingModel(raw)
    assert Understanding(model).understand("हाँ", "AskTaken").intent == "confused"
    failing = FailingModel()
    try:
        failing.classify("x", "AskTaken", "prompt")
    except NluUnavailable:
        pass
    else:
        raise AssertionError("expected NluUnavailable")
