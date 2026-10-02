from pathlib import Path

from fastapi.testclient import TestClient

from saathi.api.app import create_app
from saathi.api.auth import hash_password, issue_token
from saathi.channels.phone import ScriptedLeg, play_checkin_opening
from saathi.db import db_session, init_db, make_engine
from saathi.dialog.graph import DialogSession
from saathi.models import (
    Caregiver,
    Consent,
    ConsentMethod,
    ConsentPurpose,
    ConsentSubject,
    Contact,
    Elder,
    NotificationChannel,
)
from saathi.notify.base import Notifier
from saathi.phrases import load_phrases
from saathi.speech.wav import silence_wav


class _Quiet:
    def send(self, contact: Contact, message: str) -> bool:
        del contact, message
        return True


def test_family_clip_plays_after_the_checkin_greeting(tmp_path: Path) -> None:
    phrases = load_phrases()
    spoken = DialogSession("daily_checkin", phrases).start().spoken
    clip = silence_wav("परिवार")
    leg = ScriptedLeg(speech=[], digits=[])
    play_checkin_opening(leg, spoken, clip)
    assert leg.said[0] == spoken[0]
    assert leg.said[1] == "[family]"
    assert leg.played == [clip]
    assert leg.said[2:] == spoken[1:]

    engine = make_engine(f"sqlite:///{tmp_path / 'saathi.db'}")
    init_db(engine)
    with db_session(engine) as db:
        caregiver = Caregiver(
            login="anita.example@example.com",
            relationship="beti",
            notification_channel=NotificationChannel.email,
            password_hash=hash_password("secret"),
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
            Consent(
                elder_id=elder_id,
                subject=ConsentSubject.caregiver,
                subject_name="Anita",
                purpose=ConsentPurpose.checkins,
                method=ConsentMethod.dashboard_checkbox,
                granted=True,
            )
        )
        db.commit()
        token = issue_token(caregiver.id, "test-secret")
    notifier: Notifier = _Quiet()
    client = TestClient(
        create_app(engine, notifier, secret="test-secret", family_dir=tmp_path / "family")
    )
    headers = {"Authorization": f"Bearer {token}"}
    stored = client.post(
        f"/elders/{elder_id}/family-message",
        headers={**headers, "content-type": "audio/wav"},
        content=clip,
    )
    assert stored.status_code == 200
    opened = client.post(f"/elders/{elder_id}/simulate/checkin", headers=headers)
    assert opened.status_code == 200
    parts = opened.json()["playback"]
    assert parts[0]["text"] == "नमस्ते बाबूजी।"
    assert parts[1]["kind"] == "family"
    assert parts[2]["kind"] == "speech"
