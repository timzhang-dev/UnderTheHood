# Trace eval: what each number means

One flow: Java source in, a validated execution trace (or an honest decline) out, through
`app.services.trace_generator.generate`, the same function the API calls.

**Ground truth is not model-written.** Expected stdout, exceptions and compile errors come from
running each program on a real JVM (`backend/evals/gold.json`). The programs and the
memory-picture facts were written by Claude and reviewed by the project owner.

## Quality metrics (per case, 1 or 0)

- **correct** (headline). The final answer, after the app's single repair retry, is right:
  - *must trace*: the trace passes the semantic validator, its final stdout equals the JVM's,
    every structural fact in `cases.py` holds (aliasing, heap size, values), and for a crash the
    trace ends on the failing line and names the exception.
  - *must decline*: the answer is `unsupported`. A trace of it is wrong.
- **first try**. The same check applied to the model's first attempt alone. This is what prompt
  changes move. The gap `correct - first try` is the repair loop earning its keep.
- **refused** (lower is better). The model declined to answer at all. Kept separate so a
  refusal is never summed with a capability failure. A refused run counts as not correct.

## Tags

`tags[0]` is the category (core, secondary, limits, decline, adversarial). `tags[1]` is
`should-trace` or `should-decline`, used for the confusion metrics: recall on should-trace,
specificity on should-decline, and how many should-decline programs were traced anyway.

## Not scored

- **truncated**: the model's output was cut off at the token limit. Left out of every mean, and
  counted separately, because a clipped answer says nothing about correctness.
- **errors.jsonl**: attempts that never produced anything scorable (service error, timeout, a
  response served by a different model than requested, a harness bug). Never a zero.

## Perf fields

`latency_s` is the sum of every model attempt, i.e. what a student waits; backoff sleeps are
excluded. Token counts come from the API's `usage`, not estimates. A case answered by the free
precheck has no model call, so its usage and latency are legitimately empty.

## Not measured

Explanation quality (whether the prose is correct and beginner-friendly). It needs a human or a
calibrated judge and is out of scope for this eval.
