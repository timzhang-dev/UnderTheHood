"""llm.ask is the seam to the API: which path it takes, and how each failure is classified."""

from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.models.execution import TraceUnsupported
from app.prompts.execution_trace import SYSTEM_PROMPT
from app.services.llm import (
    FALLBACK_BETA,
    MODEL,
    ModelOutput,
    TraceServiceError,
    UnusableOutput,
    ask,
)
from tests.conftest import load
from tests.fakes import FakeClient, reply_for

MESSAGES = [{"role": "user", "content": "trace this"}]
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls, code: int):
    return cls("boom", response=httpx2.Response(code, request=REQUEST), body=None)


def test_default_path_is_beta_parse_with_the_refusal_fallback():
    _, trace = load("array_aliasing")
    client = FakeClient(trace)
    ask(MESSAGES, client=client)

    assert client.used == ["beta"]
    call = client.calls[0]
    assert call["betas"] == [FALLBACK_BETA]
    assert call["fallbacks"] == "default"
    assert call["model"] == MODEL
    assert call["output_format"] is ModelOutput


def test_system_prompt_is_sent_as_a_cacheable_block():
    _, trace = load("array_aliasing")
    client = FakeClient(trace)
    ask(MESSAGES, client=client)

    (block,) = client.calls[0]["system"]
    assert block["text"] == SYSTEM_PROMPT
    assert block["cache_control"] == {"type": "ephemeral"}


def test_fallback_can_be_switched_off_without_a_code_change(monkeypatch):
    monkeypatch.setenv("REFUSAL_FALLBACK", "0")
    _, trace = load("array_aliasing")
    client = FakeClient(trace)
    ask(MESSAGES, client=client)

    assert client.used == ["plain"]
    assert "betas" not in client.calls[0] and "fallbacks" not in client.calls[0]


def test_reply_keeps_the_raw_text_so_a_repair_can_echo_it():
    _, trace = load("array_aliasing")
    reply = ask(MESSAGES, client=FakeClient(trace))
    assert reply.result == trace
    assert reply.raw == ModelOutput(result=trace).model_dump_json()
    assert reply.request_id == "req_test"


def test_an_unsupported_answer_comes_through_as_a_normal_reply():
    unsupported = TraceUnsupported(status="unsupported", message="No.", unsupportedFeatures=["generics"])
    assert ask(MESSAGES, client=FakeClient(unsupported)).result == unsupported


@pytest.mark.parametrize(
    "error, expected_in_message",
    [
        (status_error(anthropic.AuthenticationError, 401), "key was rejected"),
        (status_error(anthropic.RateLimitError, 429), "busy"),
        (status_error(anthropic.BadRequestError, 400), "rejected"),
        (status_error(anthropic.InternalServerError, 500), "problem"),
        (anthropic.APIConnectionError(request=REQUEST), "reach"),
        (TypeError('"Could not resolve authentication method. Expected one of api_key..."'), "no API key"),
    ],
)
def test_service_failures_become_service_errors(error, expected_in_message):
    with pytest.raises(TraceServiceError, match=expected_in_message):
        ask(MESSAGES, client=FakeClient(error))


def test_unrelated_type_errors_are_bugs_and_are_not_swallowed():
    with pytest.raises(TypeError, match="boom"):
        ask(MESSAGES, client=FakeClient(TypeError("boom")))


def test_unparseable_output_is_unusable_not_a_service_error():
    with pytest.raises(UnusableOutput):
        ask(MESSAGES, client=FakeClient(ValueError("cut off mid-json")))


def test_a_refusal_is_unusable():
    refused = SimpleNamespace(parsed_output=None, content=[], stop_reason="refusal", usage=None, _request_id="r")
    with pytest.raises(UnusableOutput, match="refusal"):
        ask(MESSAGES, client=FakeClient(refused))
