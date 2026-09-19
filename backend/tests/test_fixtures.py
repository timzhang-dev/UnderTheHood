"""The §13 test matrix, asserted against the golden fixtures.

These are the invariants that define correct Java reference semantics. If one of
these breaks, the product is teaching something false.
"""

from __future__ import annotations

import pytest

from app.services.validator import validate_trace
from tests.conftest import heap, load, var


def test_all_fixtures_pass_the_validator(fixture_names):
    assert fixture_names, "no fixtures found — run scripts/build_fixtures.py"
    for name in fixture_names:
        source, trace = load(name)
        assert validate_trace(trace.steps, source) == [], f"{name} failed validation"


# --- primitives -----------------------------------------------------------


def test_primitive_assignment_copies_the_value():
    _, trace = load("primitive_copy")
    after_copy = trace.steps[1]  # int y = x;
    assert var(after_copy, "x").value == 5
    assert var(after_copy, "y").value == 5


def test_primitive_reassignment_leaves_the_source_untouched():
    _, trace = load("primitive_copy")
    after_reassign = trace.steps[2]  # y = 10;
    assert var(after_reassign, "y").value == 10
    assert var(after_reassign, "x").value == 5, "reassigning y must not touch x"


def test_primitives_never_touch_the_heap():
    _, trace = load("primitive_copy")
    assert all(step.heap == [] for step in trace.steps)


# --- single object reference ---------------------------------------------


def test_one_object_reference():
    _, trace = load("reference_aliasing")
    first = trace.steps[0]  # MyData a = new MyData(1);
    a = var(first, "a")
    assert a.kind == "reference"
    assert len(first.heap) == 1
    assert heap(first, a.target).type == "MyData"


# --- aliasing: the core lesson -------------------------------------------


def test_two_references_to_the_same_object():
    _, trace = load("reference_aliasing")
    after_alias = trace.steps[1]  # MyData b = a;
    assert var(after_alias, "a").target == var(after_alias, "b").target
    assert len(after_alias.heap) == 1, "aliasing must not duplicate the object"


def test_object_field_mutation_is_visible_through_both_references():
    source, trace = load("reference_aliasing")
    after_mutation = trace.steps[2]  # b.value = 5;
    a = var(after_mutation, "a")
    b = var(after_mutation, "b")
    assert a.target == b.target
    fields = {f.name: f.value.value for f in heap(after_mutation, a.target).fields}
    assert fields["value"] == 5
    assert trace.steps[-1].stdout == ["5"], "a.value must print 5, not 1"


def test_two_references_to_different_objects():
    _, trace = load("independent_objects")
    after_second_new = trace.steps[1]  # MyData b = new MyData(1);
    a, b = var(after_second_new, "a"), var(after_second_new, "b")
    assert a.target != b.target, "two `new` calls must produce two distinct ids"
    assert len(after_second_new.heap) == 2

    final = trace.steps[-1]
    a_fields = {f.name: f.value.value for f in heap(final, var(final, "a").target).fields}
    assert a_fields["value"] == 1, "mutating b must not affect the independent a"
    assert final.stdout == ["1"]


# --- arrays ---------------------------------------------------------------


def test_array_creation_puts_the_array_on_the_heap():
    _, trace = load("array_aliasing")
    first = trace.steps[0]
    a = var(first, "a")
    assert a.kind == "reference" and a.type == "int[]"
    entry = heap(first, a.target)
    assert entry.kind == "array"
    assert [e.value for e in entry.elements] == [1, 2, 3]


def test_array_aliasing_shares_one_array():
    """§13: after `int[] b = a`, assert a.target === b.target."""
    _, trace = load("array_aliasing")
    after_alias = trace.steps[1]
    assert var(after_alias, "a").target == var(after_alias, "b").target
    assert len(after_alias.heap) == 1


def test_array_mutation_through_the_alias():
    """§13: after `b[0] = 10`, assert heap[a.target].elements[0].value === 10."""
    _, trace = load("array_aliasing")
    after_mutation = trace.steps[2]
    a = var(after_mutation, "a")
    assert heap(after_mutation, a.target).elements[0].value == 10
    assert trace.steps[-1].stdout == ["10"], "a[0] must print 10"


# --- stdout ---------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("primitive_copy", ["5", "10"]),
        ("reference_aliasing", ["5"]),
        ("array_aliasing", ["10"]),
        ("independent_objects", ["1"]),
    ],
)
def test_stdout_tracking(name, expected):
    _, trace = load(name)
    assert trace.steps[-1].stdout == expected


def test_stdout_is_cumulative_and_only_grows(fixture_names):
    for name in fixture_names:
        _, trace = load(name)
        for earlier, later in zip(trace.steps, trace.steps[1:]):
            assert later.stdout[: len(earlier.stdout)] == earlier.stdout


# --- line mapping ---------------------------------------------------------


def test_every_step_points_at_a_real_source_line(fixture_names):
    for name in fixture_names:
        source, trace = load(name)
        lines = source.split("\n")
        for step in trace.steps:
            assert step.source.strip() == lines[step.line - 1].strip()
            assert step.source.strip(), f"{name} step {step.step} highlights a blank line"
