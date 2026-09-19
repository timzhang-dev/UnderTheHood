"""The prompt is text, so these tests pin the parts that can silently rot:
the worked example, the line numbering, and the repair message."""

from __future__ import annotations

from app.models.execution import STEP_CAP, TraceOk
from app.prompts.execution_trace import (
    EXAMPLE_SOURCE,
    EXAMPLE_TRACE,
    MAX_REPAIR_ERRORS,
    SYSTEM_PROMPT,
    UNSUPPORTED,
    build_repair_message,
    build_user_message,
    number_lines,
)
from app.services.validator import validate_trace
from tests.conftest import load


def test_worked_example_is_a_valid_trace():
    """If the schema or validator changes, the example in the prompt must not go stale."""
    trace = TraceOk.model_validate(EXAMPLE_TRACE)
    assert validate_trace(trace.steps, EXAMPLE_SOURCE) == []


def test_worked_example_teaches_reassignment_not_a_duplicate_object():
    trace = TraceOk.model_validate(EXAMPLE_TRACE)
    after_alias, after_reassign = trace.steps[1], trace.steps[2]
    assert len(after_alias.heap) == 1
    assert len(after_reassign.heap) == 2


def test_example_is_not_one_of_the_builtin_examples(fixture_names):
    """Otherwise the live eval would measure recall of the prompt, not generalisation."""
    for name in fixture_names:
        source, _ = load(name)
        assert source != EXAMPLE_SOURCE


def test_numbering_round_trips_to_the_original_lines():
    code = "class A {\n\n    int x;\n}\n"
    numbered = number_lines(code).split("\n")
    assert [row.split(" | ", 1)[1] for row in numbered] == code.split("\n")


def test_numbering_matches_every_fixture_line(fixture_names):
    """`line` in a trace is checked against source.split('\\n'); the numbers we show must agree."""
    for name in fixture_names:
        source, _ = load(name)
        for i, row in enumerate(number_lines(source).split("\n"), start=1):
            assert int(row.split("|", 1)[0]) == i


def test_numbering_pads_to_a_common_width():
    code = "\n".join(["x"] * 12)
    rows = number_lines(code).split("\n")
    assert rows[0].startswith(" 1 | ") and rows[11].startswith("12 | ")


def test_numbering_does_not_split_on_unicode_line_separators():
    """str.splitlines() would treat these as line breaks and desync from the validator."""
    code = "int a = 1;\x0c int b = 2;  int c = 3;"
    assert len(number_lines(code).split("\n")) == 1


def test_crlf_input_keeps_the_same_line_count():
    assert len(number_lines("a\r\nb\r\nc").split("\n")) == 3


def test_user_message_wraps_the_numbered_program():
    message = build_user_message("int x = 5;")
    assert "<program>\n1 | int x = 5;\n</program>" in message


def test_system_prompt_states_the_step_cap_and_every_unsupported_feature():
    assert f"{STEP_CAP} steps" in SYSTEM_PROMPT
    for feature in UNSUPPORTED:
        assert feature in SYSTEM_PROMPT


def test_repair_message_lists_every_error_verbatim():
    errors = ["step 2: a points to 'obj_9', which is not on the heap.", "step 3: stdout shrank."]
    message = build_repair_message(errors)
    for error in errors:
        assert error in message


def test_repair_message_is_bounded():
    errors = [f"error {i}" for i in range(MAX_REPAIR_ERRORS + 5)]
    message = build_repair_message(errors)
    assert f"error {MAX_REPAIR_ERRORS - 1}" in message
    assert f"error {MAX_REPAIR_ERRORS}" not in message
    assert "and 5 more" in message
