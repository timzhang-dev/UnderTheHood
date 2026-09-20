"""A stand-in for anthropic.Anthropic, so tests never touch the network or spend money."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.llm import ModelOutput


def reply_for(result, stop_reason: str = "end_turn", model: str = "claude-opus-5") -> SimpleNamespace:
    """What `messages.parse` returns for a model answer, as far as llm.ask reads it."""
    output = ModelOutput(result=result)
    return SimpleNamespace(
        parsed_output=output,
        content=[SimpleNamespace(type="text", text=output.model_dump_json())],
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(
            input_tokens=10, output_tokens=20, cache_creation_input_tokens=0, cache_read_input_tokens=0
        ),
        _request_id="req_test",
    )


class FakeClient:
    """Plays back scripted answers in order and records every call.

    Each scripted item is a trace/unsupported model (wrapped via reply_for), a ready-made
    reply object, or an Exception to raise. `used` says which API path each call took.
    """

    def __init__(self, *scripted):
        self._scripted = list(scripted)
        self.calls: list[dict] = []
        self.used: list[str] = []
        self.messages = SimpleNamespace(parse=lambda **kw: self._parse("plain", kw))
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=lambda **kw: self._parse("beta", kw)))

    def _parse(self, path: str, kwargs: dict):
        self.used.append(path)
        # Snapshot the list: the caller must not be able to change history after the fact.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, SimpleNamespace) else reply_for(item)
