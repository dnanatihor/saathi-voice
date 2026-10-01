"""Outbound reminder calls. The scripted leg never dials a telephone network."""

from typing import Protocol

from saathi.dialog.graph import Beat, DialogSession, Persona
from saathi.phrases import Phrase

DTMF_TAKEN = "1"


class CallLeg(Protocol):
    def say(self, text: str) -> None: ...

    def heard_speech(self) -> str | None: ...

    def pressed_digit(self) -> str | None: ...


class ScriptedLeg:
    def __init__(self, speech: list[str | None], digits: list[str | None]) -> None:
        self.said: list[str] = []
        self._speech = list(speech)
        self._digits = list(digits)

    def say(self, text: str) -> None:
        self.said.append(text)

    def heard_speech(self) -> str | None:
        if not self._speech:
            return None
        return self._speech.pop(0)

    def pressed_digit(self) -> str | None:
        if not self._digits:
            return None
        return self._digits.pop(0)


def run_reminder_call(
    leg: CallLeg,
    phrases: dict[str, Phrase],
    *,
    persona: Persona | None = None,
) -> Beat:
    session = DialogSession(flow="medication_reminder", phrases=phrases, persona=persona)
    opening = session.start()
    for line in opening.spoken:
        leg.say(line)
    speech = leg.heard_speech()
    if speech is None or not speech.strip():
        leg.say(phrases["ask.dtmf"].text)
        text = "हाँ, ले ली" if leg.pressed_digit() == DTMF_TAKEN else ""
        beat = session.user_turn(text)
    else:
        beat = session.user_turn(speech)
    for line in beat.spoken:
        leg.say(line)
    return beat
