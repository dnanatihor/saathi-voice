"""Sarvam Hindi speech. Tests inject a transport and do not call the network."""

import base64
import json
from collections.abc import AsyncIterator, Callable
from urllib.request import Request, urlopen

from saathi.speech.base import Transcript

_SPEECH_URL = "https://api.sarvam.ai/text-to-speech"


def _post(api_key: str, text: str, rate: float) -> bytes:
    pace = min(2.0, max(0.5, rate))
    body = json.dumps(
        {
            "text": text,
            "target_language_code": "hi-IN",
            "model": "bulbul:v3",
            "speaker": "priya",
            "pace": pace,
        }
    ).encode()
    request = Request(
        _SPEECH_URL,
        data=body,
        headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    audios = payload.get("audios")
    if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
        raise ValueError("speech provider returned no audio")
    return base64.b64decode(audios[0])


class SarvamTTS:
    name = "sarvam"

    def __init__(
        self, api_key: str, transport: Callable[[str, str, float], bytes] | None = None
    ) -> None:
        self._api_key = api_key
        self._transport = transport if transport is not None else _post

    async def synthesize_stream(self, text: str, lang: str, rate: float) -> AsyncIterator[bytes]:
        del lang
        yield self._transport(self._api_key, text, rate)


class SarvamSTT:
    """The browser already has a transcript. This returns that UTF-8 text."""

    name = "sarvam"

    async def transcribe_stream(
        self, audio: AsyncIterator[bytes], lang: str
    ) -> AsyncIterator[Transcript]:
        del lang
        chunks: list[bytes] = []
        async for chunk in audio:
            chunks.append(chunk)
        yield Transcript(text=b"".join(chunks).decode("utf-8"))
