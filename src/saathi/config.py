"""Load config.yaml. Secrets are environment variables, never fields here."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from saathi.paths import REPO_ROOT


class CallWindows(BaseModel):
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def hhmm(cls, value: str) -> str:
        datetime.strptime(value, "%H:%M")
        return value

    @field_validator("end")
    @classmethod
    def ends_after_start(cls, value: str, info: ValidationInfo) -> str:
        start = info.data.get("start")
        if isinstance(start, str) and value <= start:
            raise ValueError("call window end must be after start")
        return value


class SnoozeSettings(BaseModel):
    interval_minutes: int = Field(ge=1)
    limit: int = Field(ge=1)


class Providers(BaseModel):
    stt: str | None
    tts: str | None
    llm_model_id: str | None
    notifier: str


class AppConfig(BaseModel):
    timezone: str
    call_windows: CallWindows
    snooze: SnoozeSettings
    silence_timeout_seconds: int = Field(ge=1)
    speech_rate: float = Field(gt=0)
    retention_days: int = Field(ge=1)
    providers: Providers
    emergency_phrase_list: str

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value


def load_config(path: Path | None = None) -> AppConfig:
    import yaml

    config_path = path if path is not None else REPO_ROOT / "config.yaml"
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{config_path} must be a mapping")
    return AppConfig.model_validate(loaded)


def emergency_phrase_path(config: AppConfig, *, root: Path | None = None) -> Path:
    base = root if root is not None else REPO_ROOT
    path = Path(config.emergency_phrase_list)
    if path.is_absolute():
        return path
    return base / path
