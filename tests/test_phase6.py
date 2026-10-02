from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlmodel import select

from saathi.api.app import create_app
from saathi.api.auth import issue_token
from saathi.db import db_session, init_db, make_engine
from saathi.models import (
    Caregiver,
    Consent,
    ConsentMethod,
    ConsentPurpose,
    ConsentSubject,
    Contact,
    Elder,
    Event,
    EventType,
    Medication,
    NotificationChannel,
    Schedule,
    SessionKind,
    encode_days,
    encode_times,
)
from saathi.models import (
    Session as Call,
)
from saathi.notify.base import Notifier
from saathi.phrases import load_phrases
from saathi.privacy import purge_old_transcripts
from saathi.scheduler import advance, register_tick

MONDAY = datetime(2026, 9, 28, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


class _Quiet:
    def send(self, contact: Contact, message: str) -> bool:
        del contact, message
        return True


def _engine(tmp_path: Path):
    engine = make_engine(f"sqlite:///{tmp_path / 'saathi.db'}")
    init_db(engine)
    return engine


def test_erasure_leaves_no_personal_data(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with db_session(engine) as db:
        caregiver = Caregiver(
            login="anita.example@example.com",
            relationship="beti",
            notification_channel=NotificationChannel.email,
            password_hash="hash",
        )
        db.add(caregiver)
        db.commit()
        db.refresh(caregiver)
        assert caregiver.id is not None
        elder = Elder(caregiver_id=caregiver.id, display_name="श्याम लाल", honorific="बाबूजी")
        db.add(elder)
        db.commit()
        db.refresh(elder)
        assert elder.id is not None
        elder_id = elder.id
        db.add(
            Contact(
                elder_id=elder_id,
                name="रीता",
                relationship="beti",
                channel=NotificationChannel.telegram,
                channel_address="2002",
                emergency=True,
            )
        )
        db.add(
            Call(
                elder_id=elder_id,
                kind=SessionKind.reminder,
                state="AskTaken",
                transcript="हाँ, ले ली",
            )
        )
        db.add(Event(elder_id=elder_id, event_type=EventType.taken, payload_json='{"name":"श्याम"}'))
        db.commit()
        token = issue_token(caregiver.id, "test-secret")
    notifier: Notifier = _Quiet()
    client = TestClient(create_app(engine, notifier, secret="test-secret"))
    response = client.delete(
        f"/elders/{elder_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    with db_session(engine) as db:
        stored = " ".join(
            " ".join(str(value) for value in row.__dict__.values())
            for row in db.exec(select(Event)).all()
        )
        stored += " ".join(item.display_name for item in db.exec(select(Elder)).all())
        stored += " ".join(item.transcript for item in db.exec(select(Call)).all())
        stored += " ".join(item.channel_address for item in db.exec(select(Contact)).all())
        assert "श्याम" not in stored
        assert "2002" not in stored
        assert "हाँ" not in stored
        events = db.exec(select(Event)).all()
        assert [item.event_type for item in events] == [EventType.erasure]
        assert events[0].payload_json == "{}"
        assert events[0].elder_id is None


def test_retention_deletes_old_transcripts_and_keeps_events(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with db_session(engine) as db:
        caregiver = Caregiver(
            login="anita.example@example.com",
            relationship="beti",
            notification_channel=NotificationChannel.email,
        )
        db.add(caregiver)
        db.commit()
        db.refresh(caregiver)
        assert caregiver.id is not None
        elder = Elder(caregiver_id=caregiver.id, display_name="श्याम लाल", honorific="बाबूजी")
        db.add(elder)
        db.commit()
        db.refresh(elder)
        assert elder.id is not None
        db.add(
            Call(
                elder_id=elder.id,
                kind=SessionKind.reminder,
                state="Close",
                transcript="पुरानी बात",
                dialog_state_json='{"user_text":"पुरानी बात"}',
                started_at=datetime.now(UTC) - timedelta(days=31),
            )
        )
        db.add(Event(elder_id=elder.id, event_type=EventType.taken, payload_json="{}"))
        db.commit()
        cleared = purge_old_transcripts(db, now=datetime.now(UTC), retention_days=30)
        assert cleared == 1
        call = db.exec(select(Call)).one()
        assert call.transcript == ""
        assert call.dialog_state_json == ""
        assert db.exec(select(Event)).one().event_type == EventType.taken


def test_a_schedule_without_consent_does_not_call(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with db_session(engine) as db:
        caregiver = Caregiver(
            login="anita.example@example.com",
            relationship="beti",
            notification_channel=NotificationChannel.telegram,
        )
        db.add(caregiver)
        db.commit()
        db.refresh(caregiver)
        assert caregiver.id is not None
        elder = Elder(caregiver_id=caregiver.id, display_name="श्याम लाल", honorific="बाबूजी")
        db.add(elder)
        db.commit()
        db.refresh(elder)
        assert elder.id is not None
        medication = Medication(
            elder_id=elder.id,
            name="नीली दवा",
            spoken_label="बीपी की दवा",
            instructions="खाने के बाद",
        )
        db.add(medication)
        db.commit()
        db.refresh(medication)
        assert medication.id is not None
        db.add(
            Schedule(
                medication_id=medication.id,
                times_of_day=encode_times(["09:00"]),
                days=encode_days(["mon"]),
                start_date=date(2026, 9, 1),
            )
        )
        db.commit()
        opened = advance(db, MONDAY, load_phrases(), notifier=_Quiet())
        assert opened == []


def test_withdrawn_consent_skips_the_scheduled_call(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with db_session(engine) as db:
        caregiver = Caregiver(
            login="anita.example@example.com",
            relationship="beti",
            notification_channel=NotificationChannel.telegram,
            channel_address="1001",
        )
        db.add(caregiver)
        db.commit()
        db.refresh(caregiver)
        assert caregiver.id is not None
        elder = Elder(caregiver_id=caregiver.id, display_name="श्याम लाल", honorific="बाबूजी")
        db.add(elder)
        db.commit()
        db.refresh(elder)
        assert elder.id is not None
        medication = Medication(
            elder_id=elder.id,
            name="नीली दवा",
            spoken_label="बीपी की दवा",
            instructions="खाने के बाद",
        )
        db.add(medication)
        db.commit()
        db.refresh(medication)
        assert medication.id is not None
        db.add(
            Schedule(
                medication_id=medication.id,
                times_of_day=encode_times(["09:00"]),
                days=encode_days(["mon"]),
                start_date=date(2026, 9, 1),
            )
        )
        db.add(
            Consent(
                elder_id=elder.id,
                subject=ConsentSubject.elder,
                subject_name="श्याम लाल",
                purpose=ConsentPurpose.reminders,
                method=ConsentMethod.dashboard_checkbox,
                granted=True,
            )
        )
        db.add(
            Consent(
                elder_id=elder.id,
                subject=ConsentSubject.elder,
                subject_name="श्याम लाल",
                purpose=ConsentPurpose.reminders,
                method=ConsentMethod.dashboard_checkbox,
                granted=False,
            )
        )
        db.commit()
        opened = advance(db, MONDAY, load_phrases(), notifier=_Quiet())
        assert opened == []
        assert db.exec(select(Call)).all() == []
    scheduler = register_tick(f"sqlite:///{tmp_path / 'jobs.db'}", "Asia/Kolkata")
    assert scheduler.get_job("saathi-retention") is not None
