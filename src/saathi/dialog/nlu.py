"""Intent classification. Phase 1 uses a keyword fallback when the model is unavailable."""

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from saathi.eval_schema import Intent
from saathi.paths import REPO_ROOT

PROMPT_PATH = REPO_ROOT / "src/saathi/dialog/prompts/nlu.v1.md"
CONFIDENCE_FLOOR = 0.6

_TAKEN = ("ले ली", "ले लिया", "ले लिए", "खा ली", "खा लिए", "haan", "हाँ")
_NOT_YET = ("अभी नहीं", "नहीं ली", "नहीं खाई", "नहीं खइ", "abhi nahi", "nahi li", "not yet")
_LATER = ("बाद में", "बादे में", "थोड़ी देर", "थोड़ देर", "baad mein", "later")
_UNWELL = ("ठीक नहीं", "तबीयत", "tabiyat", "खराब", "unwell", "kamzor", "कमजोर")
_GOOD = ("बहुत अच्छा", "बढ़िया", "अच्छा हूँ", "badhiya", "accha hoon", "मस्त")
_OKAY = ("ठीक हूँ", "ठीक है", "ठीक बा", "theek", "चल रहा", "chal raha", "च चल", "वैसे ही")


class IntentResult(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    slots: dict[str, str] = Field(default_factory=dict)


class NluUnavailable(Exception):
    """The language model could not be called. Keyword fallback still runs."""


class NluModel(Protocol):
    def classify(self, text: str, dialog_state: str, prompt: str) -> IntentResult: ...


class FailingModel:
    """Phase 1 stand-in. Tests never call a live model."""

    def classify(self, text: str, dialog_state: str, prompt: str) -> IntentResult:
        del text, dialog_state, prompt
        raise NluUnavailable("language model is not configured")


def load_prompt(path: Path | None = None) -> str:
    prompt_path = path if path is not None else PROMPT_PATH
    return prompt_path.read_text(encoding="utf-8")


def apply_confidence_floor(result: IntentResult) -> IntentResult:
    if result.confidence < CONFIDENCE_FLOOR:
        return IntentResult(intent="confused", confidence=result.confidence, slots={})
    return result


def keyword_fallback(text: str, dialog_state: str) -> IntentResult:
    folded = " ".join(text.casefold().split())
    if dialog_state == "AskWellbeing":
        return _wellbeing(folded)
    if dialog_state == "FollowUpUnwell":
        if "हाँ" in text or "haan" in folded or folded == "yes":
            return IntentResult(intent="other", confidence=0.9, slots={"family": "yes"})
        if "नहीं" in text or "nahi" in folded or folded == "no":
            return IntentResult(intent="other", confidence=0.9, slots={"family": "no"})
        return IntentResult(intent="other", confidence=0.4, slots={})
    if _contains(folded, text, _LATER):
        return IntentResult(intent="later", confidence=0.95, slots={})
    if _contains(folded, text, _NOT_YET):
        return IntentResult(intent="not_yet", confidence=0.95, slots={})
    if _contains(folded, text, _TAKEN):
        return IntentResult(intent="taken", confidence=0.95, slots={})
    return IntentResult(intent="other", confidence=0.4, slots={})


def _contains(folded: str, original: str, markers: tuple[str, ...]) -> bool:
    return any(marker.casefold() in folded or marker in original for marker in markers)


def _wellbeing(folded: str) -> IntentResult:
    if _contains(folded, folded, _UNWELL):
        return IntentResult(intent="wellbeing_unwell", confidence=0.9, slots={})
    if _contains(folded, folded, _GOOD):
        return IntentResult(intent="wellbeing_good", confidence=0.9, slots={})
    if _contains(folded, folded, _OKAY):
        return IntentResult(intent="wellbeing_okay", confidence=0.9, slots={})
    return IntentResult(intent="other", confidence=0.4, slots={})


class Understanding:
    """Try the model, then keywords. Low confidence becomes `confused`."""

    def __init__(self, model: NluModel | None = None, prompt: str | None = None) -> None:
        self._model: NluModel = model if model is not None else FailingModel()
        self._prompt = prompt if prompt is not None else load_prompt()

    def understand(self, text: str, dialog_state: str) -> IntentResult:
        try:
            result = self._model.classify(text, dialog_state, self._prompt)
        except NluUnavailable:
            result = keyword_fallback(text, dialog_state)
        return apply_confidence_floor(result)
