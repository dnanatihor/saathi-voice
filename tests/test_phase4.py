import json

from fastapi.testclient import TestClient

from saathi.api.app import create_app
from saathi.db import init_db, make_engine
from saathi.models import Contact
from saathi.notify.base import Notifier


class _Quiet:
    def send(self, contact: Contact, message: str) -> bool:
        del contact, message
        return True


def _app() -> TestClient:
    engine = make_engine("sqlite://")
    init_db(engine)
    notifier: Notifier = _Quiet()
    return TestClient(create_app(engine, notifier, secret="test-secret"))


def test_voice_reminder_finishes_under_the_latency_budget() -> None:
    latencies: list[float] = []
    for _ in range(5):
        with _app().websocket_connect("/voice") as socket:
            opening = socket.receive_json()
            assert "क्या आपने बीपी की दवा ले ली?" in opening["spoken"]
            assert opening["audio_b64"]
            socket.send_bytes("हाँ, ले ली".encode())
            socket.send_text(json.dumps({"type": "end"}))
            reply = socket.receive_json()
            latencies.append(float(reply["latency_s"]))
            assert "बहुत अच्छा बाबूजी। धन्यवाद।" in reply["spoken"]
            assert "ठीक है बाबूजी। अपना ख्याल रखिए।" in reply["spoken"]
            assert "Close" in reply["states"]
    assert sorted(latencies)[len(latencies) // 2] <= 2.0
    assert max(latencies) <= 3.5
