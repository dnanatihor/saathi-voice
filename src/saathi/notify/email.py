"""SMTP email adapter. The host and credentials come from the environment."""

from collections.abc import Callable

from saathi.models import Contact, NotificationChannel

Sender = Callable[[str, str, str], None]


class EmailNotifier:
    def __init__(self, sender: Sender) -> None:
        self._sender = sender

    def send(self, contact: Contact, message: str) -> bool:
        if contact.channel != NotificationChannel.email:
            return False
        if not contact.channel_address:
            return False
        self._sender(contact.channel_address, "Saathi", message)
        return True
