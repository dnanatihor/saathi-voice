"""Speech provider interfaces from SPEC.md §7."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Transcript:
    text: str


class STTProvider(Protocol):
    def transcribe_stream(
        self, audio: AsyncIterator[bytes], lang: str
    ) -> AsyncIterator[Transcript]:
        """Partial transcripts from audio. SPEC.md writes this as an async method."""


class TTSProvider(Protocol):
    def synthesize_stream(self, text: str, lang: str, rate: float) -> AsyncIterator[bytes]:
        """Audio chunks for spoken text. SPEC.md writes this as an async method."""
