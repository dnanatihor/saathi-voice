"""SQLite engine via SQLModel. Postgres can replace the URL later."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine


def make_engine(url: str = "sqlite:///saathi.db") -> Engine:
    connect_args: dict[str, bool] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, connect_args=connect_args)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor: Any = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def db_session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session
