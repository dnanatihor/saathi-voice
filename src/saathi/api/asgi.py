"""Local server entry: `uv run uvicorn saathi.api.asgi:app --port 8000`."""

import os

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from saathi.api.app import create_app
from saathi.db import init_db, make_engine
from saathi.models import Contact
from saathi.notify.base import Notifier
from saathi.paths import REPO_ROOT


class DevNotifier:
    def send(self, contact: Contact, message: str) -> bool:
        del contact, message
        return True


def build_app() -> FastAPI:
    engine = make_engine(os.environ.get("SAATHI_DATABASE_URL", "sqlite:///saathi.db"))
    init_db(engine)
    notifier: Notifier = DevNotifier()
    secret = os.environ.get("SAATHI_SECRET", "dev-secret")
    application = create_app(engine, notifier, secret=secret)
    dist = REPO_ROOT / "web" / "dist"
    if dist.is_dir():
        application.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
    return application


app = build_app()
