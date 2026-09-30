"""SQLite round-trip for the domain models. Personas are fictional."""

from datetime import date
from pathlib import Path

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
    Session,
    SessionKind,
    decode_days,
    decode_times,
    encode_days,
    encode_times,
)


def test_fictional_household_round_trip(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'saathi.db'}")
    init_db(engine)

    with db_session(engine) as session:
        caregiver = Caregiver(
            login="anita.example@example.com",
            relationship="beti",
            notification_channel=NotificationChannel.telegram,
        )
        session.add(caregiver)
        session.commit()
        session.refresh(caregiver)
        assert caregiver.id is not None

        elder = Elder(
            caregiver_id=caregiver.id,
            display_name="श्याम लाल",
            honorific="बाबूजी",
        )
        session.add(elder)
        session.commit()
        session.refresh(elder)
        assert elder.id is not None
        assert elder.language == "hi"
        assert elder.preferred_speech_rate == 0.85
        assert elder.timezone == "Asia/Kolkata"

        contact = Contact(
            elder_id=elder.id,
            name="रीता",
            relationship="beti",
            channel=NotificationChannel.email,
            channel_address="rita.example@example.com",
            emergency=True,
        )
        medication = Medication(
            elder_id=elder.id,
            name="नीली गोली",
            spoken_label="बीपी की दवा",
            instructions="खाने के बाद",
        )
        session.add(contact)
        session.add(medication)
        session.commit()
        session.refresh(medication)
        assert medication.id is not None

        schedule = Schedule(
            medication_id=medication.id,
            times_of_day=encode_times(["08:00", "20:00"]),
            days=encode_days(["mon", "wed", "fri"]),
            start_date=date(2026, 1, 1),
        )
        consent = Consent(
            elder_id=elder.id,
            subject=ConsentSubject.elder,
            subject_name="श्याम लाल",
            purpose=ConsentPurpose.reminders,
            method=ConsentMethod.verbal,
            transcript="हाँ",
        )
        session.add(schedule)
        session.add(consent)
        session.commit()
        session.refresh(schedule)
        assert schedule.id is not None

        call = Session(
            elder_id=elder.id,
            schedule_id=schedule.id,
            kind=SessionKind.reminder,
            state="Greet",
        )
        session.add(call)
        session.commit()
        session.refresh(call)
        assert call.id is not None

        event = Event(
            elder_id=elder.id,
            session_id=call.id,
            event_type=EventType.reminder_sent,
            payload_json="{}",
        )
        session.add(event)
        session.commit()
        elder_id = elder.id
        schedule_id = schedule.id
        consent_id = consent.id

    with db_session(engine) as session:
        stored = session.get(Elder, elder_id)
        assert stored is not None
        assert stored.honorific == "बाबूजी"
        stored_schedule = session.get(Schedule, schedule_id)
        assert stored_schedule is not None
        assert decode_times(stored_schedule.times_of_day) == ["08:00", "20:00"]
        assert decode_days(stored_schedule.days) == ["mon", "wed", "fri"]
        stored_consent = session.get(Consent, consent_id)
        assert stored_consent is not None
        assert stored_consent.transcript == "हाँ"
