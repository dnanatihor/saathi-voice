"""Domain models from SPEC.md §4."""

from datetime import UTC, date, datetime
from enum import StrEnum
from json import dumps, loads

from pydantic import field_validator
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class NotificationChannel(StrEnum):
    telegram = "telegram"
    email = "email"


class ConsentSubject(StrEnum):
    caregiver = "caregiver"
    elder = "elder"


class ConsentPurpose(StrEnum):
    reminders = "reminders"
    checkins = "checkins"
    storing_transcripts = "storing_transcripts"


class ConsentMethod(StrEnum):
    dashboard_checkbox = "dashboard_checkbox"
    verbal = "verbal"


class SessionKind(StrEnum):
    reminder = "reminder"
    checkin = "checkin"


class EventType(StrEnum):
    reminder_sent = "reminder_sent"
    taken = "taken"
    snoozed = "snoozed"
    missed = "missed"
    missed_by_system = "missed_by_system"
    checkin_result = "checkin_result"
    emergency = "emergency"
    notification_sent = "notification_sent"
    consent_recorded = "consent_recorded"
    erasure = "erasure"


_WEEKDAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})


def _require_hhmm(value: str) -> str:
    datetime.strptime(value, "%H:%M")
    return value


def encode_times(times: list[str]) -> str:
    encoded = [_require_hhmm(item) for item in times]
    return dumps(encoded)


def decode_times(raw: str) -> list[str]:
    loaded = loads(raw)
    if not isinstance(loaded, list):
        raise ValueError("times_of_day must be a JSON list")
    times: list[str] = []
    for item in loaded:
        if not isinstance(item, str):
            raise ValueError("times_of_day entries must be strings")
        times.append(_require_hhmm(item))
    return times


def encode_days(days: list[str]) -> str:
    unknown = set(days) - _WEEKDAYS
    if unknown:
        raise ValueError(f"unknown weekdays: {sorted(unknown)}")
    return dumps(days)


def decode_days(raw: str) -> list[str]:
    loaded = loads(raw)
    if not isinstance(loaded, list):
        raise ValueError("days must be a JSON list")
    days: list[str] = []
    for item in loaded:
        if not isinstance(item, str) or item not in _WEEKDAYS:
            raise ValueError("days entries must be weekday names")
        days.append(item)
    return days


class Caregiver(SQLModel, table=True):
    __tablename__ = "caregivers"

    id: int | None = Field(default=None, primary_key=True)
    login: str
    relationship: str
    notification_channel: NotificationChannel
    password_hash: str = ""
    channel_address: str = ""


class Elder(SQLModel, table=True):
    __tablename__ = "elders"

    id: int | None = Field(default=None, primary_key=True)
    caregiver_id: int = Field(foreign_key="caregivers.id")
    display_name: str
    honorific: str
    language: str = "hi"
    preferred_speech_rate: float = 0.85
    call_window_start: str = "08:00"
    call_window_end: str = "20:00"
    timezone: str = "Asia/Kolkata"
    family_message_path: str = ""

    @field_validator("language")
    @classmethod
    def only_hindi(cls, value: str) -> str:
        if value != "hi":
            raise ValueError("only hi is supported")
        return value

    @field_validator("call_window_start", "call_window_end")
    @classmethod
    def hhmm(cls, value: str) -> str:
        return _require_hhmm(value)


class Contact(SQLModel, table=True):
    __tablename__ = "contacts"

    id: int | None = Field(default=None, primary_key=True)
    elder_id: int = Field(foreign_key="elders.id")
    name: str
    relationship: str
    channel: NotificationChannel
    channel_address: str
    emergency: bool


class Medication(SQLModel, table=True):
    __tablename__ = "medications"

    id: int | None = Field(default=None, primary_key=True)
    elder_id: int = Field(foreign_key="elders.id")
    name: str
    spoken_label: str
    instructions: str


class Schedule(SQLModel, table=True):
    __tablename__ = "schedules"

    id: int | None = Field(default=None, primary_key=True)
    medication_id: int = Field(foreign_key="medications.id")
    times_of_day: str
    days: str
    start_date: date
    end_date: date | None = None


class Consent(SQLModel, table=True):
    """Append-only record. Withdrawal and erasure are Phase 6."""

    __tablename__ = "consents"

    id: int | None = Field(default=None, primary_key=True)
    elder_id: int = Field(foreign_key="elders.id")
    subject: ConsentSubject
    subject_name: str
    purpose: ConsentPurpose
    recorded_at: datetime = Field(default_factory=utc_now)
    method: ConsentMethod
    transcript: str | None = None
    granted: bool = True


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: int | None = Field(default=None, primary_key=True)
    elder_id: int = Field(foreign_key="elders.id")
    schedule_id: int | None = Field(default=None, foreign_key="schedules.id")
    kind: SessionKind
    state: str
    prior_snoozes: int = 0
    dialog_state_json: str = ""
    transcript: str = ""
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: int | None = Field(default=None, primary_key=True)
    elder_id: int | None = Field(default=None, foreign_key="elders.id")
    session_id: int | None = Field(default=None, foreign_key="sessions.id")
    event_type: EventType
    created_at: datetime = Field(default_factory=utc_now)
    payload_json: str = "{}"


class DoseOccurrence(SQLModel, table=True):
    __tablename__ = "dose_occurrences"

    id: int | None = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="schedules.id")
    scheduled_for: str
    outcome: str
    session_id: int | None = Field(default=None, foreign_key="sessions.id")


class SnoozeReminder(SQLModel, table=True):
    __tablename__ = "snooze_reminders"

    id: int | None = Field(default=None, primary_key=True)
    elder_id: int = Field(foreign_key="elders.id")
    schedule_id: int = Field(foreign_key="schedules.id")
    due_at: str
    prior_snoozes: int
    done: bool = False


class LinkCode(SQLModel, table=True):
    __tablename__ = "link_codes"

    code: str = Field(primary_key=True)
    caregiver_id: int = Field(foreign_key="caregivers.id")
    created_at: datetime = Field(default_factory=utc_now)
