"""Short silent clips used when a speech provider has no live voice."""

import io
import wave


def silence_wav(text: str) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "w") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(8000)
        frames = 800 * max(1, len(text.split()))
        clip.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()
