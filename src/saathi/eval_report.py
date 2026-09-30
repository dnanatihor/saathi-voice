"""Metrics for the utterance set and the local speech harness."""

import asyncio
from pathlib import Path

from saathi.config import emergency_phrase_path, load_config
from saathi.dialog.emergency import EmergencyDetector
from saathi.dialog.nlu import Understanding
from saathi.dialog.offline import OfflineModel
from saathi.eval_schema import load_utterance_set
from saathi.paths import REPO_ROOT
from saathi.phrases import load_emergency_phrases
from saathi.speech.metrics import transcribe_latency, word_error_rate
from saathi.speech.providers.dev import DropLastSTT, IdentitySTT, SubstitutionSTT

_WELLBEING = {"wellbeing_good", "wellbeing_okay", "wellbeing_unwell"}


def _load_clips(path: Path) -> list[str]:
    import yaml

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("asr clips must be a mapping")
    clips = loaded.get("clips")
    if not isinstance(clips, list):
        raise ValueError("asr clips must be a list")
    references: list[str] = []
    for clip in clips:
        if isinstance(clip, dict) and isinstance(clip.get("reference"), str):
            references.append(clip["reference"])
    return references


def nlu_metrics() -> dict[str, float]:
    phrases = load_emergency_phrases(emergency_phrase_path(load_config()))
    detector = EmergencyDetector(phrases)
    understanding = Understanding(OfflineModel(detector))
    utterances = load_utterance_set(REPO_ROOT / "eval/utterances.yaml").utterances
    correct = 0
    emergency_total = 0
    emergency_caught = 0
    other_total = 0
    false_emergency = 0
    for item in utterances:
        state = "AskWellbeing" if item.intent in _WELLBEING else "AskTaken"
        predicted = understanding.understand(item.text, state).intent
        if predicted == item.intent:
            correct += 1
        if item.intent == "emergency":
            emergency_total += 1
            rules = detector.is_emergency(item.text)
            if rules or predicted == "emergency":
                emergency_caught += 1
        else:
            other_total += 1
            if predicted == "emergency":
                false_emergency += 1
    return {
        "intent_accuracy": correct / len(utterances),
        "emergency_recall": emergency_caught / emergency_total,
        "false_emergency_rate": false_emergency / other_total,
        "utterances": float(len(utterances)),
    }


def speech_table() -> list[dict[str, float | str]]:
    references = _load_clips(REPO_ROOT / "eval/asr/clips.yaml")
    rows: list[dict[str, float | str]] = []
    for provider in (IdentitySTT(), SubstitutionSTT(), DropLastSTT()):
        rates: list[float] = []
        latencies: list[float] = []
        for reference in references:
            hypothesis, elapsed = asyncio.run(transcribe_latency(provider, reference))
            rates.append(word_error_rate(reference, hypothesis))
            latencies.append(elapsed)
        rows.append(
            {
                "provider": provider.name,
                "wer": sum(rates) / len(rates),
                "latency_p50_s": _percentile(latencies, 50),
                "latency_p95_s": _percentile(latencies, 95),
            }
        )
    return rows


def _percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = round((percent / 100) * (len(ordered) - 1))
    return ordered[index]
