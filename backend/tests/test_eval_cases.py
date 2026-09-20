"""Sanity checks on the eval's own inputs. A broken case makes every result meaningless."""

from __future__ import annotations

import json

from app.services.trace_generator import precheck
from evals.build_gold import GOLD_PATH
from evals.cases import CASES

GOLD = json.loads(GOLD_PATH.read_text())
NOT_EXECUTABLE = {"", "{", "}", "};"}


def test_ids_are_unique():
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))


def test_every_referenced_line_is_a_real_executable_line():
    """A fact about line 14 in a 13-line program, or about a brace, can never be satisfied."""
    for case in CASES:
        lines = case.source.split("\n")
        referenced = [f.line for f in case.facts if f.line is not None]
        if case.fails_at_line is not None:
            referenced.append(case.fails_at_line)
        for n in referenced:
            assert 1 <= n <= len(lines), f"{case.id}: line {n} is outside the program"
            assert lines[n - 1].strip() not in NOT_EXECUTABLE, f"{case.id}: line {n} is not a statement"


def test_every_runnable_case_has_gold_from_the_jvm():
    for case in CASES:
        assert (case.id in GOLD) == case.oracle, f"{case.id}: gold.json out of date, rerun build_gold"


def test_gold_agrees_with_what_each_case_claims():
    for case in CASES:
        if not case.oracle:
            continue
        gold = GOLD[case.id]
        if not case.compiles:
            assert gold["compiles"] is False and gold["compile_error"]
        elif case.expect == "exception":
            assert gold["exception"] == case.exception and gold["exit_code"] != 0
        else:
            assert gold["exit_code"] == 0 and gold["exception"] is None


def test_code_that_does_not_compile_is_a_decline_never_a_trace():
    broken = [c for c in CASES if not c.compiles]
    assert broken, "no compile-error cases: the most common student mistake is untested"
    for case in broken:
        assert case.expect == "unsupported" and not case.facts


def test_exception_cases_say_where_they_fail_and_others_do_not():
    for case in CASES:
        assert (case.expect == "exception") == (case.fails_at_line is not None and case.exception is not None)


def test_only_the_bare_snippet_is_stopped_before_the_model():
    """Every other case reaches the model: it is the model being tested, not the precheck."""
    for case in CASES:
        stopped = precheck(case.source) is not None
        assert stopped == (case.id == "decline_bare_snippet"), case.id


def test_declined_cases_carry_no_facts_and_traced_cases_carry_some():
    for case in CASES:
        if case.expect == "unsupported":
            assert not case.facts
        else:
            assert case.facts, f"{case.id} would pass on stdout alone"


def test_the_set_has_both_things_to_trace_and_things_to_decline():
    traced = [c for c in CASES if c.expect != "unsupported"]
    declined = [c for c in CASES if c.expect == "unsupported"]
    assert traced and declined
