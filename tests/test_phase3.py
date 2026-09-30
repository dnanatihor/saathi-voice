import wave

from saathi.dialog.llm import LangchainStructured, StructuredNlu
from saathi.dialog.nlu import IntentResult, NluUnavailable, Understanding
from saathi.eval_report import nlu_metrics, speech_table
from saathi.paths import REPO_ROOT
from saathi.speech.base import STTProvider
from saathi.speech.providers.dev import DropLastSTT, IdentitySTT, SubstitutionSTT


def test_speech_protocols_are_implemented() -> None:
    providers: tuple[STTProvider, ...] = (IdentitySTT(), SubstitutionSTT(), DropLastSTT())
    assert len(providers) == 3


def test_combined_emergency_recall_is_complete() -> None:
    metrics = nlu_metrics()
    assert metrics["emergency_recall"] == 1.0
    assert 0.0 < metrics["intent_accuracy"] <= 1.0


def test_speech_harness_reports_real_differences() -> None:
    rows = {str(row["provider"]): row for row in speech_table()}
    assert rows["identity"]["wer"] == 0.0
    assert float(rows["substitution"]["wer"]) > 0.0
    assert float(rows["drop-last"]["wer"]) > 0.0
    for row in rows.values():
        assert float(row["latency_p95_s"]) < 3.5
    assert float(rows["drop-last"]["wer"]) != float(rows["substitution"]["wer"])


def test_asr_directory_has_a_wav_per_clip() -> None:
    metrics = nlu_metrics()
    assert metrics["false_emergency_rate"] == 0.0
    folder = REPO_ROOT / "eval/asr"
    for index in range(1, 11):
        path = folder / f"c{index:02d}.wav"
        with wave.open(str(path)) as clip:
            assert clip.getnframes() > 0


def test_structured_nlu_accepts_an_injected_model() -> None:
    class Chat:
        def invoke(self, messages: list[tuple[str, str]]) -> IntentResult:
            assert messages[0][0] == "system"
            return IntentResult(intent="taken", confidence=0.91, slots={})

    result = Understanding(StructuredNlu(Chat())).understand("हाँ ले ली", "AskTaken")
    assert result.intent == "taken"


def test_live_model_is_not_called_without_langchain(monkeypatch: object) -> None:
    import builtins

    real_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name == "langchain.chat_models" or name.startswith("langchain"):
            raise ImportError("blocked in tests")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)  # type: ignore[attr-defined]
    try:
        LangchainStructured("unused").invoke([("human", "नमस्ते")])
    except NluUnavailable as exc:
        assert "not installed" in str(exc)
    else:
        raise AssertionError("expected NluUnavailable")
