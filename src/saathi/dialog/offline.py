"""Offline NLU used when no live model is configured. It can only add emergencies."""

from saathi.dialog.emergency import EmergencyDetector
from saathi.dialog.nlu import IntentResult, keyword_fallback

# Dialect and roman paraphrases the phrase list does not contain.
_PARAPHRASES = (
    "हदये",
    "सांस फूल",
    "खून निकल",
    "saans atak",
    "saans ruk",
    "gir pare",
    "behosh",
    "ghabraya",
    "गिर पड़ल",
    "bura haal",
)


class OfflineModel:
    def __init__(self, detector: EmergencyDetector) -> None:
        self._detector = detector

    def classify(self, text: str, dialog_state: str, prompt: str) -> IntentResult:
        del prompt
        folded = text.casefold()
        paraphrase = any(item.casefold() in folded for item in _PARAPHRASES)
        if self._detector.is_emergency(text) or paraphrase:
            return IntentResult(intent="emergency", confidence=0.95, slots={})
        return keyword_fallback(text, dialog_state)
