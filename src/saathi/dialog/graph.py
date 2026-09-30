"""LangGraph dialog. Emergency is applied before the intent transition."""

from dataclasses import dataclass
from typing import TypedDict, cast

from langgraph.graph import END, START, StateGraph

from saathi.eval_schema import Flow, NotificationExpectation
from saathi.phrases import Phrase, render


class DialogError(Exception):
    """The dialog reached a step the scripted flows do not define."""


class GraphState(TypedDict):
    flow: str
    step: str
    turn_kind: str
    user_text: str
    prior_snoozes: int
    clarify_count: int
    silence_count: int
    rules_emergency: bool
    nlu_intent: str
    states: list[str]
    phrase_ids: list[str]
    events: list[str]
    notifications: list[dict[str, str]]
    session_remains_open: bool
    closed: bool


def _base(state: GraphState, **updates: object) -> GraphState:
    data: dict[str, object] = dict(state)
    data.update(updates)
    return cast(GraphState, data)


def _opening_reminder(state: GraphState) -> GraphState:
    return _base(
        state,
        step="AskTaken",
        states=["Greet", "Remind", "AskTaken"],
        phrase_ids=["greet.reminder", "remind.dose", "remind.instructions", "ask.taken"],
        events=["reminder_sent"],
        notifications=[],
        session_remains_open=False,
        closed=False,
    )


def _opening_checkin(state: GraphState) -> GraphState:
    return _base(
        state,
        step="AskWellbeing",
        states=["Greet", "AskWellbeing"],
        phrase_ids=["checkin.greet", "checkin.ask"],
        events=[],
        notifications=[],
        session_remains_open=False,
        closed=False,
    )


def _emergency(state: GraphState) -> GraphState:
    return _base(
        state,
        states=["Emergency"],
        phrase_ids=["emergency.alert"],
        events=["emergency"],
        notifications=[
            {
                "audience": "emergency_contacts",
                "reason": "emergency",
                "template_id": "notify.emergency",
            }
        ],
        session_remains_open=True,
        closed=False,
    )


def _missed(state: GraphState) -> GraphState:
    return _base(
        state,
        step="Close",
        states=["Missed", "NotifyCaregiver", "Close"],
        phrase_ids=["ack.missed", "close.polite"],
        events=["missed"],
        notifications=[
            {"audience": "caregiver", "reason": "missed", "template_id": "notify.missed"}
        ],
        session_remains_open=False,
        closed=True,
    )


def _on_ask_taken(state: GraphState) -> GraphState:
    intent = state["nlu_intent"]
    if intent == "taken":
        return _base(
            state,
            step="Close",
            states=["Taken", "Close"],
            phrase_ids=["ack.taken", "close.polite"],
            events=["taken"],
            notifications=[],
            session_remains_open=False,
            closed=True,
        )
    if intent in {"not_yet", "later"}:
        if state["prior_snoozes"] >= 1:
            return _missed(state)
        return _base(
            state,
            step="Snooze",
            states=["Snooze"],
            phrase_ids=["ack.snooze"],
            events=["snoozed"],
            notifications=[],
            session_remains_open=False,
            closed=True,
        )
    if state["clarify_count"] >= 1:
        return _missed(state)
    return _base(
        state,
        step="AskTaken",
        clarify_count=state["clarify_count"] + 1,
        states=["Clarify", "AskTaken"],
        phrase_ids=["clarify.taken", "ask.taken"],
        events=[],
        notifications=[],
        session_remains_open=False,
        closed=False,
    )


def _on_wellbeing(state: GraphState) -> GraphState:
    intent = state["nlu_intent"]
    if intent == "wellbeing_good":
        return _base(
            state,
            step="Close",
            states=["Close"],
            phrase_ids=["checkin.good"],
            events=["checkin_result"],
            notifications=[],
            session_remains_open=False,
            closed=True,
        )
    if intent == "wellbeing_okay":
        return _base(
            state,
            step="Close",
            states=["Close"],
            phrase_ids=["checkin.okay"],
            events=["checkin_result"],
            notifications=[],
            session_remains_open=False,
            closed=True,
        )
    if intent == "wellbeing_unwell":
        return _base(
            state,
            step="FollowUpUnwell",
            states=["FollowUpUnwell"],
            phrase_ids=["checkin.unwell_offer"],
            events=[],
            notifications=[],
            session_remains_open=False,
            closed=False,
        )
    # `other` and `confused` have no specified health reply. End without a summary.
    return _base(
        state,
        step="Close",
        states=["Close"],
        phrase_ids=["close.polite"],
        events=[],
        notifications=[],
        session_remains_open=False,
        closed=True,
    )


def _on_followup(state: GraphState) -> GraphState:
    return _base(
        state,
        step="Close",
        states=["NotifyCaregiver", "Close"],
        phrase_ids=["checkin.notify_ack", "close.polite"],
        events=["checkin_result"],
        notifications=[
            {
                "audience": "caregiver",
                "reason": "checkin_unwell",
                "template_id": "summary.checkin",
            }
        ],
        session_remains_open=False,
        closed=True,
    )


def _silence(state: GraphState) -> GraphState:
    if state["silence_count"] >= 1:
        return _base(
            state,
            step="Close",
            silence_count=state["silence_count"] + 1,
            states=["Close"],
            phrase_ids=["silence.end"],
            events=[],
            notifications=[],
            session_remains_open=False,
            closed=True,
        )
    return _base(
        state,
        silence_count=1,
        states=[state["step"]],
        phrase_ids=["silence.repeat"],
        events=[],
        notifications=[],
        session_remains_open=False,
        closed=False,
    )


def choose(state: GraphState) -> str:
    if state["turn_kind"] == "start":
        if state["flow"] == "daily_checkin":
            return "opening_checkin"
        return "opening_reminder"
    if state["turn_kind"] == "silence":
        return "silence"
    if state["rules_emergency"] or state["nlu_intent"] == "emergency":
        return "emergency"
    step = state["step"]
    if step == "AskWellbeing":
        return "on_wellbeing"
    if step == "FollowUpUnwell":
        return "on_followup"
    if step == "AskTaken":
        return "on_ask_taken"
    raise DialogError(f"no transition from {step}")


def build_graph() -> object:
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("opening_reminder", _opening_reminder)
    builder.add_node("opening_checkin", _opening_checkin)
    builder.add_node("emergency", _emergency)
    builder.add_node("on_ask_taken", _on_ask_taken)
    builder.add_node("on_wellbeing", _on_wellbeing)
    builder.add_node("on_followup", _on_followup)
    builder.add_node("silence", _silence)
    builder.add_conditional_edges(
        START,
        choose,
        {
            "opening_reminder": "opening_reminder",
            "opening_checkin": "opening_checkin",
            "emergency": "emergency",
            "on_ask_taken": "on_ask_taken",
            "on_wellbeing": "on_wellbeing",
            "on_followup": "on_followup",
            "silence": "silence",
        },
    )
    for name in (
        "opening_reminder",
        "opening_checkin",
        "emergency",
        "on_ask_taken",
        "on_wellbeing",
        "on_followup",
        "silence",
    ):
        builder.add_edge(name, END)
    return builder.compile()


_COMPILED = build_graph()


@dataclass(frozen=True)
class Persona:
    honorific: str = "बाबूजी"
    spoken_label: str = "बीपी की दवा"
    instructions: str = "खाने के बाद"


@dataclass(frozen=True)
class Beat:
    states: list[str]
    phrase_ids: list[str]
    events: list[str]
    notifications: list[NotificationExpectation]
    session_remains_open: bool
    spoken: list[str]


def _blank_state(flow: Flow, prior_snoozes: int) -> GraphState:
    return {
        "flow": flow,
        "step": "",
        "turn_kind": "start",
        "user_text": "",
        "prior_snoozes": prior_snoozes,
        "clarify_count": 0,
        "silence_count": 0,
        "rules_emergency": False,
        "nlu_intent": "other",
        "states": [],
        "phrase_ids": [],
        "events": [],
        "notifications": [],
        "session_remains_open": False,
        "closed": False,
    }


class DialogSession:
    def __init__(
        self,
        flow: Flow,
        phrases: dict[str, Phrase],
        *,
        prior_snoozes: int = 0,
        persona: Persona | None = None,
        understanding: object | None = None,
        detector: object | None = None,
    ) -> None:
        from saathi.dialog.emergency import EmergencyDetector
        from saathi.dialog.nlu import Understanding

        self.flow = flow
        self.phrases = phrases
        self.persona = persona if persona is not None else Persona()
        self._understanding = (
            understanding if isinstance(understanding, Understanding) else Understanding()
        )
        if detector is None:
            from saathi.config import emergency_phrase_path, load_config
            from saathi.dialog.emergency import EmergencyDetector as Detector
            from saathi.phrases import load_emergency_phrases

            self._detector = Detector(load_emergency_phrases(emergency_phrase_path(load_config())))
        elif isinstance(detector, EmergencyDetector):
            self._detector = detector
        else:
            raise TypeError("detector must be an EmergencyDetector")
        self._state = _blank_state(flow, prior_snoozes)

    def start(self) -> Beat:
        return self._step("start", "")

    def user_turn(self, text: str) -> Beat:
        if self._state["closed"]:
            raise DialogError("session is closed")
        return self._step("speech", text)

    def silence(self) -> Beat:
        if self._state["closed"]:
            raise DialogError("session is closed")
        return self._step("silence", "")

    def _step(self, kind: str, text: str) -> Beat:
        from saathi.dialog.nlu import Understanding

        state: GraphState = {
            **self._state,
            "turn_kind": kind,
            "user_text": text,
            "rules_emergency": False,
            "nlu_intent": "other",
        }
        if kind == "speech":
            state["rules_emergency"] = self._detector.is_emergency(text)
            assert isinstance(self._understanding, Understanding)
            understood = self._understanding.understand(text, state["step"])
            state["nlu_intent"] = understood.intent
        result = _COMPILED.invoke(state)  # type: ignore[attr-defined]
        if not isinstance(result, dict):
            raise DialogError("dialog graph returned an unexpected value")
        self._state = _copy_state(result)
        return self._beat(self._state)

    def _beat(self, state: GraphState) -> Beat:
        snippet = state["user_text"][:80]
        values = {
            "honorific": self.persona.honorific,
            "spoken_label": self.persona.spoken_label,
            "instructions": self.persona.instructions,
            "elder_words": snippet,
            "snippet": snippet,
        }
        spoken: list[str] = []
        for phrase_id in state["phrase_ids"]:
            phrase = self.phrases[phrase_id]
            if not phrase.spoken:
                raise DialogError(f"{phrase_id} is a notification template")
            spoken.append(render(phrase.text, values))
        notes = [NotificationExpectation.model_validate(item) for item in state["notifications"]]
        return Beat(
            states=list(state["states"]),
            phrase_ids=list(state["phrase_ids"]),
            events=list(state["events"]),
            notifications=notes,
            session_remains_open=state["session_remains_open"],
            spoken=spoken,
        )


def _copy_state(result: dict[str, object]) -> GraphState:
    required = (
        "flow",
        "step",
        "turn_kind",
        "user_text",
        "prior_snoozes",
        "clarify_count",
        "silence_count",
        "rules_emergency",
        "nlu_intent",
        "states",
        "phrase_ids",
        "events",
        "notifications",
        "session_remains_open",
        "closed",
    )
    copied: dict[str, object] = {}
    for key in required:
        if key not in result:
            raise DialogError(f"dialog graph omitted {key}")
        copied[key] = result[key]
    return copied  # type: ignore[return-value]
