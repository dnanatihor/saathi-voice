"""Retention, erasure, and whether a reminder consent is still in force."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session as DbSession
from sqlmodel import select

from saathi.family import delete_family_file
from saathi.models import (
    Consent,
    ConsentPurpose,
    Contact,
    DoseOccurrence,
    Elder,
    Event,
    EventType,
    Medication,
    Schedule,
    Session,
    SnoozeReminder,
)


def purpose_allowed(db: DbSession, elder_id: int, purpose: ConsentPurpose) -> bool:
    """The latest row for that purpose wins. No row means the call does not start."""
    rows = db.exec(
        select(Consent).where(Consent.elder_id == elder_id, Consent.purpose == purpose)
    ).all()
    if not rows:
        return False
    latest = max(rows, key=lambda row: row.id or 0)
    return latest.granted


def calls_allowed(db: DbSession, elder_id: int) -> bool:
    return purpose_allowed(db, elder_id, ConsentPurpose.reminders)


def purge_old_transcripts(db: DbSession, *, now: datetime, retention_days: int) -> int:
    cutoff = now.astimezone(UTC) - timedelta(days=retention_days)
    cleared = 0
    for call in db.exec(select(Session)).all():
        started = call.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if started.astimezone(UTC) >= cutoff:
            continue
        if call.transcript or call.dialog_state_json:
            call.transcript = ""
            call.dialog_state_json = ""
            db.add(call)
            cleared += 1
    db.commit()
    return cleared


def erase_elder(db: DbSession, elder_id: int) -> None:
    """Remove personal rows and leave one erasure event with no personal content."""
    if db.get(Elder, elder_id) is None:
        return
    medications = db.exec(select(Medication).where(Medication.elder_id == elder_id)).all()
    medication_ids = [item.id for item in medications if item.id is not None]
    schedules: list[Schedule] = []
    for medication_id in medication_ids:
        schedules.extend(
            db.exec(select(Schedule).where(Schedule.medication_id == medication_id)).all()
        )
    schedule_ids = [item.id for item in schedules if item.id is not None]
    for schedule_id in schedule_ids:
        for dose in db.exec(
            select(DoseOccurrence).where(DoseOccurrence.schedule_id == schedule_id)
        ).all():
            db.delete(dose)
    for event in db.exec(select(Event).where(Event.elder_id == elder_id)).all():
        db.delete(event)
    for call in db.exec(select(Session).where(Session.elder_id == elder_id)).all():
        db.delete(call)
    reminders = select(SnoozeReminder).where(SnoozeReminder.elder_id == elder_id)
    for reminder in db.exec(reminders).all():
        db.delete(reminder)
    for contact in db.exec(select(Contact).where(Contact.elder_id == elder_id)).all():
        db.delete(contact)
    for consent in db.exec(select(Consent).where(Consent.elder_id == elder_id)).all():
        db.delete(consent)
    for schedule in schedules:
        db.delete(schedule)
    for medication in medications:
        db.delete(medication)
    elder = db.get(Elder, elder_id)
    if elder is not None:
        delete_family_file(elder.family_message_path)
        db.delete(elder)
    db.commit()
    db.add(Event(elder_id=None, session_id=None, event_type=EventType.erasure, payload_json="{}"))
    db.commit()
