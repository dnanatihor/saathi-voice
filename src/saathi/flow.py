"""Persist a dialog beat and send the notifications it asks for."""

from collections.abc import Callable
from datetime import datetime

from sqlmodel import Session as DbSession
from sqlmodel import select

from saathi.dialog.graph import Beat, DialogSession, Persona
from saathi.eval_schema import Flow
from saathi.models import (
    Contact,
    Elder,
    Event,
    EventType,
    Medication,
    Session,
    SessionKind,
)
from saathi.notify.base import Notifier
from saathi.notify.dispatch import notify_emergency, send_logged
from saathi.phrases import Phrase, render
from saathi.scheduler import _caregiver_contact, queue_snooze


def open_checkin(db: DbSession, elder: Elder, phrases: dict[str, Phrase]) -> Session:
    dialog = DialogSession(
        "daily_checkin",
        phrases,
        persona=Persona(honorific=elder.honorific),
    )
    beat = dialog.start()
    call = Session(
        elder_id=elder.id if elder.id is not None else 0,
        kind=SessionKind.checkin,
        state=beat.states[-1],
        dialog_state_json=dialog.export_state(),
        transcript="\n".join(beat.spoken),
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    _store_events(db, call, beat)
    return call


def apply_user_text(
    db: DbSession,
    call: Session,
    text: str,
    phrases: dict[str, Phrase],
    notifier: Notifier | None,
    now: datetime,
    *,
    snooze_minutes: int = 15,
    sleep: Callable[[float], None] | None = None,
) -> Beat:
    dialog = _resume(db, call, phrases)
    beat = dialog.user_turn(text)
    call.state = beat.states[-1]
    call.dialog_state_json = dialog.export_state()
    call.transcript = (call.transcript + "\n" + text + "\n" + "\n".join(beat.spoken)).strip()
    if call.state == "Close":
        call.ended_at = now
    db.add(call)
    _store_events(db, call, beat)
    _deliver(db, call, beat, phrases, notifier, now, snooze_minutes, text, sleep)
    db.commit()
    return beat


def _resume(db: DbSession, call: Session, phrases: dict[str, Phrase]) -> DialogSession:
    elder = db.get(Elder, call.elder_id)
    medication = None
    if call.schedule_id is not None:
        from saathi.models import Schedule

        schedule = db.get(Schedule, call.schedule_id)
        if schedule is not None:
            medication = db.get(Medication, schedule.medication_id)
    persona = Persona(
        honorific=elder.honorific if elder is not None else "",
        spoken_label=medication.spoken_label if medication is not None else "",
        instructions=medication.instructions if medication is not None else "",
    )
    flow: SessionKind = call.kind
    dialog_flow: Flow = "daily_checkin" if flow == SessionKind.checkin else "medication_reminder"
    dialog = DialogSession(dialog_flow, phrases, prior_snoozes=call.prior_snoozes, persona=persona)
    dialog.restore(call.dialog_state_json)
    return dialog


def _store_events(db: DbSession, call: Session, beat: Beat) -> None:
    assert call.id is not None
    for name in beat.events:
        db.add(
            Event(
                elder_id=call.elder_id,
                session_id=call.id,
                event_type=EventType(name),
                payload_json="{}",
            )
        )
    db.commit()


def _deliver(
    db: DbSession,
    call: Session,
    beat: Beat,
    phrases: dict[str, Phrase],
    notifier: Notifier | None,
    now: datetime,
    snooze_minutes: int,
    user_text: str,
    sleep: Callable[[float], None] | None,
) -> None:
    if notifier is None:
        if "snoozed" in beat.events:
            queue_snooze(db, call, now, snooze_minutes)
        return
    elder = db.get(Elder, call.elder_id)
    medication = _medication(db, call)
    values = {
        "honorific": elder.honorific if elder is not None else "",
        "spoken_label": medication.spoken_label if medication is not None else "",
        "instructions": medication.instructions if medication is not None else "",
        "elder_words": user_text[:80],
        "snippet": user_text[:80],
    }
    if "snoozed" in beat.events:
        queue_snooze(db, call, now, snooze_minutes)
    for note in beat.notifications:
        message = render(phrases[note.template_id].text, values)
        if note.audience == "emergency_contacts":
            contacts = list(db.exec(select(Contact).where(Contact.elder_id == call.elder_id)).all())
            pauses = sleep if sleep is not None else (lambda _seconds: None)
            notify_emergency(
                contacts,
                message,
                notifier,
                elder_id=call.elder_id,
                session_id=call.id,
                log=db.add,
                sleep=pauses,
            )
        else:
            contact = _caregiver_contact(db, call.elder_id)
            if contact is None:
                continue
            send_logged(
                notifier,
                contact,
                message,
                elder_id=call.elder_id,
                session_id=call.id,
                log=db.add,
            )


def _medication(db: DbSession, call: Session) -> Medication | None:
    if call.schedule_id is None:
        return None
    from saathi.models import Schedule

    schedule = db.get(Schedule, call.schedule_id)
    if schedule is None:
        return None
    return db.get(Medication, schedule.medication_id)
