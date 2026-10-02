"""Local server entry: `uv run uvicorn saathi.api.asgi:app --port 8000`."""

import os

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from saathi.api.app import create_app
from saathi.db import init_db, make_engine
from saathi.models import Contact
from saathi.notify.base import Notifier
from saathi.paths import REPO_ROOT
from saathi.speech.providers.sarvam import SarvamTTS


class DevNotifier:
    def send(self, contact: Contact, message: str) -> bool:
        del contact, message
        return True


def load_env_file() -> None:
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key, value)


def build_app() -> FastAPI:
    load_env_file()
    engine = make_engine(os.environ.get("SAATHI_DATABASE_URL", "sqlite:///saathi.db"))
    init_db(engine)
    notifier: Notifier = DevNotifier()
    secret = os.environ.get("SAATHI_SECRET", "dev-secret")
    tts = None
    speech_key = os.environ.get("SAATHI_SPEECH_API_KEY", "")
    if os.environ.get("SAATHI_SPEECH_PROVIDER") == "sarvam" and speech_key:
        tts = SarvamTTS(speech_key)
    application = create_app(engine, notifier, secret=secret, tts=tts)
    dist = REPO_ROOT / "web" / "dist"
    if dist.is_dir():
        application.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
    return application


app = build_app()
