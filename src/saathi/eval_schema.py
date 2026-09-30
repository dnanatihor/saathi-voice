"""Schemas for eval/utterances.yaml and eval/dialogs/*.yaml."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from saathi.models import EventType
from saathi.phrases import Phrase

Intent = Literal[
    "taken",
    "not_yet",
    "later",
    "confused",
    "wellbeing_good",
    "wellbeing_okay",
    "wellbeing_unwell",
    "emergency",
    "other",
]
ScriptForm = Literal["devanagari", "roman", "dialect"]
Flow = Literal["medication_reminder", "daily_checkin"]
TurnKind = Literal["speech", "silence"]
Audience = Literal["caregiver", "emergency_contacts"]
NotificationReason = Literal["missed", "emergency", "checkin_unwell"]

INTENTS: frozenset[str] = frozenset(
    {
        "taken",
        "not_yet",
        "later",
        "confused",
        "wellbeing_good",
        "wellbeing_okay",
        "wellbeing_unwell",
        "emergency",
        "other",
    }
)

MEDICATION_STATES = frozenset(
    {
        "Greet",
        "Remind",
        "AskTaken",
        "Taken",
        "Snooze",
        "Clarify",
        "Missed",
        "NotifyCaregiver",
        "Close",
        "Emergency",
    }
)
CHECKIN_STATES = frozenset(
    {
        "Greet",
        "AskWellbeing",
        "FollowUpUnwell",
        "NotifyCaregiver",
        "Close",
        "Emergency",
    }
)
FLOW_STATES: dict[Flow, frozenset[str]] = {
    "medication_reminder": MEDICATION_STATES,
    "daily_checkin": CHECKIN_STATES,
}
EVENT_TYPES = frozenset(item.value for item in EventType)


class Utterance(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    intent: Intent
    script: ScriptForm
    mentions_pain_or_health: bool


class UtteranceSet(BaseModel):
    schema_version: Literal[1]
    utterances: list[Utterance] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> "UtteranceSet":
        ids = [item.id for item in self.utterances]
        if len(ids) != len(set(ids)):
            raise ValueError("utterance ids must be unique")
        return self


class NotificationExpectation(BaseModel):
    audience: Audience
    reason: NotificationReason
    template_id: str = Field(min_length=1)


class DialogBeat(BaseModel):
    states: list[str] = Field(min_length=1)
    phrase_ids: list[str] = Field(min_length=1)
    events: list[str] = Field(default_factory=list)
    notifications: list[NotificationExpectation] = Field(default_factory=list)
    session_remains_open: bool = False


class DialogTurn(DialogBeat):
    user: str
    kind: TurnKind = "speech"

    @model_validator(mode="after")
    def text_matches_kind(self) -> "DialogTurn":
        if self.kind == "silence" and self.user != "":
            raise ValueError("silence turns have empty user text")
        if self.kind == "speech" and not self.user.strip():
            raise ValueError("speech turns need user text")
        return self


class DialogScript(BaseModel):
    schema_version: Literal[1]
    id: str = Field(min_length=1)
    flow: Flow
    prior_snoozes: int = Field(default=0, ge=0, le=2)
    opening: DialogBeat
    turns: list[DialogTurn] = Field(min_length=1)

    @model_validator(mode="after")
    def known_states_and_events(self) -> "DialogScript":
        allowed = FLOW_STATES[self.flow]
        beats: list[DialogBeat] = [self.opening, *self.turns]
        for beat in beats:
            unknown_states = set(beat.states) - allowed
            if unknown_states:
                raise ValueError(f"{self.id} has unknown states: {sorted(unknown_states)}")
            unknown_events = set(beat.events) - EVENT_TYPES
            if unknown_events:
                raise ValueError(f"{self.id} has unknown events: {sorted(unknown_events)}")
        return self


def _load_mapping(path: Path) -> dict[str, object]:
    import yaml

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must be a mapping")
    return loaded


def load_utterance_set(path: Path) -> UtteranceSet:
    return UtteranceSet.model_validate(_load_mapping(path))


def load_dialog_scripts(directory: Path) -> list[DialogScript]:
    paths = sorted(directory.glob("*.yaml"))
    if not paths:
        raise ValueError(f"no dialog scripts in {directory}")
    scripts = [DialogScript.model_validate(_load_mapping(path)) for path in paths]
    ids = [script.id for script in scripts]
    if len(ids) != len(set(ids)):
        raise ValueError("dialog script ids must be unique")
    return scripts


def assert_phrase_ids_exist(scripts: list[DialogScript], phrases: dict[str, Phrase]) -> None:
    for script in scripts:
        beats: list[DialogBeat] = [script.opening, *script.turns]
        for beat in beats:
            missing = [phrase_id for phrase_id in beat.phrase_ids if phrase_id not in phrases]
            if missing:
                raise ValueError(f"{script.id} references missing phrases: {missing}")
            for note in beat.notifications:
                if note.template_id not in phrases:
                    raise ValueError(f"{script.id} references missing template {note.template_id}")
                if phrases[note.template_id].spoken:
                    raise ValueError(f"{note.template_id} is spoken; notifications use templates")
