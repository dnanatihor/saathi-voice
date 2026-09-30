"""Text in, text out. Used by tests and the dashboard simulate-call action."""

from saathi.dialog.graph import Beat, DialogSession


class TextChannel:
    def __init__(self, session: DialogSession) -> None:
        self.session = session

    def start(self) -> list[str]:
        return self.session.start().spoken

    def receive(self, text: str) -> list[str]:
        beat: Beat = self.session.user_turn(text)
        return beat.spoken
