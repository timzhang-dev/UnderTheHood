"""The runner, end to end against a scripted fake model: what it writes, what it refuses to
write, and how it fails. The audit's "an induced API error must be an error, not a zero"
lives here."""

from __future__ import annotations

import json

import pytest

from app.models.execution import TraceUnsupported
from app.services.llm import TraceServiceError
from evals import run as runner
from evals.cases import Case
from evals.facts import Field, Heap, Same
from evals.run import MAX_RETRIES, check_harness, run_eval, served_ok, summarize, wilson
from tests.conftest import load
from tests.fakes import FakeClient, reply_for

SOURCE, TRACE = load("reference_aliasing")

OK_CASE = Case(
    id="alias", category="core", why="", source=SOURCE, expect="ok",
    facts=(Same("a", "b", 12), Heap(1, 12), Field("a", "value", 5, 14)),
)
DECLINE_CASE = Case(id="decline", category="decline", why="", source=SOURCE, expect="unsupported")
SNIPPET_CASE = Case(id="snippet", category="decline", why="", source="int x = 5;", expect="unsupported")
GOLD = {"alias": {"stdout": ["5"]}}
DECLINE = TraceUnsupported(status="unsupported", message="No.", unsupportedFeatures=["x"])


def go(tmp_path, cases, client, **kw):
    sleeps: list[float] = []
    lines: list[str] = []
    summary = run_eval(
        cases=cases, gold=GOLD, client=client, flow=tmp_path, concurrency=1,
        sleep=sleeps.append, out=lines.append, **kw,
    )
    return summary, sleeps


def rows(tmp_path, name="results.jsonl"):
    path = tmp_path / "baseline" / name
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# --- a good run writes a complete, plausible row --------------------------------------------------


def test_a_correct_run_writes_a_complete_row_and_a_readable_trace(tmp_path):
    summary, _ = go(tmp_path, [OK_CASE], FakeClient(TRACE))

    (row,) = rows(tmp_path)
    assert row["prompt_id"] == "alias" and row["rep"] == 0 and row["prompt"] == SOURCE
    assert row["tags"] == ["core", "should-trace"]
    assert row["grade"] == {"correct": 1.0, "first_try": 1.0, "refused": 0.0}
    # Every field the report needs is present and non-trivial on a model-backed row.
    assert row["model"] == "claude-opus-5" and row["stop_reason"] == "end_turn"
    assert row["usage"]["input_tokens"] == 10 and row["usage"]["output_tokens"] == 20
    assert row["latency_s"] >= 0 and row["attempts"] == 1 and row["steps"] == len(TRACE.steps)
    assert "status" not in row

    turns = json.loads((tmp_path / "baseline" / "traces" / "alias_rep0.json").read_text())
    assert [t["role"] for t in turns] == ["system", "user", "assistant", "assistant"]
    assert turns[-1]["content"].startswith("[grader] correct=1")
    assert summary["correct"][:2] == (1, 1)


def test_resume_skips_what_is_already_scored_and_makes_no_calls(tmp_path):
    go(tmp_path, [OK_CASE], FakeClient(TRACE))
    go(tmp_path, [OK_CASE], FakeClient())  # an empty script raises IndexError if anything is called
    assert len(rows(tmp_path)) == 1


def test_more_reps_run_only_the_missing_ones(tmp_path):
    go(tmp_path, [OK_CASE], FakeClient(TRACE), reps=1)
    go(tmp_path, [OK_CASE], FakeClient(TRACE), reps=2)
    assert sorted(r["rep"] for r in rows(tmp_path)) == [0, 1]


# --- failures are errors, never zeros -----------------------------------------------------------------


def test_a_service_error_lands_in_errors_not_as_a_wrong_answer(tmp_path):
    summary, _ = go(tmp_path, [OK_CASE], FakeClient(TraceServiceError("The server has no API key configured.")))

    assert rows(tmp_path) == [], "nothing may occupy the (case, rep) slot"
    (error,) = rows(tmp_path, "errors.jsonl")
    assert error["failure_class"] == "service_error" and error["prompt_id"] == "alias"
    assert summary["scored"] == 0 and summary["errors"] == {"service_error": 1}

    go(tmp_path, [OK_CASE], FakeClient(TRACE))  # the failed case is retried on the next run
    assert len(rows(tmp_path)) == 1


def test_a_busy_service_is_retried_with_backoff_and_the_retry_is_recorded(tmp_path):
    _, sleeps = go(tmp_path, [OK_CASE], FakeClient(TraceServiceError("busy", retryable=True), TRACE))

    (row,) = rows(tmp_path)
    assert row["meta"]["retries"] == 1 and row["grade"]["correct"] == 1.0
    assert len(sleeps) == 1 and sleeps[0] > 0


def test_retries_are_capped_and_then_the_case_is_an_error(tmp_path):
    busy = [TraceServiceError("busy", retryable=True)] * (MAX_RETRIES + 1)
    _, sleeps = go(tmp_path, [OK_CASE], FakeClient(*busy))

    assert rows(tmp_path) == []
    assert len(sleeps) == MAX_RETRIES
    assert rows(tmp_path, "errors.jsonl")[0]["failure_class"] == "service_error"


def test_a_response_from_the_wrong_model_is_an_error_not_a_score(tmp_path):
    _, _ = go(tmp_path, [OK_CASE], FakeClient(reply_for(TRACE, model="claude-sonnet-5")))

    assert rows(tmp_path) == []
    (error,) = rows(tmp_path, "errors.jsonl")
    assert error["failure_class"] == "serving_substitution" and error["model"] == "claude-sonnet-5"
    assert error["usage"]["input_tokens"] == 10, "billed spend on a failed attempt is still counted"


def test_a_dated_snapshot_of_the_requested_model_is_accepted(tmp_path):
    go(tmp_path, [OK_CASE], FakeClient(reply_for(TRACE, model="claude-opus-5-20260901")))
    assert len(rows(tmp_path)) == 1


@pytest.mark.parametrize(
    "requested, served, ok",
    [
        ("claude-opus-5", "claude-opus-5", True),
        ("claude-opus-5", "claude-opus-5-20260901", True),
        ("claude-opus-5", "claude-opus-5@20260901", True),
        ("claude-opus-5", "claude-opus-5-1", False),
        ("claude-opus-5", "claude-opus-4-8", False),
        ("claude-opus-5", "claude-opus-5-extended", False),
    ],
)
def test_served_model_rule(requested, served, ok):
    assert served_ok(requested, served) is ok


def test_a_harness_bug_is_recorded_and_does_not_stop_the_pass(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("grader crashed")

    monkeypatch.setattr(runner, "grade_generation", boom)
    go(tmp_path, [OK_CASE, DECLINE_CASE], FakeClient(TRACE, DECLINE))

    assert rows(tmp_path) == []
    assert [e["failure_class"] for e in rows(tmp_path, "errors.jsonl")] == ["harness_error"] * 2


# --- special rows ----------------------------------------------------------------------------------------------


def test_a_precheck_answer_is_scored_without_a_model_call(tmp_path):
    go(tmp_path, [SNIPPET_CASE], FakeClient())

    (row,) = rows(tmp_path)
    assert row["grade"]["correct"] == 1.0 and row["meta"]["prechecked"] is True
    assert row["model"] is None and row["attempts"] == 0


def test_truncated_output_is_flagged_and_left_out_of_the_means(tmp_path):
    summary, _ = go(tmp_path, [OK_CASE], FakeClient(ValueError("cut off mid-json")))

    (row,) = rows(tmp_path)
    assert row["status"] == "truncated" and row["grade"] == {}
    assert summary["truncated"] == 1 and summary["scored"] == 0


def test_tracing_a_program_that_should_be_declined_is_counted_as_the_dangerous_failure(tmp_path):
    summary, _ = go(tmp_path, [DECLINE_CASE], FakeClient(TRACE))

    (row,) = rows(tmp_path)
    assert row["grade"]["correct"] == 0.0
    assert summary["traced_should_decline"] == 1 and summary["specificity_should_decline"] == 0.0


# --- summary math -------------------------------------------------------------------------------------------------


def test_wilson_interval_is_wide_at_small_n_and_ordered():
    lo, hi = wilson(5, 10)
    assert 0.23 < lo < 0.25 and 0.75 < hi < 0.77
    assert wilson(0, 0) == (0.0, 1.0)
    assert wilson(10, 10)[1] == 1.0 and wilson(10, 10)[0] > 0.6


def test_the_summary_is_recomputed_from_rows_not_trusted_from_a_running_total(tmp_path):
    go(tmp_path, [OK_CASE, DECLINE_CASE, SNIPPET_CASE], FakeClient(TRACE, DECLINE))
    on_disk = summarize(rows(tmp_path), [], "claude-opus-5")

    assert on_disk["scored"] == 3
    assert on_disk["correct"][:2] == (3, 3)
    assert on_disk["by_category"] == {"core": (1, 1), "decline": (2, 2)}
    assert on_disk["cost_usd"] > 0, "a model-backed row must never cost zero"


# --- the harness gate -----------------------------------------------------------------------------------------------


def test_the_harness_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "BACKEND", tmp_path)
    grader = tmp_path / "grader.py"
    grader.write_text("v1")
    state_path = tmp_path / "_state.json"
    state = {"harness_paths": ["grader.py"]}

    assert check_harness(state_path, state, approve=False) == 2, "never approved"
    assert check_harness(state_path, state, approve=True) == 0 and state["harness_sha"]
    assert check_harness(state_path, state, approve=False) is None, "unchanged and approved"

    grader.write_text("v2 quietly weakened")
    assert check_harness(state_path, state, approve=False) == 2, "a changed yardstick must not run"
