from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.models.execution import TraceOk, VisualizeResponse

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
RESPONSE = TypeAdapter(VisualizeResponse)


def load(name: str) -> tuple[str, TraceOk]:
    """Returns (source, trace) for a golden fixture."""
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    trace = RESPONSE.validate_python(data["trace"])
    assert isinstance(trace, TraceOk)
    return data["source"], trace


def var(step, name: str, frame: int = 0):
    """The value of a named variable in a stack frame."""
    return next(v.value for v in step.stackFrames[frame].variables if v.name == name)


def heap(step, id_: str):
    return next(e for e in step.heap if e.id == id_)


@pytest.fixture(scope="session")
def fixture_names() -> list[str]:
    return sorted(p.stem for p in FIXTURES.glob("*.json"))
