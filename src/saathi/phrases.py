"""Load assistant speech from phrases/hi.yaml. Spoken lines stay within 12 words."""

import re
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from saathi.paths import REPO_ROOT

SPOKEN_WORD_LIMIT = 12
SPEC_EMERGENCY_PHRASES = (
    "सीने में दर्द",
    "साँस नहीं",
    "गिर गया",
    "गिर गई",
    "मदद करो",
    "बचाओ",
    "chest pain",
    "help",
    "seene mein dard",
    "saans nahi",
    "gir gaya",
    "gir gayi",
    "madad karo",
    "bachao",
)
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
ALLOWED_PLACEHOLDERS = frozenset(
    {"honorific", "spoken_label", "instructions", "elder_words", "snippet"}
)


class Phrase(BaseModel):
    text: str = Field(min_length=1)
    spoken: bool = True

    @model_validator(mode="after")
    def check_template(self) -> "Phrase":
        placeholders = set(_PLACEHOLDER.findall(self.text))
        unknown = placeholders - ALLOWED_PLACEHOLDERS
        if unknown:
            raise ValueError(f"unknown placeholders: {sorted(unknown)}")
        if self.spoken and len(self.text.split()) > SPOKEN_WORD_LIMIT:
            raise ValueError(f"spoken phrase exceeds {SPOKEN_WORD_LIMIT} words: {self.text}")
        return self


class PhraseFile(BaseModel):
    phrases: dict[str, Phrase] = Field(min_length=1)


class EmergencyPhraseList(BaseModel):
    phrases: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def nonempty_unique(self) -> "EmergencyPhraseList":
        cleaned = [item.strip() for item in self.phrases]
        if any(not item for item in cleaned):
            raise ValueError("emergency phrases must be non-empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("emergency phrases must be unique")
        self.phrases = cleaned
        return self


def _load_mapping(path: Path) -> dict[str, object]:
    import yaml

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must be a mapping")
    return loaded


def load_phrases(path: Path | None = None) -> dict[str, Phrase]:
    phrase_path = path if path is not None else REPO_ROOT / "src/saathi/dialog/phrases/hi.yaml"
    return PhraseFile.model_validate(_load_mapping(phrase_path)).phrases


def load_emergency_phrases(path: Path) -> list[str]:
    return EmergencyPhraseList.model_validate(_load_mapping(path)).phrases
