"""Weekly adherence grid for the caregiver dashboard."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session as DbSession
from sqlmodel import select

from saathi.models import (
    DoseOccurrence,
    Event,
    EventType,
    Medication,
    Schedule,
    Session,
    SessionKind,
    decode_days,
    decode_times,
)

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def week_grid(db: DbSession, elder_id: int, week_start: date) -> list[dict[str, str]]:
    cells: list[dict[str, str]] = []
    medications = db.exec(select(Medication).where(Medication.elder_id == elder_id)).all()
    for medication in medications:
        schedules = db.exec(select(Schedule).where(Schedule.medication_id == medication.id)).all()
        for schedule in schedules:
            days = set(decode_days(schedule.days))
            times = decode_times(schedule.times_of_day)
            for offset in range(7):
                day = week_start + timedelta(days=offset)
                weekday = _WEEKDAYS[day.weekday()]
                if weekday not in days:
                    continue
                if schedule.start_date > day:
                    continue
                if schedule.end_date is not None and schedule.end_date < day:
                    continue
                for clock in times:
                    cells.append(
                        {
                            "day": weekday,
                            "date": day.isoformat(),
                            "time": clock,
                            "label": medication.spoken_label,
                            "status": _status(db, schedule.id, day, clock),
                        }
                    )
    return cells


def _status(db: DbSession, schedule_id: int | None, day: date, clock: str) -> str:
    if schedule_id is None:
        return "pending"
    occurrence = db.exec(
        select(DoseOccurrence).where(DoseOccurrence.schedule_id == schedule_id)
    ).all()
    matched = [
        item
        for item in occurrence
        if item.scheduled_for.startswith(day.isoformat()) and f"T{clock}" in item.scheduled_for
    ]
    calls = db.exec(select(Session).where(Session.schedule_id == schedule_id)).all()
    session_ids = [
        call.id for call in calls if call.id is not None and _on_day(call.started_at, day)
    ]
    events: list[Event] = []
    for session_id in session_ids:
        events.extend(db.exec(select(Event).where(Event.session_id == session_id)).all())
    names = {item.event_type for item in events}
    if EventType.taken in names:
        return "taken"
    if EventType.missed in names:
        return "missed"
    if any(item.outcome == "missed_by_system" for item in matched):
        return "missed_by_system"
    if EventType.snoozed in names:
        return "snoozed"
    if matched:
        return "pending"
    return "pending"


def _on_day(moment: datetime, day: date) -> bool:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(ZoneInfo("Asia/Kolkata")).date() == day


def checkin_summaries(db: DbSession, elder_id: int) -> list[dict[str, str]]:
    calls = db.exec(
        select(Session).where(Session.elder_id == elder_id, Session.kind == SessionKind.checkin)
    ).all()
    summaries: list[dict[str, str]] = []
    for call in calls:
        if "ने कहा" not in call.transcript and call.kind != "checkin":
            continue
        summaries.append(
            {
                "session_id": str(call.id),
                "state": call.state,
                "transcript": call.transcript,
            }
        )
    return summaries
