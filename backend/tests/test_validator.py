"""The validator is only worth having if it actually rejects bad traces.

Each test corrupts a good fixture in a way a model plausibly could, and asserts
the corruption is caught. The null-reference case is tested here rather than in
the fixtures because none of the four examples produce a null.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import TypeAdapter

from app.models.execution import STEP_CAP, Step, TraceOk
from app.services.validator import validate_trace
from tests.conftest import load

STEPS = TypeAdapter(list[Step])


def corrupt(name: str, mutate) -> tuple[list[Step], str]:
    """Round-trips a fixture through dicts so a test can edit it, then re-validates."""
    source, trace = load(name)
    raw = copy.deepcopy(trace.model_dump())["steps"]
    mutate(raw)
    return STEPS.validate_python(raw), source


def assert_rejected(errors: list[str], needle: str):
    assert errors, "validator accepted a corrupted trace"
    assert any(needle in e for e in errors), f"expected {needle!r} in {errors}"


def test_clean_fixture_produces_no_errors():
    source, trace = load("array_aliasing")
    assert validate_trace(trace.steps, source) == []


def test_catches_broken_aliasing_via_dangling_reference():
    """The headline failure: `b` quietly stops pointing at the shared array."""

    def mutate(steps):
        steps[2]["stackFrames"][0]["variables"][1]["value"]["target"] = "obj_99"

    steps, source = corrupt("array_aliasing", mutate)
    assert_rejected(validate_trace(steps, source), "not on the heap")


def test_catches_duplicated_object_for_two_references():
    """Splitting one aliased object into two is the exact lie we must never render."""

    def mutate(steps):
        step = steps[1]
        clone = copy.deepcopy(step["heap"][0])
        step["heap"].append(clone)  # same id, twice

    steps, source = corrupt("reference_aliasing", mutate)
    assert_rejected(validate_trace(steps, source), "duplicate heap ids")


def test_catches_array_changing_length():
    def mutate(steps):
        steps[2]["heap"][0]["elements"].append(
            {"kind": "primitive", "type": "int", "value": 4}
        )

    steps, source = corrupt("array_aliasing", mutate)
    assert_rejected(validate_trace(steps, source), "fixed-length")


def test_catches_object_gaining_a_field():
    def mutate(steps):
        steps[2]["heap"][0]["fields"].append(
            {"name": "extra", "value": {"kind": "primitive", "type": "int", "value": 0}}
        )

    steps, source = corrupt("reference_aliasing", mutate)
    assert_rejected(validate_trace(steps, source), "do not gain or lose fields")


def test_catches_object_changing_type():
    def mutate(steps):
        steps[2]["heap"][0]["type"] = "OtherData"

    steps, source = corrupt("reference_aliasing", mutate)
    assert_rejected(validate_trace(steps, source), "type never changes")


def test_catches_stdout_being_rewritten():
    def mutate(steps):
        steps[-1]["stdout"] = ["999"]

    steps, source = corrupt("primitive_copy", mutate)
    assert_rejected(validate_trace(steps, source), "cumulative")


def test_catches_line_source_mismatch():
    def mutate(steps):
        steps[0]["source"] = "int totallyDifferent = 42;"

    steps, source = corrupt("primitive_copy", mutate)
    assert_rejected(validate_trace(steps, source), "does not match")


def test_catches_out_of_range_line():
    def mutate(steps):
        steps[0]["line"] = 999

    steps, source = corrupt("primitive_copy", mutate)
    assert_rejected(validate_trace(steps, source), "outside the source")


def test_catches_non_contiguous_step_numbers():
    def mutate(steps):
        steps[1]["step"] = 7

    steps, source = corrupt("primitive_copy", mutate)
    assert_rejected(validate_trace(steps, source), "contiguously")


def test_catches_changed_marker_pointing_at_nothing():
    def mutate(steps):
        steps[2]["changed"] = {"kind": "element", "id": "obj_1", "index": 99}

    steps, source = corrupt("array_aliasing", mutate)
    assert_rejected(validate_trace(steps, source), "out of bounds")


def test_catches_step_cap_overrun():
    source, trace = load("primitive_copy")
    raw = copy.deepcopy(trace.model_dump())["steps"]
    template = raw[0]
    long_trace = []
    for i in range(STEP_CAP + 5):
        step = copy.deepcopy(template)
        step["step"] = i + 1
        long_trace.append(step)
    errors = validate_trace(STEPS.validate_python(long_trace), source)
    assert_rejected(errors, "step cap")


# --- null references ------------------------------------------------------


NULL_SOURCE = """public class Main {
    public static void main(String[] args) {
        MyData a = null;
    }
}"""


def null_step(target):
    return {
        "step": 1,
        "line": 3,
        "source": "        MyData a = null;",
        "stackFrames": [
            {
                "name": "main",
                "variables": [
                    {"name": "a", "value": {"kind": "reference", "type": "MyData", "target": target}}
                ],
            }
        ],
        "heap": [],
        "stdout": [],
        "explanation": "a is declared but points at nothing.",
        "changed": {"kind": "variable", "frame": 0, "name": "a"},
    }


def test_null_reference_is_accepted_with_an_empty_heap():
    steps = STEPS.validate_python([null_step(None)])
    assert validate_trace(steps, NULL_SOURCE) == []


def test_non_null_reference_to_an_empty_heap_is_rejected():
    steps = STEPS.validate_python([null_step("obj_1")])
    assert_rejected(validate_trace(steps, NULL_SOURCE), "not on the heap")
