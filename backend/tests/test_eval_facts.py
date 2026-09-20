"""The eval's checks must be able to fail. Each fact is tried on a trace where it holds
and on one where it must not, using the golden fixtures as known-correct traces."""

from __future__ import annotations

from app.models.execution import TraceOk
from evals.facts import (
    Different, Elem, ElemNull, ElemsSame, Field, FieldNull, FieldRef, Frames, Heap, Null, Same, Skipped, Var,
    _same_value,
)
from tests.conftest import load


def passes(fact, trace) -> bool:
    return fact.check(trace) is None


# --- reference_aliasing: 11 a=new  12 b=a  14 b.value=5  16 println ---------------


def test_aliasing_facts_hold_on_the_correct_trace_and_fail_on_the_wrong_claim():
    _, t = load("reference_aliasing")
    assert passes(Same("a", "b", 12), t)
    assert passes(Heap(1, 12), t)
    assert not passes(Different("a", "b", 12), t)
    assert not passes(Heap(2, 12), t)


def test_a_variable_that_does_not_exist_yet_is_a_failure_not_a_crash():
    _, t = load("reference_aliasing")
    assert "not on the stack" in Same("a", "b", 11).check(t)


def test_field_facts():
    _, t = load("reference_aliasing")
    assert passes(Field("a", "value", 5, 14), t)  # visible through the alias
    assert not passes(Field("a", "value", 1, 14), t)
    assert "no field" in Field("a", "nope", 1, 14).check(t)


def test_final_state_is_the_default_when_no_line_is_given():
    _, t = load("reference_aliasing")
    assert passes(Field("a", "value", 5), t)


# --- independent_objects: 12 b=new -> two objects -------------------------------


def test_different_objects():
    _, t = load("independent_objects")
    assert passes(Different("a", "b", 12), t)
    assert not passes(Same("a", "b", 12), t)
    assert passes(Heap(2, 12), t)


# --- array_aliasing: 4 b=a  6 b[0]=10 --------------------------------------------


def test_array_elements():
    _, t = load("array_aliasing")
    assert passes(Elem("a", 0, 10, 6), t)
    assert not passes(Elem("a", 0, 1, 6), t)
    assert "no element" in Elem("a", 9, 1, 6).check(t)
    assert "expected a null reference" in ElemNull("a", 0, 6).check(t)


# --- primitives and the traps in comparing values -----------------------------------


def test_primitive_var_and_the_missing_line_case():
    _, t = load("primitive_copy")
    assert passes(Var("y", 10, 5), t)
    assert not passes(Var("y", 5, 5), t)
    assert "no step executes line 99" in Var("x", 5, 99).check(t)


def test_bool_and_int_are_never_confused():
    """True == 1 in Python. A model emitting 1 for `true` must not pass."""
    assert not _same_value(True, 1)
    assert not _same_value(1, True)
    assert _same_value(True, True)
    assert _same_value(3, 3.0)  # a double shown as 3 is still the value 3
    assert not _same_value("3", 3)


def test_a_primitive_is_not_accepted_where_a_reference_is_expected_and_vice_versa():
    _, t = load("primitive_copy")
    assert "primitive, not a reference" in Same("x", "y", 5).check(t)
    _, r = load("reference_aliasing")
    assert "is a reference" in Var("a", 1, 12).check(r)


def test_a_line_that_ran_twice_is_judged_by_its_last_step():
    _, t = load("primitive_copy")
    later = t.model_copy(deep=True)
    dup = later.steps[0].model_copy(deep=True)
    dup.stackFrames[0].variables[0].value.value = 99
    later.steps.append(dup)  # line 3 again, with x = 99
    assert passes(Var("x", 99, 3), later)
    assert not passes(Var("x", 5, 3), later)


def test_skipped_line():
    _, t = load("primitive_copy")  # runs 3,4,5,7,8
    assert passes(Skipped(6), t)
    assert "never runs" in Skipped(3).check(t)


# --- frames -------------------------------------------------------------------------


def test_frames_count_and_innermost_variable_wins():
    _, t = load("primitive_copy")
    deeper = t.model_copy(deep=True)
    step = deeper.steps[2]  # line 5
    step.stackFrames.append(step.stackFrames[0].model_copy(deep=True, update={"name": "callee"}))
    step.stackFrames[1].variables[1].value.value = 777  # callee's y
    assert passes(Frames(2, 5), deeper)
    assert not passes(Frames(1, 5), deeper)
    assert passes(Var("y", 777, 5), deeper)  # callee's y shadows main's


# --- null, field/element references: one hand-built step ---------------------------------


def _handbuilt() -> TraceOk:
    def ref(t, target):
        return {"kind": "reference", "type": t, "target": target}

    step = {
        "step": 1, "line": 1, "source": "x", "explanation": "e", "changed": None, "stdout": [],
        "stackFrames": [{"name": "main", "variables": [
            {"name": "a", "value": ref("Node", "obj_1")},
            {"name": "b", "value": ref("Node", "obj_2")},
            {"name": "arr", "value": ref("Node[]", "obj_3")},
            {"name": "nothing", "value": ref("Node", None)},
        ]}],
        "heap": [
            {"kind": "object", "id": "obj_1", "type": "Node", "fields": [{"name": "next", "value": ref("Node", "obj_2")}]},
            {"kind": "object", "id": "obj_2", "type": "Node", "fields": [{"name": "next", "value": ref("Node", None)}]},
            {"kind": "array", "id": "obj_3", "type": "Node[]",
             "elements": [ref("Node", "obj_2"), ref("Node", "obj_2"), ref("Node", None)]},
        ],
    }
    return TraceOk.model_validate({"status": "ok", "steps": [step]})


def test_null_and_reference_valued_facts():
    t = _handbuilt()
    assert passes(Null("nothing"), t) and not passes(Null("a"), t)
    assert passes(FieldRef("a", "next", "b"), t) and not passes(FieldRef("b", "next", "a"), t)
    assert passes(FieldNull("b", "next"), t) and not passes(FieldNull("a", "next"), t)
    assert passes(ElemsSame("arr", 0, 1), t) and not passes(ElemsSame("arr", 0, 2), t)
    assert passes(ElemNull("arr", 2), t) and not passes(ElemNull("arr", 0), t)
    assert "is null" in Field("nothing", "next", 1).check(t)
