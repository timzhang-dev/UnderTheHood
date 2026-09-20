"""Grades one eval run. Deterministic: no model is involved in judging.

"Correct" is the product outcome the student experiences, judged against things a model
did not write: the real JVM's stdout, the semantic validator, and the structural facts
in cases.py. Two views of every run are graded:

  correct    the final answer, after the app's one repair retry
  first_try  the model's FIRST attempt alone, which is what prompt tuning moves

Their gap is the repair loop earning its keep. `refused` is its own metric so a refusal
is never summed with a capability failure, and an answer cut off at the token limit is
marked `truncated` and left out of the means rather than scored as wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.execution import TraceUnsupported, VisualizeResponse
from app.services.trace_generator import Generation
from app.services.validator import validate_trace
from evals.cases import Case


@dataclass
class Verdict:
    correct: bool
    reasons: list[str]


def _mentions_exception(text: str, exception: str) -> bool:
    """'NullPointerException' or 'null pointer' both count: the check is that it is named."""
    lowered = text.lower()
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", exception.removesuffix("Exception")).lower()
    return exception.lower() in lowered or words in lowered


def judge(case: Case, gold: dict | None, result: VisualizeResponse | None) -> Verdict:
    """Is this one answer right for this case?"""
    if result is None:
        return Verdict(False, ["no usable answer"])

    if case.expect == "unsupported":
        if isinstance(result, TraceUnsupported):
            return Verdict(True, [])
        return Verdict(False, ["traced a program that should have been declined"])

    if isinstance(result, TraceUnsupported):
        return Verdict(False, [f"declined a program that should be traced: {result.message[:120]}"])

    reasons = [f"validator: {e}" for e in validate_trace(result.steps, case.source)]
    if not result.steps:
        return Verdict(False, reasons)

    final = result.steps[-1]
    if gold is not None and final.stdout != gold["stdout"]:
        reasons.append(f"stdout {final.stdout} != real JVM output {gold['stdout']}")
    if case.expect == "exception":
        if final.line != case.fails_at_line:
            reasons.append(f"trace ends at line {final.line}, the program fails at line {case.fails_at_line}")
        if not _mentions_exception(final.explanation, case.exception):
            reasons.append(f"final explanation never names {case.exception}")
    for fact in case.facts:
        problem = fact.check(result)
        if problem:
            reasons.append(f"fact: {problem}")
    return Verdict(not reasons, reasons)


@dataclass
class GradedRun:
    grade: dict[str, float]
    explanation: dict[str, str]
    status: str  # "ok", or "truncated" when the model's output was cut off
    usage: dict[str, int]
    latency_s: float
    steps: int
    attempts: int
    model: str | None
    stop_reason: str | None
    unknown_usage_attempts: int  # attempts that were billed but returned nothing we could read


def usage_of(gen: Generation) -> dict[str, int]:
    """Billed token counts summed over every attempt that returned a readable answer."""
    total = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    for attempt in gen.attempts:
        if attempt.reply is None:
            continue
        for key in total:
            total[key] += getattr(attempt.reply.usage, key, 0) or 0
    return total


def grade_generation(case: Case, gold: dict | None, gen: Generation) -> GradedRun:
    final = judge(case, gold, gen.result)

    if gen.prechecked or not gen.attempts:
        first = final  # answered by a deterministic check, so there was no model attempt to differ
    else:
        opener = gen.attempts[0]
        first = judge(case, gold, opener.reply.result if opener.reply else None)

    unusable = [a.unusable for a in gen.attempts if a.unusable is not None]
    refused = any(u.kind == "refusal" for u in unusable)
    truncated = any(u.kind != "refusal" for u in unusable)

    replies = [a.reply for a in gen.attempts if a.reply is not None]
    last = replies[-1] if replies else None
    reasons = list(final.reasons)
    if refused:
        reasons.append("the model refused to answer")

    if truncated:  # excluded from the means: a clipped answer says nothing about correctness
        grade: dict[str, float] = {}
        status = "truncated"
    else:
        grade = {
            "correct": float(final.correct and not refused),
            "first_try": float(first.correct and not refused),
            "refused": float(refused),
        }
        status = "ok"

    return GradedRun(
        grade=grade,
        explanation={"correct": "; ".join(reasons) or "matches the JVM and every fact holds"},
        status=status,
        usage=usage_of(gen),
        latency_s=round(sum(a.latency_s for a in gen.attempts), 3),
        steps=0 if isinstance(gen.result, TraceUnsupported) else len(gen.result.steps),
        attempts=len(gen.attempts),
        model=last.model if last else None,
        stop_reason=last.stop_reason if last else None,
        unknown_usage_attempts=sum(1 for a in gen.attempts if a.reply is None),
    )
