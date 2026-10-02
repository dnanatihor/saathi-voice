"""A caregiver-uploaded clip played after the check-in greeting."""

import base64
from pathlib import Path

MAX_FAMILY_BYTES = 1_000_000


class FamilyMessageError(ValueError):
    """The upload is not a short WAV."""


def save_family_message(directory: Path, elder_id: int, audio: bytes) -> Path:
    if len(audio) > MAX_FAMILY_BYTES or not audio.startswith(b"RIFF"):
        raise FamilyMessageError("family message must be a WAV under 1 MB")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{elder_id}.wav"
    path.write_bytes(audio)
    return path


def delete_family_file(path: str) -> None:
    if path:
        Path(path).unlink(missing_ok=True)


def playback(spoken: list[str], clip: bytes | None) -> list[dict[str, str]]:
    """Greeting, then the family clip, then the rest of the opening."""
    parts: list[dict[str, str]] = []
    if not spoken:
        return parts
    parts.append({"kind": "speech", "text": spoken[0]})
    if clip:
        parts.append({"kind": "family", "audio_b64": base64.b64encode(clip).decode("ascii")})
    parts.extend({"kind": "speech", "text": line} for line in spoken[1:])
    return parts
