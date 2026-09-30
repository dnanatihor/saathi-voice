"""Structured-output NLU. Live model calls stay out of the tests."""

from typing import Protocol

from saathi.dialog.nlu import IntentResult, NluUnavailable

Message = tuple[str, str]


class StructuredChat(Protocol):
    def invoke(self, messages: list[Message]) -> IntentResult: ...


class StructuredNlu:
    def __init__(self, chat: StructuredChat) -> None:
        self._chat = chat

    def classify(self, text: str, dialog_state: str, prompt: str) -> IntentResult:
        result = self._chat.invoke(
            [("system", prompt), ("human", f"dialog_state: {dialog_state}\n{text}")]
        )
        if not isinstance(result, IntentResult):
            raise NluUnavailable("model did not return an intent")
        return result


class LangchainStructured:
    """Calls `init_chat_model` only when `invoke` runs."""

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id

    def invoke(self, messages: list[Message]) -> IntentResult:
        try:
            from langchain.chat_models import init_chat_model
        except ImportError as exc:
            raise NluUnavailable("langchain chat model is not installed") from exc
        try:
            model = init_chat_model(self._model_id)
            structured = model.with_structured_output(IntentResult)
            raw = structured.invoke(messages)
        except NluUnavailable:
            raise
        except Exception as exc:
            raise NluUnavailable("language model call failed") from exc
        if isinstance(raw, IntentResult):
            return raw
        if isinstance(raw, dict):
            return IntentResult.model_validate(raw)
        raise NluUnavailable("model did not return an intent")
