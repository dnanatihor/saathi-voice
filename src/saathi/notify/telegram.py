"""Telegram bot adapter. The chat id is linked with a one-time code."""

from collections.abc import Callable
from json import dumps
from urllib.request import Request, urlopen

from saathi.models import Contact, NotificationChannel

Payload = dict[str, str]
Transport = Callable[[str, Payload], int]


def urllib_transport(url: str, payload: Payload) -> int:
    body = dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:  # noqa: S310
        status = getattr(response, "status", None)
        return int(status) if isinstance(status, int) else response.getcode()


class TelegramNotifier:
    def __init__(self, token: str, transport: Transport | None = None) -> None:
        self._token = token
        self._transport = transport if transport is not None else urllib_transport

    def send(self, contact: Contact, message: str) -> bool:
        if contact.channel != NotificationChannel.telegram:
            return False
        if not contact.channel_address:
            return False
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        code = self._transport(url, {"chat_id": contact.channel_address, "text": message})
        return code == 200
