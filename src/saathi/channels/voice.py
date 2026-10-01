"""Browser voice turn: end of speech, then the first audio of the reply."""

from collections.abc import AsyncIterator
from time import perf_counter

from saathi.dialog.graph import Beat, DialogSession, Persona
from saathi.phrases import Phrase
from saathi.speech.base import STTProvider, TTSProvider
from saathi.speech.providers.dev import IdentitySTT, SilentTTS
from saathi.speech.wav import silence_wav


class VoiceCall:
    def __init__(
        self,
        phrases: dict[str, Phrase],
        *,
        persona: Persona | None = None,
        stt: STTProvider | None = None,
        tts: TTSProvider | None = None,
        rate: float = 0.85,
    ) -> None:
        self._session = DialogSession(flow="medication_reminder", phrases=phrases, persona=persona)
        self._stt = stt if stt is not None else IdentitySTT()
        self._tts = tts if tts is not None else SilentTTS()
        self._rate = rate

    async def opening(self) -> tuple[Beat, bytes]:
        beat = self._session.start()
        return beat, await self._audio(beat.spoken)

    async def hear(self, audio: AsyncIterator[bytes]) -> tuple[str, Beat, bytes, float]:
        started = perf_counter()
        parts: list[str] = []
        async for transcript in self._stt.transcribe_stream(audio, "hi"):
            parts.append(transcript.text)
        heard = " ".join(parts).strip()
        beat = self._session.user_turn(heard)
        reply = await self._audio(beat.spoken)
        return heard, beat, reply, perf_counter() - started

    async def _audio(self, lines: list[str]) -> bytes:
        text = " ".join(lines)
        chunks: list[bytes] = []
        async for chunk in self._tts.synthesize_stream(text, "hi", self._rate):
            chunks.append(chunk)
        if not chunks:
            return silence_wav(text)
        audio = b"".join(chunks)
        if audio.startswith(b"RIFF"):
            return audio
        return silence_wav(text)
