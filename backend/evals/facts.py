"""Checkable facts about a trace, so the eval can grade structure without an LLM.

The real JVM supplies the expected stdout. What a JVM cannot tell us is what the
memory picture should look like ("a and b share one object here"), and that is the
whole product. A Fact states one such property; `check` returns None when it holds
or a short failure message, and `describe` is the same claim in plain English for the
review page.

Line semantics. "At line N" means the state shown by the step for line N, which is the
state AFTER that line finishes. If line N ran several times (a loop) the LAST such step
is used, so facts about a loop's effect are stated on the line after the loop or at
the end (line=None). A line with no step at all is itself a failure: it means the model
skipped something that ran.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.execution import Step, TraceOk


def _where(line: int | None) -> str:
    return "at the end" if line is None else f"after line {line}"


def _step_at(trace: TraceOk, line: int | None) -> tuple[Step | None, str]:
    if line is None:
        return trace.steps[-1], ""
    matches = [s for s in trace.steps if s.line == line]
    if not matches:
        return None, f"no step executes line {line}"
    return matches[-1], ""


def _same_value(actual, expected) -> bool:
    # bool is an int subclass: without this, a model emitting 1 for `true` would pass.
    if isinstance(actual, bool) or isinstance(expected, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual == expected
    return actual == expected


def _variable(step: Step, name: str):
    """Innermost frame first, so a callee's `n` wins over a caller's `n`."""
    for frame in reversed(step.stackFrames):
        for var in frame.variables:
            if var.name == name:
                return var.value
    return None


def _entry(step: Step, id_: str):
    return next((e for e in step.heap if e.id == id_), None)


def _reference(step: Step, name: str):
    """(value, None) for a reference variable, else (None, why not)."""
    value = _variable(step, name)
    if value is None:
        return None, f"variable {name!r} is not on the stack"
    if value.kind != "reference":
        return None, f"{name!r} is a primitive, not a reference"
    return value, None


def _object(step: Step, name: str):
    """(heap entry, None) that variable `name` points at, else (None, why not)."""
    ref, err = _reference(step, name)
    if err:
        return None, err
    if ref.target is None:
        return None, f"{name!r} is null"
    entry = _entry(step, ref.target)
    if entry is None:
        return None, f"{name!r} points at {ref.target}, which is not on the heap"
    return entry, None


def _field(entry, field: str):
    if entry.kind != "object":
        return None
    return next((f.value for f in entry.fields if f.name == field), None)


class _Fact:
    """Shared plumbing: subclasses implement `_check(step)` and `describe()`."""

    line: int | None

    def check(self, trace: TraceOk) -> str | None:
        step, err = _step_at(trace, self.line)
        if step is None:
            return err
        problem = self._check(step)
        return None if problem is None else f"{_where(self.line)}: {problem}"


@dataclass(frozen=True)
class Var(_Fact):
    """A primitive variable holds this value."""

    name: str
    value: object
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.name} = {self.value!r}"

    def _check(self, step):
        v = _variable(step, self.name)
        if v is None:
            return f"variable {self.name!r} is not on the stack"
        if v.kind != "primitive":
            return f"{self.name!r} is a reference, expected the value {self.value!r}"
        if not _same_value(v.value, self.value):
            return f"{self.name} is {v.value!r}, expected {self.value!r}"


@dataclass(frozen=True)
class Same(_Fact):
    """Two reference variables point at the same object (aliasing)."""

    a: str
    b: str
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.a} and {self.b} point at the SAME object"

    def _check(self, step):
        ra, err = _reference(step, self.a)
        rb, err2 = _reference(step, self.b)
        if err or err2:
            return err or err2
        if ra.target is None or ra.target != rb.target:
            return f"{self.a} -> {ra.target}, {self.b} -> {rb.target}; expected one shared object"


@dataclass(frozen=True)
class Different(_Fact):
    """Two reference variables point at different objects."""

    a: str
    b: str
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.a} and {self.b} point at DIFFERENT objects"

    def _check(self, step):
        ra, err = _reference(step, self.a)
        rb, err2 = _reference(step, self.b)
        if err or err2:
            return err or err2
        if ra.target is None or rb.target is None or ra.target == rb.target:
            return f"{self.a} -> {ra.target}, {self.b} -> {rb.target}; expected two distinct objects"


@dataclass(frozen=True)
class Null(_Fact):
    """A reference variable is null."""

    name: str
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.name} is null"

    def _check(self, step):
        ref, err = _reference(step, self.name)
        if err:
            return err
        if ref.target is not None:
            return f"{self.name} -> {ref.target}, expected null"


@dataclass(frozen=True)
class Heap(_Fact):
    """The heap holds exactly this many entries (objects and arrays)."""

    count: int
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, the heap holds exactly {self.count} object(s)"

    def _check(self, step):
        if len(step.heap) != self.count:
            return f"heap has {len(step.heap)} entries, expected {self.count}"


@dataclass(frozen=True)
class Field(_Fact):
    """A primitive field of the object a variable points at."""

    var: str
    field: str
    value: object
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.var}.{self.field} = {self.value!r}"

    def _check(self, step):
        entry, err = _object(step, self.var)
        if err:
            return err
        f = _field(entry, self.field)
        if f is None:
            return f"{entry.id} has no field {self.field!r}"
        if f.kind != "primitive" or not _same_value(f.value, self.value):
            return f"{self.var}.{self.field} is {getattr(f, 'value', f)!r}, expected {self.value!r}"


@dataclass(frozen=True)
class FieldNull(_Fact):
    """A reference field of the object a variable points at is null."""

    var: str
    field: str
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.var}.{self.field} is null"

    def _check(self, step):
        entry, err = _object(step, self.var)
        if err:
            return err
        f = _field(entry, self.field)
        if f is None or f.kind != "reference" or f.target is not None:
            return f"{self.var}.{self.field} is {f!r}, expected a null reference"


@dataclass(frozen=True)
class FieldRef(_Fact):
    """A reference field points at the same object another variable points at."""

    var: str
    field: str
    same_as: str
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.var}.{self.field} points at the same object as {self.same_as}"

    def _check(self, step):
        entry, err = _object(step, self.var)
        if err:
            return err
        other, err = _reference(step, self.same_as)
        if err:
            return err
        f = _field(entry, self.field)
        if f is None or f.kind != "reference" or f.target is None or f.target != other.target:
            return f"{self.var}.{self.field} is {f!r}, expected it to point at {other.target}"


@dataclass(frozen=True)
class Elem(_Fact):
    """A primitive array element."""

    var: str
    index: int
    value: object
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.var}[{self.index}] = {self.value!r}"

    def _check(self, step):
        entry, err = _object(step, self.var)
        if err:
            return err
        if entry.kind != "array" or not (0 <= self.index < len(entry.elements)):
            return f"{self.var} has no element {self.index}"
        e = entry.elements[self.index]
        if e.kind != "primitive" or not _same_value(e.value, self.value):
            return f"{self.var}[{self.index}] is {getattr(e, 'value', e)!r}, expected {self.value!r}"


@dataclass(frozen=True)
class ElemNull(_Fact):
    """An array element that holds a reference is null."""

    var: str
    index: int
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.var}[{self.index}] is null"

    def _check(self, step):
        entry, err = _object(step, self.var)
        if err:
            return err
        if entry.kind != "array" or not (0 <= self.index < len(entry.elements)):
            return f"{self.var} has no element {self.index}"
        e = entry.elements[self.index]
        if e.kind != "reference" or e.target is not None:
            return f"{self.var}[{self.index}] is {e!r}, expected a null reference"


@dataclass(frozen=True)
class ElemsSame(_Fact):
    """Two elements of one array point at the same object."""

    var: str
    i: int
    j: int
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, {self.var}[{self.i}] and {self.var}[{self.j}] point at the SAME object"

    def _check(self, step):
        entry, err = _object(step, self.var)
        if err:
            return err
        if entry.kind != "array" or max(self.i, self.j) >= len(entry.elements):
            return f"{self.var} has no elements {self.i} and {self.j}"
        a, b = entry.elements[self.i], entry.elements[self.j]
        if a.kind != "reference" or b.kind != "reference" or a.target is None or a.target != b.target:
            return f"{self.var}[{self.i}] -> {getattr(a, 'target', a)}, {self.var}[{self.j}] -> {getattr(b, 'target', b)}"


@dataclass(frozen=True)
class Frames(_Fact):
    """How many stack frames exist (2 = main plus one method call)."""

    count: int
    line: int | None = None

    def describe(self):
        return f"{_where(self.line)}, the stack has {self.count} frame(s)"

    def _check(self, step):
        if len(step.stackFrames) != self.count:
            return f"stack has {len(step.stackFrames)} frame(s), expected {self.count}"


@dataclass(frozen=True)
class Skipped:
    """This line never ran (the untaken branch, or code after a crash)."""

    line: int

    def describe(self):
        return f"line {self.line} never executes, so no step may show it"

    def check(self, trace: TraceOk) -> str | None:
        if any(s.line == self.line for s in trace.steps):
            return f"a step shows line {self.line}, which never runs"
