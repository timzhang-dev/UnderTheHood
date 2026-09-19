"""Execution trace schema — the contract between the LLM, the API, and the frontend.

Two conventions here are deliberate and worth reading before you change anything:

1. Field names are camelCase, not snake_case. This schema is a wire format, not a
   domain model: it is emitted by the LLM, validated here, and consumed by
   TypeScript. Naming the Python fields camelCase avoids an alias layer
   (populate_by_name / by_alias=True) whose only job would be to undo itself.

2. Every map is an ordered list of records — `heap` is a list of entries carrying
   their own `id`, not a dict keyed by id. Strict JSON Schema requires
   `additionalProperties: false`, which cannot coexist with user-data keys. Lists
   also give stable render ordering, so heap cards don't jump between steps.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# A trace longer than this is rejected rather than truncated. Loops are the only
# realistic way to reach it; see D6 in the architecture plan.
STEP_CAP = 60


class Strict(BaseModel):
    """Base model emitting `additionalProperties: false`, required for strict output."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Values
# --------------------------------------------------------------------------

# `String` is modelled as a primitive even though Java strings are references.
# Beginners reading the stack should see `name "Tim"`, not a hop into the heap.
# Documented simplification, not an oversight.
PrimitiveType = Literal[
    "int", "long", "short", "byte", "double", "float", "boolean", "char", "String"
]


class PrimitiveValue(Strict):
    kind: Literal["primitive"]
    type: PrimitiveType
    # bool is listed before int on purpose: bool is an int subclass, and without
    # this ordering `true` can round-trip as `1`.
    value: Union[bool, int, float, str]


class ReferenceValue(Strict):
    kind: Literal["reference"]
    type: str = Field(description='Declared type, e.g. "MyData" or "int[]".')
    target: str | None = Field(description="Heap entry id, or null for a null reference.")


# Non-recursive on purpose: an array element is a primitive or a reference, never
# another array inline. int[][] is out of scope, and MyData[] still works because
# each element is a reference into the heap. Keeping the union flat keeps the
# generated JSON Schema free of $ref cycles.
Value = Annotated[Union[PrimitiveValue, ReferenceValue], Field(discriminator="kind")]


# --------------------------------------------------------------------------
# Heap
# --------------------------------------------------------------------------


class ObjectField(Strict):
    name: str
    value: Value


class ObjectEntry(Strict):
    kind: Literal["object"]
    id: str = Field(description='Stable across every step, e.g. "obj_1".')
    type: str
    fields: list[ObjectField]


class ArrayEntry(Strict):
    kind: Literal["array"]
    id: str
    type: str = Field(description='Array type including brackets, e.g. "int[]".')
    elements: list[Value]


HeapEntry = Annotated[Union[ObjectEntry, ArrayEntry], Field(discriminator="kind")]


# --------------------------------------------------------------------------
# Stack
# --------------------------------------------------------------------------


class Variable(Strict):
    name: str
    value: Value


class Frame(Strict):
    name: str = Field(description='Method name, e.g. "main".')
    variables: list[Variable]


# --------------------------------------------------------------------------
# Change markers — drive the "flash what just changed" highlight in the UI
# --------------------------------------------------------------------------


class ChangedVariable(Strict):
    kind: Literal["variable"]
    frame: int = Field(description="Index into stackFrames.")
    name: str


class ChangedField(Strict):
    kind: Literal["field"]
    id: str
    field: str


class ChangedElement(Strict):
    kind: Literal["element"]
    id: str
    index: int


Changed = Annotated[
    Union[ChangedVariable, ChangedField, ChangedElement], Field(discriminator="kind")
]


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------


class Step(Strict):
    step: int = Field(description="1-based, contiguous.")
    line: int = Field(description="1-based line number in the submitted source.")
    source: str = Field(description="Echo of that source line; cross-checked by the validator.")
    # Index 0 is the bottom of the stack (main); the last entry is executing.
    stackFrames: list[Frame]
    heap: list[HeapEntry]
    # Cumulative, not per-step. The frontend renders step.stdout directly with no
    # accumulation logic, which keeps backward navigation a pure lookup.
    stdout: list[str]
    explanation: str
    changed: Changed | None = None


# --------------------------------------------------------------------------
# API envelope
# --------------------------------------------------------------------------


class TraceOk(Strict):
    status: Literal["ok"]
    steps: list[Step]


class TraceUnsupported(Strict):
    status: Literal["unsupported"]
    message: str
    unsupportedFeatures: list[str]


VisualizeResponse = Annotated[
    Union[TraceOk, TraceUnsupported], Field(discriminator="status")
]


class VisualizeRequest(Strict):
    language: Literal["java"] = "java"
    code: str
