"""The grader, tested the way an eval must be: an oracle that must pass, and nulls and
plausible-but-wrong answers that must fail. Known-correct traces come from the golden fixtures."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.execution import TraceOk, TraceUnsupported
from app.services.llm import Reply, UnusableOutput
from app.services.trace_generator import Attempt, Generation
from evals.cases import Case
from evals.facts import Field, Heap, Same
from evals.grade import _mentions_exception, grade_generation, judge
from tests.conftest import load

USAGE = SimpleNamespace(input_tokens=10, output_tokens=20, cache_creation_input_tokens=1, cache_read_input_tokens=100)


def reply(result, model="claude-opus-5") -> Reply:
    return Reply(result=result, raw="{}", stop_reason="end_turn", usage=USAGE, request_id="req", model=model)


def alias_case() -> tuple[Case, dict, TraceOk]:
    """reference_aliasing as an eval case: 11 a=new, 12 b=a, 14 b.value=5, 16 println."""
    source, trace = load("reference_aliasing")
    case = Case(
        id="alias", category="core", why="", source=source, expect="ok",
        facts=(Same("a", "b", 12), Heap(1, 12), Field("a", "value", 5, 14)),
    )
    return case, {"stdout": ["5"]}, trace


def decline_case() -> Case:
    source, _ = load("reference_aliasing")
    return Case(id="decline", category="decline", why="", source=source, expect="unsupported")


def unsupported() -> TraceUnsupported:
    return TraceUnsupported(status="unsupported", message="Not supported.", unsupportedFeatures=["x"])


# --- the oracle: a correct answer must pass -----------------------------------------


def test_oracle_a_correct_trace_passes():
    case, gold, trace = alias_case()
    verdict = judge(case, gold, trace)
    assert verdict.correct and verdict.reasons == []


def test_oracle_a_correct_decline_passes():
    assert judge(decline_case(), None, unsupported()).correct


# --- the nulls: things that must fail ----------------------------------------------------


def test_null_no_answer_fails():
    case, gold, _ = alias_case()
    assert not judge(case, gold, None).correct


def test_null_declining_a_program_that_should_be_traced_fails():
    case, gold, _ = alias_case()
    verdict = judge(case, gold, unsupported())
    assert not verdict.correct and "declined a program that should be traced" in verdict.reasons[0]


def test_null_an_empty_trace_fails():
    case, gold, _ = alias_case()
    assert not judge(case, gold, TraceOk(status="ok", steps=[])).correct


def test_null_tracing_a_program_that_should_be_declined_fails():
    _, _, trace = alias_case()
    verdict = judge(decline_case(), None, trace)
    assert not verdict.correct and "should have been declined" in verdict.reasons[0]


def test_wrong_stdout_fails_even_when_everything_else_is_plausible():
    case, gold, trace = alias_case()
    wrong = trace.model_copy(deep=True)
    wrong.steps[-1].stdout = ["1"]  # the classic wrong answer: a.value never changed
    verdict = judge(case, gold, wrong)
    assert not verdict.correct
    assert any("stdout" in r for r in verdict.reasons)


def test_the_aliasing_lie_passes_the_validator_but_the_facts_catch_it():
    """b gets its own copy of the object. Well-formed, ids unique, refs resolve: only a fact can tell."""
    case, gold, trace = alias_case()
    lie = trace.model_copy(deep=True)
    for step in lie.steps[1:]:
        step.stackFrames[0].variables[1].value.target = "obj_2"
        twin = step.heap[0].model_copy(deep=True)
        twin.id = "obj_2"
        step.heap.append(twin)

    verdict = judge(case, gold, lie)

    assert not verdict.correct
    assert not any(r.startswith("validator") for r in verdict.reasons), "the validator alone cannot see this"
    assert any(r.startswith("fact") for r in verdict.reasons)


# --- crashes ----------------------------------------------------------------------------------


def crash_case() -> tuple[Case, dict, TraceOk]:
    """primitive_copy cut off after line 4, as if line 4 threw."""
    source, trace = load("primitive_copy")
    crashed = TraceOk(status="ok", steps=[s.model_copy(deep=True) for s in trace.steps[:2]])
    crashed.steps[-1].explanation = "Line 4 throws a NullPointerException, so the program stops here."
    case = Case(
        id="crash", category="secondary", why="", source=source, expect="exception",
        exception="NullPointerException", fails_at_line=4, facts=(),
    )
    return case, {"stdout": []}, crashed


def test_a_crash_trace_must_end_on_the_failing_line_and_name_the_exception():
    case, gold, trace = crash_case()
    assert judge(case, gold, trace).correct

    wrong_line = Case(**{**case.__dict__, "fails_at_line": 3})
    assert any("ends at line 4" in r for r in judge(wrong_line, gold, trace).reasons)

    silent = trace.model_copy(deep=True)
    silent.steps[-1].explanation = "The program stops here."
    assert any("never names" in r for r in judge(case, gold, silent).reasons)


@pytest.mark.parametrize(
    "text, exception, expected",
    [
        ("throws a NullPointerException", "NullPointerException", True),
        ("this is a null pointer error", "NullPointerException", True),
        ("Array index out of bounds here", "ArrayIndexOutOfBoundsException", True),
        ("the program stops", "NullPointerException", False),
    ],
)
def test_naming_the_exception_accepts_either_spelling(text, exception, expected):
    assert _mentions_exception(text, exception) is expected


# --- grade_generation: first try vs final, refusals, truncation, usage -----------------------------


def test_a_clean_single_attempt():
    case, gold, trace = alias_case()
    graded = grade_generation(case, gold, Generation(result=trace, attempts=[Attempt(reply(trace), 1.5)]))

    assert graded.grade == {"correct": 1.0, "first_try": 1.0, "refused": 0.0}
    assert graded.status == "ok" and graded.attempts == 1 and graded.steps == len(trace.steps)
    assert graded.usage == {
        "input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 1, "cache_read_input_tokens": 100,
    }
    assert graded.model == "claude-opus-5" and graded.latency_s == 1.5


def test_the_repair_retry_rescuing_a_bad_first_attempt_shows_as_first_try_zero_correct_one():
    case, gold, trace = alias_case()
    bad = trace.model_copy(deep=True)
    bad.steps[-1].stdout = ["1"]
    gen = Generation(
        result=trace,
        attempts=[Attempt(reply(bad), 2.0, ["step 4: something"]), Attempt(reply(trace), 3.0)],
    )

    graded = grade_generation(case, gold, gen)

    assert graded.grade["correct"] == 1.0 and graded.grade["first_try"] == 0.0
    assert graded.usage["input_tokens"] == 20, "both attempts are billed"
    assert graded.latency_s == 5.0 and graded.attempts == 2


def test_a_precheck_answer_has_no_model_call_and_is_not_padded_with_fake_numbers():
    gen = Generation(result=unsupported(), prechecked=True)
    graded = grade_generation(decline_case(), None, gen)

    assert graded.grade["correct"] == 1.0 and graded.grade["first_try"] == 1.0
    assert graded.model is None and graded.attempts == 0 and graded.latency_s == 0
    assert graded.usage["input_tokens"] == 0


def test_a_truncated_answer_is_excluded_not_scored_as_wrong():
    case, gold, _ = alias_case()
    gen = Generation(
        result=unsupported(),
        attempts=[Attempt(None, 30.0, unusable=UnusableOutput("cut off", kind="unparseable"))],
    )

    graded = grade_generation(case, gold, gen)

    assert graded.status == "truncated" and graded.grade == {}
    assert graded.unknown_usage_attempts == 1, "billed, but the usage was never readable"


def test_a_refusal_is_its_own_metric_and_never_a_lucky_correct_decline():
    """The app answers `unsupported` after a refusal. On a should-decline case that must not score as correct."""
    gen = Generation(
        result=unsupported(),
        attempts=[Attempt(None, 1.0, unusable=UnusableOutput("refused", kind="refusal"))],
    )

    graded = grade_generation(decline_case(), None, gen)

    assert graded.status == "ok"
    assert graded.grade == {"correct": 0.0, "first_try": 0.0, "refused": 1.0}
