"""Phase 2: a test clock fires a reminder, and a missed dose notifies Telegram."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlmodel import select

from saathi.adherence import week_grid
from saathi.api.app import create_app
from saathi.db import db_session, init_db, make_engine
from saathi.flow import apply_user_text
from saathi.models import (
    Caregiver,
    Contact,
    Elder,
    Event,
    EventType,
    Medication,
    NotificationChannel,
    Schedule,
    encode_days,
    encode_times,
)
from saathi.notify.dispatch import notify_emergency
from saathi.notify.telegram import TelegramNotifier
from saathi.phrases import load_phrases
from saathi.scheduler import advance, register_tick

ZONE = ZoneInfo("Asia/Kolkata")
MONDAY = datetime(2026, 9, 28, 9, 0, tzinfo=ZONE)


class _Telegram:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, payload: dict[str, str]) -> int:
        self.calls.append((url, payload))
        return self.status


def _household(tmp_path: object) -> tuple[object, int, int]:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    engine = make_engine(f"sqlite:///{tmp_path / 'saathi.db'}")
    init_db(engine)
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
        schedule = Schedule(
            medication_id=medication.id,
            times_of_day=encode_times(["09:00"]),
            days=encode_days(["mon"]),
            start_date=date(2026, 9, 1),
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        assert schedule.id is not None
        contact = Contact(
            elder_id=elder.id,
            name="रीता",
            relationship="beti",
            channel=NotificationChannel.telegram,
            channel_address="2002",
            emergency=True,
        )
        db.add(contact)
        db.commit()
        return engine, elder.id, schedule.id


def test_scheduled_reminder_and_missed_telegram(tmp_path: object) -> None:
    engine, _elder_id, _schedule_id = _household(tmp_path)
    phrases = load_phrases()
    transport = _Telegram()
    notifier = TelegramNotifier("test-token", transport)
    database_url = str(engine.url)
    scheduler = register_tick(database_url, "Asia/Kolkata")
    job = scheduler.get_job("saathi-tick")
    assert job is not None
    assert job.misfire_grace_time == 1800

    with db_session(engine) as db:
        opened = advance(db, MONDAY, phrases, notifier=notifier)
        assert len(opened) == 1
        call = opened[0]
        assert call.state == "AskTaken"
        events = db.exec(select(Event).where(Event.session_id == call.id)).all()
        assert [item.event_type for item in events] == [EventType.reminder_sent]
        apply_user_text(db, call, "अभी नहीं", phrases, notifier, MONDAY)
        later = datetime(2026, 9, 28, 9, 15, tzinfo=ZONE)
        follow = advance(db, later, phrases, notifier=notifier)
        assert len(follow) == 1
        assert follow[0].prior_snoozes == 1
        apply_user_text(db, follow[0], "अभी नहीं ली", phrases, notifier, later)

    assert transport.calls
    assert transport.calls[0][0].startswith("https://api.telegram.org/bottest-token/sendMessage")
    assert transport.calls[0][1]["chat_id"] == "1001"
    assert "बीपी की दवा" in transport.calls[0][1]["text"]
    with db_session(engine) as db:
        sent = db.exec(select(Event).where(Event.event_type == EventType.notification_sent)).all()
        assert sent
        assert '"success": true' in sent[-1].payload_json
        cells = week_grid(db, _elder_id, date(2026, 9, 28))
        assert cells[0]["status"] == "missed"
        assert cells[0]["day"] == "mon"


def test_restart_outside_grace_marks_missed_by_system(tmp_path: object) -> None:
    engine, elder_id, _schedule_id = _household(tmp_path)
    phrases = load_phrases()
    transport = _Telegram()
    notifier = TelegramNotifier("test-token", transport)
    late = datetime(2026, 9, 28, 10, 0, tzinfo=ZONE)
    with db_session(engine) as db:
        opened = advance(db, late, phrases, notifier=notifier)
        assert opened == []
        missed = db.exec(select(Event).where(Event.event_type == EventType.missed_by_system)).all()
        assert len(missed) == 1
        assert week_grid(db, elder_id, date(2026, 9, 28))[0]["status"] == "missed_by_system"
    assert transport.calls


def test_emergency_retries_then_next_contact(tmp_path: object) -> None:
    engine, elder_id, _schedule_id = _household(tmp_path)
    sleeps: list[float] = []
    attempts = {"n": 0}

    class _Flaky:
        def send(self, contact: Contact, message: str) -> bool:
            del message
            attempts["n"] += 1
            return contact.channel_address != "2002"

    with db_session(engine) as db:
        second = Contact(
            elder_id=elder_id,
            name="मोहन",
            relationship="beta",
            channel=NotificationChannel.telegram,
            channel_address="3003",
            emergency=True,
        )
        db.add(second)
        db.commit()
        contacts = db.exec(select(Contact).where(Contact.elder_id == elder_id)).all()
        logged: list[Event] = []
        ok = notify_emergency(
            list(contacts),
            "alert",
            _Flaky(),
            elder_id=elder_id,
            session_id=None,
            log=logged.append,
            sleep=sleeps.append,
        )
    assert ok is True
    assert attempts["n"] == 6
    assert sleeps == [30, 30, 30, 30]


def test_login_and_adherence_route(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    engine, _elder_id, _schedule_id = _household(tmp_path)
    app = create_app(engine, TelegramNotifier("test-token", _Telegram()), secret="test-secret")
    client = TestClient(app)
    registered = client.post(
        "/auth/register",
        json={
            "login": "rita.example@example.com",
            "password": "correct horse",
            "relationship": "beti",
            "notification_channel": "telegram",
        },
    )
    assert registered.status_code == 200
    token = registered.json()["token"]
    denied = client.get("/elders")
    assert denied.status_code == 401
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/elders",
        headers=headers,
        json={"display_name": "दादी", "honorific": "दादी जी"},
    )
    assert created.status_code == 200
    elder_id = created.json()["id"]
    grid = client.get(
        f"/elders/{elder_id}/adherence",
        headers=headers,
        params={"week": "2026-09-28"},
    )
    assert grid.status_code == 200
    assert grid.json() == []
