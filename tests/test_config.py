"""Shipped config matches the numbers named in SPEC.md."""

from saathi.config import emergency_phrase_path, load_config
from saathi.paths import REPO_ROOT


def test_shipped_config_matches_spec_defaults() -> None:
    config = load_config()
    assert config.timezone == "Asia/Kolkata"
    assert config.call_windows.start == "08:00"
    assert config.call_windows.end == "20:00"
    assert config.snooze.interval_minutes == 15
    assert config.snooze.limit == 2
    assert config.silence_timeout_seconds == 6
    assert config.speech_rate == 0.85
    assert config.retention_days == 30
    assert config.providers.notifier == "telegram"
    assert config.providers.stt is None
    assert config.providers.tts is None
    assert config.providers.llm_model_id is None
    phrase_path = emergency_phrase_path(config)
    assert phrase_path.is_file()
    assert phrase_path.is_relative_to(REPO_ROOT)


def test_config_has_no_secret_fields() -> None:
    from saathi.config import AppConfig

    names = {name.lower() for name in AppConfig.model_fields}
    assert names.isdisjoint({"password", "token", "secret", "api_key"})
