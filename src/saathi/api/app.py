"""Caregiver routes: profiles, adherence, and a text simulate-call."""

import base64
import json
from collections.abc import AsyncIterator, Generator
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlmodel import Session, select

from saathi.adherence import checkin_summaries, week_grid
from saathi.api.auth import (
    caregiver_id_from_token,
    find_caregiver,
    hash_password,
    issue_link_code,
    issue_token,
    redeem_link_code,
    verify_password,
)
from saathi.channels.voice import VoiceCall
from saathi.flow import apply_user_text, open_checkin
from saathi.models import (
    Caregiver,
    Consent,
    ConsentMethod,
    ConsentPurpose,
    ConsentSubject,
    Contact,
    Elder,
    Event,
    Medication,
    NotificationChannel,
    Schedule,
    encode_days,
    encode_times,
)
from saathi.models import (
    Session as Call,
)
from saathi.notify.base import Notifier
from saathi.phrases import Phrase, load_phrases
from saathi.privacy import erase_elder
from saathi.scheduler import advance


class RegisterBody(BaseModel):
    login: str
    password: str
    relationship: str
    notification_channel: NotificationChannel


class LoginBody(BaseModel):
    login: str
    password: str


class ElderBody(BaseModel):
    display_name: str
    honorific: str
    call_window_start: str = "08:00"
    call_window_end: str = "20:00"


class MedicationBody(BaseModel):
    name: str
    spoken_label: str
    instructions: str


class ScheduleBody(BaseModel):
    times_of_day: list[str]
    days: list[str]
    start_date: date
    end_date: date | None = None


class ContactBody(BaseModel):
    name: str
    relationship: str
    channel: NotificationChannel
    channel_address: str
    emergency: bool


class ConsentBody(BaseModel):
    subject: ConsentSubject
    subject_name: str
    purpose: ConsentPurpose
    method: ConsentMethod
    transcript: str | None = None
    granted: bool = True


class TurnBody(BaseModel):
    text: str


class LinkBody(BaseModel):
    code: str
    chat_id: str


def create_app(
    engine: Engine,
    notifier: Notifier,
    *,
    secret: str,
    phrases: dict[str, Phrase] | None = None,
    timezone: str = "Asia/Kolkata",
) -> FastAPI:
    app = FastAPI(title="Saathi Voice")
    app.state.engine = engine
    app.state.notifier = notifier
    app.state.secret = secret
    app.state.phrases = phrases if phrases is not None else load_phrases()
    app.state.timezone = timezone

    def db_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def current_caregiver(
        session: Annotated[Session, Depends(db_session)],
        authorization: Annotated[str | None, Header()] = None,
    ) -> Caregiver:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="login required")
        caregiver_id = caregiver_id_from_token(authorization.removeprefix("Bearer "), secret)
        if caregiver_id is None:
            raise HTTPException(status_code=401, detail="login required")
        caregiver = session.get(Caregiver, caregiver_id)
        if caregiver is None:
            raise HTTPException(status_code=401, detail="login required")
        return caregiver

    def owned_elder(
        elder_id: int,
        session: Annotated[Session, Depends(db_session)],
        caregiver: Annotated[Caregiver, Depends(current_caregiver)],
    ) -> Elder:
        elder = session.get(Elder, elder_id)
        if elder is None or elder.caregiver_id != caregiver.id:
            raise HTTPException(status_code=404, detail="elder not found")
        return elder

    @app.post("/auth/register")
    def register(
        body: RegisterBody, session: Annotated[Session, Depends(db_session)]
    ) -> dict[str, str]:
        if find_caregiver(session, body.login) is not None:
            raise HTTPException(status_code=409, detail="login already exists")
        caregiver = Caregiver(
            login=body.login,
            relationship=body.relationship,
            notification_channel=body.notification_channel,
            password_hash=hash_password(body.password),
        )
        session.add(caregiver)
        session.commit()
        session.refresh(caregiver)
        assert caregiver.id is not None
        return {"token": issue_token(caregiver.id, secret)}

    @app.post("/auth/login")
    def login(body: LoginBody, session: Annotated[Session, Depends(db_session)]) -> dict[str, str]:
        caregiver = find_caregiver(session, body.login)
        if (
            caregiver is None
            or caregiver.id is None
            or not verify_password(body.password, caregiver.password_hash)
        ):
            raise HTTPException(status_code=401, detail="login required")
        return {"token": issue_token(caregiver.id, secret)}

    @app.post("/auth/link-code")
    def link_code(
        session: Annotated[Session, Depends(db_session)],
        caregiver: Annotated[Caregiver, Depends(current_caregiver)],
    ) -> dict[str, str]:
        assert caregiver.id is not None
        return {"code": issue_link_code(session, caregiver.id)}

    @app.post("/auth/link-code/redeem")
    def redeem(body: LinkBody, session: Annotated[Session, Depends(db_session)]) -> dict[str, str]:
        caregiver = redeem_link_code(session, body.code, body.chat_id)
        if caregiver is None:
            raise HTTPException(status_code=404, detail="code not found")
        return {"channel_address": caregiver.channel_address}

    @app.post("/elders")
    def create_elder(
        body: ElderBody,
        session: Annotated[Session, Depends(db_session)],
        caregiver: Annotated[Caregiver, Depends(current_caregiver)],
    ) -> dict[str, int | None]:
        assert caregiver.id is not None
        elder = Elder(
            caregiver_id=caregiver.id,
            display_name=body.display_name,
            honorific=body.honorific,
            call_window_start=body.call_window_start,
            call_window_end=body.call_window_end,
            timezone=timezone,
        )
        session.add(elder)
        session.commit()
        session.refresh(elder)
        return {"id": elder.id}

    @app.get("/elders")
    def list_elders(
        session: Annotated[Session, Depends(db_session)],
        caregiver: Annotated[Caregiver, Depends(current_caregiver)],
    ) -> list[dict[str, str | int | None]]:
        rows = session.exec(select(Elder).where(Elder.caregiver_id == caregiver.id)).all()
        return [
            {"id": row.id, "display_name": row.display_name, "honorific": row.honorific}
            for row in rows
        ]

    @app.post("/elders/{elder_id}/medications")
    def add_medication(
        body: MedicationBody,
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
    ) -> dict[str, int | None]:
        assert elder.id is not None
        medication = Medication(
            elder_id=elder.id,
            name=body.name,
            spoken_label=body.spoken_label,
            instructions=body.instructions,
        )
        session.add(medication)
        session.commit()
        session.refresh(medication)
        return {"id": medication.id}

    @app.post("/medications/{medication_id}/schedules")
    def add_schedule(
        medication_id: int,
        body: ScheduleBody,
        session: Annotated[Session, Depends(db_session)],
        caregiver: Annotated[Caregiver, Depends(current_caregiver)],
    ) -> dict[str, int | None]:
        medication = session.get(Medication, medication_id)
        elder = session.get(Elder, medication.elder_id) if medication is not None else None
        if medication is None or elder is None or elder.caregiver_id != caregiver.id:
            raise HTTPException(status_code=404, detail="medication not found")
        schedule = Schedule(
            medication_id=medication_id,
            times_of_day=encode_times(body.times_of_day),
            days=encode_days(body.days),
            start_date=body.start_date,
            end_date=body.end_date,
        )
        session.add(schedule)
        session.commit()
        session.refresh(schedule)
        return {"id": schedule.id}

    @app.post("/elders/{elder_id}/contacts")
    def add_contact(
        body: ContactBody,
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
    ) -> dict[str, int | None]:
        assert elder.id is not None
        contact = Contact(elder_id=elder.id, **body.model_dump())
        session.add(contact)
        session.commit()
        session.refresh(contact)
        return {"id": contact.id}

    @app.post("/elders/{elder_id}/consents")
    def add_consent(
        body: ConsentBody,
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
    ) -> dict[str, int | None]:
        assert elder.id is not None
        consent = Consent(elder_id=elder.id, **body.model_dump())
        session.add(consent)
        session.commit()
        session.refresh(consent)
        return {"id": consent.id}

    @app.delete("/elders/{elder_id}")
    def erase(
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
    ) -> dict[str, bool]:
        assert elder.id is not None
        erase_elder(session, elder.id)
        return {"erased": True}

    @app.get("/elders/{elder_id}/adherence")
    def adherence(
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
        week: date,
    ) -> list[dict[str, str]]:
        assert elder.id is not None
        return week_grid(session, elder.id, week)

    @app.get("/elders/{elder_id}/events")
    def events(
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
    ) -> list[dict[str, str]]:
        rows = session.exec(select(Event).where(Event.elder_id == elder.id)).all()
        return [
            {
                "type": row.event_type.value,
                "payload": row.payload_json,
                "at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    @app.get("/elders/{elder_id}/checkins")
    def checkins(
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
    ) -> list[dict[str, str]]:
        assert elder.id is not None
        return checkin_summaries(session, elder.id)

    @app.post("/elders/{elder_id}/export")
    def export_elder(
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
    ) -> dict[str, object]:
        assert elder.id is not None
        return {
            "elder": {"display_name": elder.display_name, "honorific": elder.honorific},
            "events": [
                row.event_type.value
                for row in session.exec(select(Event).where(Event.elder_id == elder.id)).all()
            ],
            "checkins": checkin_summaries(session, elder.id),
        }

    @app.post("/elders/{elder_id}/simulate/checkin")
    def simulate_checkin(
        elder: Annotated[Elder, Depends(owned_elder)],
        session: Annotated[Session, Depends(db_session)],
    ) -> dict[str, int | None]:
        call = open_checkin(session, elder, app.state.phrases)
        return {"session_id": call.id}

    @app.post("/sessions/{session_id}/turns")
    def turn(
        session_id: int,
        body: TurnBody,
        session: Annotated[Session, Depends(db_session)],
        caregiver: Annotated[Caregiver, Depends(current_caregiver)],
    ) -> dict[str, list[str]]:
        call = session.get(Call, session_id)
        elder = session.get(Elder, call.elder_id) if call is not None else None
        if call is None or elder is None or elder.caregiver_id != caregiver.id:
            raise HTTPException(status_code=404, detail="session not found")
        beat = apply_user_text(
            session,
            call,
            body.text,
            app.state.phrases,
            app.state.notifier,
            datetime.now(ZoneInfo(timezone)),
        )
        return {"spoken": beat.spoken, "states": beat.states}

    @app.post("/clock")
    def clock(
        session: Annotated[Session, Depends(db_session)],
        caregiver: Annotated[Caregiver, Depends(current_caregiver)],
        at: datetime,
    ) -> dict[str, int]:
        del caregiver
        opened = advance(session, at, app.state.phrases, notifier=app.state.notifier)
        return {"opened": len(opened)}

    @app.websocket("/voice")
    async def voice(socket: WebSocket) -> None:
        await socket.accept()
        call = VoiceCall(app.state.phrases)
        opening, audio = await call.opening()
        await socket.send_json(_voice_payload(opening, audio, latency_s=None))
        try:
            while True:
                chunks = await _audio_until_end(socket)
                heard, beat, reply, latency = await call.hear(_chunks(chunks))
                del heard
                await socket.send_json(_voice_payload(beat, reply, latency_s=latency))
                if "Close" in beat.states:
                    break
        except WebSocketDisconnect:
            return

    return app


def _voice_payload(beat: object, audio: bytes, *, latency_s: float | None) -> dict[str, object]:
    from saathi.dialog.graph import Beat

    if not isinstance(beat, Beat):
        raise TypeError("beat required")
    payload: dict[str, object] = {
        "type": "reply",
        "spoken": beat.spoken,
        "states": beat.states,
        "audio_b64": base64.b64encode(audio).decode("ascii"),
    }
    if latency_s is not None:
        payload["latency_s"] = latency_s
    return payload


async def _audio_until_end(socket: WebSocket) -> list[bytes]:
    chunks: list[bytes] = []
    while True:
        message = await socket.receive()
        if message.get("type") == "websocket.disconnect":
            raise WebSocketDisconnect
        raw = message.get("bytes")
        if isinstance(raw, bytes) and raw:
            chunks.append(raw)
        text = message.get("text")
        if isinstance(text, str) and text:
            loaded = json.loads(text)
            if isinstance(loaded, dict) and loaded.get("type") == "end":
                return chunks


async def _chunks(chunks: list[bytes]) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk
