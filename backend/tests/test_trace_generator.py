"""The generate -> validate -> repair-once -> give-up flow, against a scripted fake model."""

from __future__ import annotations

import pytest

from app.models.execution import TraceOk, TraceUnsupported
from app.services.llm import ModelOutput, UnusableOutput
from app.services.trace_generator import MAX_CODE_CHARS, generate, generate_trace, precheck
from tests.conftest import load
from tests.fakes import FakeClient


def broken(trace: TraceOk) -> TraceOk:
    """The same trace with b pointing at an id that is not on the heap."""
    bad = trace.model_copy(deep=True)
    bad.steps[1].stackFrames[0].variables[1].value.target = "obj_9"
    return bad


# --- deterministic prechecks: never cost a model call ----------------------


@pytest.mark.parametrize(
    "code, feature",
    [
        ("", "empty input"),
        ("   \n\t ", "empty input"),
        ("int x = 5;\nint y = x;", "bare snippet"),
        ("x" * (MAX_CODE_CHARS + 1), "program too long"),
    ],
)
def test_unusable_input_is_rejected_without_calling_the_model(code, feature):
    client = FakeClient()  # any call would raise IndexError
    result = generate_trace(code, client=client)

    assert isinstance(result, TraceUnsupported)
    assert any(feature in f for f in result.unsupportedFeatures)
    assert client.calls == []


def test_a_complete_program_passes_the_precheck(fixture_names):
    for name in fixture_names:
        source, _ = load(name)
        assert precheck(source) is None


def test_the_bare_snippet_message_tells_the_student_how_to_fix_it():
    result = precheck("int x = 5;")
    assert "public static void main" in result.message
    assert "examples" in result.message


# --- the flow ----------------------------------------------------------------


def test_a_valid_first_answer_is_returned_after_a_single_call():
    source, trace = load("array_aliasing")
    client = FakeClient(trace)

    assert generate_trace(source, client=client) == trace
    assert len(client.calls) == 1


def test_an_invalid_answer_gets_exactly_one_repair_with_the_errors_attached():
    source, trace = load("array_aliasing")
    client = FakeClient(broken(trace), trace)

    result = generate_trace(source, client=client)

    assert result == trace
    assert len(client.calls) == 2
    first, second = client.calls[0]["messages"], client.calls[1]["messages"]
    assert [m["role"] for m in first] == ["user"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[1]["content"] == ModelOutput(result=broken(trace)).model_dump_json()
    assert "obj_9" in second[2]["content"], "the validator's error must reach the model verbatim"


def test_two_invalid_answers_end_in_unsupported_never_a_wrong_trace():
    source, trace = load("array_aliasing")
    client = FakeClient(broken(trace), broken(trace))

    result = generate_trace(source, client=client)

    assert isinstance(result, TraceUnsupported)
    assert len(client.calls) == 2, "no third attempt"
    assert "trust" in result.message


def test_the_model_declining_a_program_passes_straight_through():
    source, _ = load("array_aliasing")
    declined = TraceUnsupported(status="unsupported", message="Uses generics.", unsupportedFeatures=["generics"])
    client = FakeClient(declined)

    assert generate_trace(source, client=client) == declined
    assert len(client.calls) == 1


def test_unparseable_output_becomes_unsupported_without_a_pointless_retry():
    source, _ = load("array_aliasing")
    client = FakeClient(UnusableOutput("cut off"))

    result = generate_trace(source, client=client)

    assert isinstance(result, TraceUnsupported)
    assert "too long or complicated" in result.message
    assert len(client.calls) == 1


# --- generate(): the same flow, with a report of what happened -------------------------------------


def test_generate_reports_every_attempt_and_what_the_validator_said():
    source, trace = load("array_aliasing")

    gen = generate(source, client=FakeClient(broken(trace), trace))

    assert gen.result == trace and not gen.prechecked
    assert len(gen.attempts) == 2
    assert gen.attempts[0].validation_errors and gen.attempts[1].validation_errors == []
    assert all(a.reply is not None and a.latency_s >= 0 for a in gen.attempts)


def test_generate_marks_answers_that_needed_no_model_call():
    gen = generate("int x = 5;", client=FakeClient())
    assert gen.prechecked and gen.attempts == []


def test_generate_records_an_attempt_that_returned_nothing_usable():
    source, _ = load("array_aliasing")

    gen = generate(source, client=FakeClient(ValueError("cut off")))

    (attempt,) = gen.attempts
    assert attempt.reply is None and attempt.unusable.kind == "unparseable"


def test_generate_trace_is_exactly_generate_result():
    source, trace = load("array_aliasing")
    assert generate_trace(source, client=FakeClient(trace)) == generate(source, client=FakeClient(trace)).result
