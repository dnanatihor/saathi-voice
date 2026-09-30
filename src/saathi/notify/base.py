"""Notifier.send(contact, message) from SPEC.md §6."""

from typing import Protocol, runtime_checkable

from saathi.models import Contact


@runtime_checkable
class Notifier(Protocol):
    def send(self, contact: Contact, message: str) -> bool: ...
