"""Emergency rules: phrase-list recall is 100%, and negation does not fire."""

import re

from saathi.config import emergency_phrase_path, load_config
from saathi.dialog.emergency import EmergencyDetector, normalize
from saathi.eval_schema import load_utterance_set
from saathi.paths import REPO_ROOT
from saathi.phrases import load_emergency_phrases

_NEGATION_AFTER = re.compile(r"^(?:\s|[.।,])*?(?:नहीं|नही|nahin|nahi|not\b)")


def _active_phrase(text: str, phrases: list[str]) -> bool:
    """Independent check used only to score recall, not the production matcher."""
    normalized = " ".join(text.casefold().split())
    for phrase in sorted((item.strip() for item in phrases), key=len, reverse=True):
        if not phrase:
            continue
        folded = phrase.casefold()
        start = 0
        while True:
            index = normalized.find(folded, start)
            if index < 0:
                break
            end = index + len(folded)
            if folded.isascii() and " " not in folded:
                before = normalized[index - 1] if index else " "
                after = normalized[end] if end < len(normalized) else " "
                if before.isalnum() or after.isalnum():
                    start = index + 1
                    continue
            tail = normalized[end : end + 16]
            if _NEGATION_AFTER.search(tail) is None:
                return True
            start = index + 1
    return False


def test_spec_examples_and_negation() -> None:
    phrases = load_emergency_phrases(emergency_phrase_path(load_config()))
    detector = EmergencyDetector(phrases)
    assert detector.is_emergency("सीने में दर्द हो रहा है")
    assert detector.is_emergency("साँस नहीं आ रही")
    assert detector.is_emergency("please HELP me")
    assert detector.is_emergency("main gir gaya")
    assert detector.is_emergency("  ") is False
    assert detector.is_emergency("दर्द नहीं है") is False
    assert detector.is_emergency("सीने में दर्द नहीं है") is False
    assert detector.is_emergency("seene mein dard nahi hai") is False
    assert detector.is_emergency("chest pain, nahi hai") is False
    assert detector.is_emergency("the helper called") is False
    assert detector.is_emergency("मौसम अच्छा है") is False
    assert EmergencyDetector(["", "  "]).is_emergency("help") is False
    assert normalize("  A  B \n") == "a b"


def test_phrase_list_recall_is_complete() -> None:
    phrases = load_emergency_phrases(emergency_phrase_path(load_config()))
    detector = EmergencyDetector(phrases)
    utterances = load_utterance_set(REPO_ROOT / "eval/utterances.yaml").utterances
    phrase_list = [item for item in utterances if _active_phrase(item.text, phrases)]
    assert len(phrase_list) >= 40
    missed = [item.id for item in phrase_list if not detector.is_emergency(item.text)]
    assert missed == []
    false_alarms = [
        item.id
        for item in utterances
        if item.intent != "emergency" and detector.is_emergency(item.text)
    ]
    assert false_alarms == []
