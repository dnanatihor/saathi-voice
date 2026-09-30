"""Development providers. They read synthetic audio bytes, not a cloud API."""

from collections.abc import AsyncIterator

from saathi.speech.base import Transcript


async def _read_audio(audio: AsyncIterator[bytes]) -> str:
    chunks: list[bytes] = []
    async for chunk in audio:
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8")


class IdentitySTT:
    """Returns the synthetic clip unchanged."""

    name = "identity"

    async def transcribe_stream(
        self, audio: AsyncIterator[bytes], lang: str
    ) -> AsyncIterator[Transcript]:
        del lang
        yield Transcript(text=await _read_audio(audio))


class SubstitutionSTT:
    """Replaces the first word so the harness can compute a non-zero error rate."""

    name = "substitution"

    async def transcribe_stream(
        self, audio: AsyncIterator[bytes], lang: str
    ) -> AsyncIterator[Transcript]:
        del lang
        words = (await _read_audio(audio)).split()
        if words:
            words[0] = "सुना"
        yield Transcript(text=" ".join(words))


class DropLastSTT:
    """Drops the last two words of the synthetic clip."""

    name = "drop-last"

    async def transcribe_stream(
        self, audio: AsyncIterator[bytes], lang: str
    ) -> AsyncIterator[Transcript]:
        del lang
        words = (await _read_audio(audio)).split()
        kept = words[:-2] if len(words) >= 2 else []
        yield Transcript(text=" ".join(kept))


class SilentTTS:
    async def synthesize_stream(self, text: str, lang: str, rate: float) -> AsyncIterator[bytes]:
        del lang, rate
        yield text.encode("utf-8")
