"""Java source -> a trace we are willing to show a student.

The flow is deliberately conservative, because a confident wrong trace is the one
failure this product cannot afford:

  1. cheap deterministic checks, so obviously unusable input never costs a model call
  2. ask the model
  3. run the semantic validator on its answer
  4. if it fails, ONE repair attempt with the validator's errors fed back
  5. still failing -> say we can't, rather than show a trace that might be wrong
"""

from __future__ import annotations

import logging
import re

import anthropic

from app.models.execution import TraceUnsupported, VisualizeResponse
from app.prompts.execution_trace import build_repair_message, build_user_message
from app.services.llm import UnusableOutput, ask
from app.services.validator import validate_trace

log = logging.getLogger(__name__)

# First attempt plus this many repairs. One is enough to fix a stray id or a
# miscounted line; more mostly burns money re-failing the same way.
MAX_REPAIRS = 1

# Bounds cost per request. Beginner programs are far smaller; the step cap limits
# the output side.
MAX_CODE_CHARS = 6000

# `void main(` rather than the full `public static void main(String[] args)`: a
# false accept just costs one model call (the prompt rejects it too), while a false
# reject would turn away a valid program.
_MAIN_METHOD = re.compile(r"\bvoid\s+main\s*\(")


def _unsupported(message: str, *features: str) -> TraceUnsupported:
    return TraceUnsupported(status="unsupported", message=message, unsupportedFeatures=list(features))


def precheck(code: str) -> TraceUnsupported | None:
    """Deterministic rejections that need no model. None means: go ahead."""
    if not code.strip():
        return _unsupported("Paste a Java program to visualize.", "empty input")
    if len(code) > MAX_CODE_CHARS:
        return _unsupported(
            f"This program is longer than ExplainMyCode can handle ({MAX_CODE_CHARS} characters). "
            "Try a shorter one, or start from one of the examples.",
            "program too long",
        )
    if not _MAIN_METHOD.search(code):
        return _unsupported(
            "ExplainMyCode needs a complete program, not just a few statements. Wrap your code in "
            "`public class Main { public static void main(String[] args) { ... } }`, "
            "or start from one of the examples.",
            "bare snippet (no main method)",
        )
    return None


def generate_trace(code: str, *, client: anthropic.Anthropic | None = None) -> VisualizeResponse:
    early = precheck(code)
    if early is not None:
        return early

    messages: list[dict] = [{"role": "user", "content": build_user_message(code)}]

    for attempt in range(1 + MAX_REPAIRS):
        try:
            reply = ask(messages, client=client)
        except UnusableOutput as exc:
            # No assistant text to echo back, and a retry would likely be cut off again.
            log.warning("attempt %d: unusable model output: %s", attempt + 1, exc)
            return _unsupported(
                "This program is too long or complicated for ExplainMyCode to trace. "
                "Try a shorter one, or start from one of the examples.",
                "trace too long",
            )

        result = reply.result
        if isinstance(result, TraceUnsupported):
            return result

        errors = validate_trace(result.steps, code)
        if not errors:
            return result

        log.warning("attempt %d: trace failed validation (%d errors): %s", attempt + 1, len(errors), errors[:3])
        # New list each time: nothing that already holds an earlier `messages` sees it change.
        messages = [
            *messages,
            {"role": "assistant", "content": reply.raw},
            {"role": "user", "content": build_repair_message(errors)},
        ]

    return _unsupported(
        "I couldn't produce a trace of this program that I trust, so I won't show one that might be wrong. "
        "Try simplifying it, or start from one of the examples."
    )
