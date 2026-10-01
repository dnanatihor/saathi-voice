"""Dose times, catch-up after restart, and snooze follow-ups."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session as DbSession
from sqlmodel import select

from saathi.dialog.graph import DialogSession, Persona
from saathi.models import (
    Caregiver,
    Contact,
    DoseOccurrence,
    Elder,
    Event,
    EventType,
    Medication,
    Schedule,
    Session,
    SessionKind,
    SnoozeReminder,
    decode_days,
    decode_times,
)
from saathi.notify.base import Notifier
from saathi.notify.dispatch import send_logged
from saathi.phrases import Phrase, render
from saathi.privacy import calls_allowed, purge_old_transcripts

CATCH_UP = timedelta(minutes=30)
_TICK_JOB = "saathi-tick"
_RETENTION_JOB = "saathi-retention"


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment
        self.slept = 0.0

    def now(self) -> datetime:
        return self.moment

    def sleep(self, seconds: float) -> None:
        self.slept += seconds
        self.moment = self.moment + timedelta(seconds=seconds)


def tick() -> None:
    """Placeholder invoked by APScheduler. Callers drive time with advance()."""
    return None


def retention_job(database_url: str, retention_days: int = 30) -> None:
    """Daily clear of transcripts older than the retention window."""
    from saathi.db import db_session, make_engine

    engine = make_engine(database_url)
    with db_session(engine) as db:
        purge_old_transcripts(
            db,
            now=datetime.now(ZoneInfo("Asia/Kolkata")),
            retention_days=retention_days,
        )


def register_tick(database_url: str, timezone: str) -> BackgroundScheduler:
    """One persistent APScheduler job. The grace window is the 30 minute catch-up."""
    store = SQLAlchemyJobStore(url=database_url)
    scheduler = BackgroundScheduler(jobstores={"default": store}, timezone=timezone)
    scheduler.add_job(
        tick,
        CronTrigger(minute="*", timezone=timezone),
        id=_TICK_JOB,
        replace_existing=True,
        misfire_grace_time=int(CATCH_UP.total_seconds()),
    )
    scheduler.add_job(
        retention_job,
        CronTrigger(hour=3, minute=0, timezone=timezone),
        id=_RETENTION_JOB,
        kwargs={"database_url": database_url, "retention_days": 30},
        replace_existing=True,
    )
    return scheduler


def advance(
    db: DbSession,
    now: datetime,
    phrases: dict[str, Phrase],
    *,
    notifier: Notifier | None = None,
) -> list[Session]:
    zone = now.tzinfo if now.tzinfo is not None else ZoneInfo("Asia/Kolkata")
    local_now = now.astimezone(zone)
    opened: list[Session] = []
    for schedule in db.exec(select(Schedule)).all():
        opened.extend(_due_slots(db, schedule, local_now, phrases, notifier))
    opened.extend(_due_snoozes(db, local_now, phrases, notifier))
    db.commit()
    for call in opened:
        db.refresh(call)
    return opened


def _due_slots(
    db: DbSession,
    schedule: Schedule,
    now: datetime,
    phrases: dict[str, Phrase],
    notifier: Notifier | None,
) -> list[Session]:
    opened: list[Session] = []
    for scheduled_for in _candidates(schedule, now):
        if _occurrence(db, schedule.id, scheduled_for) is not None:
            continue
        if scheduled_for > now:
            continue
        elder_id = _elder_id(db, schedule)
        if not calls_allowed(db, elder_id):
            db.add(
                DoseOccurrence(
                    schedule_id=_required(schedule.id),
                    scheduled_for=scheduled_for.isoformat(),
                    outcome="consent_withdrawn",
                    session_id=None,
                )
            )
            continue
        late = now - scheduled_for
        if late <= CATCH_UP:
            call = _open_reminder(db, schedule, phrases, prior_snoozes=0, now=now)
            db.add(
                DoseOccurrence(
                    schedule_id=_required(schedule.id),
                    scheduled_for=scheduled_for.isoformat(),
                    outcome="fired",
                    session_id=call.id,
                )
            )
            opened.append(call)
        else:
            db.add(
                Event(
                    elder_id=elder_id,
                    session_id=None,
                    event_type=EventType.missed_by_system,
                    payload_json="{}",
                )
            )
            _notify_caregiver(db, elder_id, _missed_text(db, schedule, phrases), notifier, None)
            db.add(
                DoseOccurrence(
                    schedule_id=_required(schedule.id),
                    scheduled_for=scheduled_for.isoformat(),
                    outcome="missed_by_system",
                    session_id=None,
                )
            )
    return opened


def _due_snoozes(
    db: DbSession,
    now: datetime,
    phrases: dict[str, Phrase],
    notifier: Notifier | None,
) -> list[Session]:
    opened: list[Session] = []
    reminders = db.exec(select(SnoozeReminder).where(SnoozeReminder.done == False)).all()  # noqa: E712
    for reminder in reminders:
        due_at = datetime.fromisoformat(reminder.due_at)
        if due_at > now:
            continue
        if not calls_allowed(db, reminder.elder_id):
            reminder.done = True
            db.add(reminder)
            continue
        if now - due_at <= CATCH_UP:
            schedule = db.get(Schedule, reminder.schedule_id)
            if schedule is None:
                continue
            call = _open_reminder(
                db,
                schedule,
                phrases,
                prior_snoozes=reminder.prior_snoozes,
                now=now,
            )
            opened.append(call)
        else:
            db.add(
                Event(
                    elder_id=reminder.elder_id,
                    session_id=None,
                    event_type=EventType.missed_by_system,
                    payload_json="{}",
                )
            )
            schedule = db.get(Schedule, reminder.schedule_id)
            text = _missed_text(db, schedule, phrases) if schedule is not None else ""
            _notify_caregiver(db, reminder.elder_id, text, notifier, None)
        reminder.done = True
        db.add(reminder)
    return opened


def _candidates(schedule: Schedule, now: datetime) -> list[datetime]:
    assert schedule.id is not None
    days = set(decode_days(schedule.days))
    times = decode_times(schedule.times_of_day)
    found: list[datetime] = []
    for delta in range(2):
        day = (now - timedelta(days=delta)).date()
        if schedule.start_date > day:
            continue
        if schedule.end_date is not None and schedule.end_date < day:
            continue
        weekday = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[day.weekday()]
        if weekday not in days:
            continue
        for clock in times:
            hour, minute = (int(part) for part in clock.split(":"))
            moment = datetime(
                day.year,
                day.month,
                day.day,
                hour,
                minute,
                tzinfo=now.tzinfo,
            )
            found.append(moment)
    return found


def _occurrence(db: DbSession, schedule_id: int | None, when: datetime) -> DoseOccurrence | None:
    if schedule_id is None:
        return None
    stamp = when.isoformat()
    return db.exec(
        select(DoseOccurrence).where(
            DoseOccurrence.schedule_id == schedule_id,
            DoseOccurrence.scheduled_for == stamp,
        )
    ).first()


def _elder_id(db: DbSession, schedule: Schedule) -> int:
    medication = db.get(Medication, schedule.medication_id)
    if medication is None:
        raise ValueError("schedule is missing its medication")
    return medication.elder_id


def _open_reminder(
    db: DbSession,
    schedule: Schedule,
    phrases: dict[str, Phrase],
    *,
    prior_snoozes: int,
    now: datetime,
) -> Session:
    medication = db.get(Medication, schedule.medication_id)
    if medication is None or schedule.id is None:
        raise ValueError("schedule is missing its medication")
    elder = db.get(Elder, medication.elder_id)
    if elder is None:
        raise ValueError("medication is missing its elder")
    dialog = DialogSession(
        "medication_reminder",
        phrases,
        prior_snoozes=prior_snoozes,
        persona=Persona(
            honorific=elder.honorific,
            spoken_label=medication.spoken_label,
            instructions=medication.instructions,
        ),
    )
    beat = dialog.start()
    call = Session(
        elder_id=elder.id if elder.id is not None else 0,
        schedule_id=schedule.id,
        kind=SessionKind.reminder,
        state=beat.states[-1],
        prior_snoozes=prior_snoozes,
        dialog_state_json=dialog.export_state(),
        transcript="\n".join(beat.spoken),
        started_at=now,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    assert call.id is not None
    for event_type in beat.events:
        db.add(
            Event(
                elder_id=elder.id if elder.id is not None else 0,
                session_id=call.id,
                event_type=EventType(event_type),
                payload_json="{}",
            )
        )
    db.commit()
    return call


def queue_snooze(db: DbSession, call: Session, now: datetime, minutes: int) -> None:
    if call.schedule_id is None:
        return
    db.add(
        SnoozeReminder(
            elder_id=call.elder_id,
            schedule_id=call.schedule_id,
            due_at=(now + timedelta(minutes=minutes)).isoformat(),
            prior_snoozes=call.prior_snoozes + 1,
        )
    )
    db.commit()


def _required(value: int | None) -> int:
    if value is None:
        raise ValueError("missing id")
    return value


def _missed_text(db: DbSession, schedule: Schedule, phrases: dict[str, Phrase]) -> str:
    medication = db.get(Medication, schedule.medication_id)
    elder = db.get(Elder, medication.elder_id) if medication is not None else None
    values = {
        "honorific": elder.honorific if elder is not None else "",
        "spoken_label": medication.spoken_label if medication is not None else "",
        "instructions": "",
        "elder_words": "",
        "snippet": "",
    }
    return render(phrases["notify.missed"].text, values)


def _notify_caregiver(
    db: DbSession,
    elder_id: int,
    message: str,
    notifier: Notifier | None,
    session_id: int | None,
) -> None:
    if notifier is None or not message:
        return
    contact = _caregiver_contact(db, elder_id)
    if contact is None:
        return

    def log(event: Event) -> None:
        db.add(event)

    send_logged(
        notifier,
        contact,
        message,
        elder_id=elder_id,
        session_id=session_id,
        log=log,
    )


def _caregiver_contact(db: DbSession, elder_id: int) -> Contact | None:
    elder = db.get(Elder, elder_id)
    if elder is None:
        return None
    caregiver = db.get(Caregiver, elder.caregiver_id)
    if caregiver is None or not caregiver.channel_address:
        return None
    return Contact(
        elder_id=elder_id,
        name=caregiver.login,
        relationship=caregiver.relationship,
        channel=caregiver.notification_channel,
        channel_address=caregiver.channel_address,
        emergency=False,
    )
