"""Send a message and log the result. Emergency sends retry, then move on."""

from collections.abc import Callable
from datetime import timedelta

from saathi.models import Contact, Event, EventType
from saathi.notify.base import Notifier

LogEvent = Callable[[Event], None]
Sleep = Callable[[float], None]


def send_logged(
    notifier: Notifier,
    contact: Contact,
    message: str,
    *,
    elder_id: int,
    session_id: int | None,
    log: LogEvent,
) -> bool:
    success = False
    try:
        success = notifier.send(contact, message)
    except Exception:
        success = False
    log(
        Event(
            elder_id=elder_id,
            session_id=session_id,
            event_type=EventType.notification_sent,
            payload_json=('{"success": true}' if success else '{"success": false}'),
        )
    )
    return success


def notify_emergency(
    contacts: list[Contact],
    message: str,
    notifier: Notifier,
    *,
    elder_id: int,
    session_id: int | None,
    log: LogEvent,
    sleep: Sleep,
    attempts: int = 5,
    retry_seconds: float = 30,
) -> bool:
    """Retry each emergency contact, then try the next. Sleep is a test clock hook."""
    for contact in contacts:
        if not contact.emergency:
            continue
        for attempt in range(attempts):
            if send_logged(
                notifier,
                contact,
                message,
                elder_id=elder_id,
                session_id=session_id,
                log=log,
            ):
                return True
            if attempt < attempts - 1:
                sleep(retry_seconds)
    return False


def retry_gap() -> timedelta:
    return timedelta(seconds=30)
