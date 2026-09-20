"""Runs the trace eval through the app's real entry point and records every case.

  cd backend
  uv run python -m evals.run --dry-run                        # show the plan, call nothing
  uv run python -m evals.run --approve-harness                # a human records the harness hash once
  uv run --env-file .env python -m evals.run --only core_counter_repoint,decline_for_each
  uv run --env-file .env python -m evals.run --reps 2         # the full set, twice

Output (per variant) under .claude/hillclimb/tracing/<variant>/ in the layout the report
builder reads: results.jsonl (one row per case and rep, written as each finishes),
traces/<id>_rep<k>.json (the full conversation), errors.jsonl (attempts that never produced
something scorable). Failed attempts NEVER land in results.jsonl: a row there would be
scored as a wrong answer and would stop a resume from ever retrying it.

Properties this keeps on purpose, each one a way an eval quietly lies:
  - it calls app.services.trace_generator.generate, the same function the API uses
  - resume is idempotent at (case, rep), and rows are appended as cases complete
  - retryable service errors back off with jitter and the retry count is recorded
  - the model that served each response must be the one requested, or the attempt fails
  - the harness (this file, the grader, the cases, the gold) is hashed; a change refuses to
    run until a human re-approves with --approve-harness, so a tuning loop cannot quietly
    edit the yardstick
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
from pydantic import TypeAdapter

from app.models.execution import VisualizeResponse
from app.prompts.execution_trace import SYSTEM_PROMPT, build_repair_message, build_user_message
from app.services.llm import MODEL, TraceServiceError
from app.services.trace_generator import Generation, generate, precheck
from evals.build_gold import GOLD_PATH
from evals.cases import CASES, Case
from evals.grade import GradedRun, grade_generation, usage_of

BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_FLOW = BACKEND.parent / ".claude" / "hillclimb" / "tracing"
RESPONSE = TypeAdapter(VisualizeResponse)

MAX_RETRIES = 3
_SNAPSHOT = re.compile(r"^[-@](\d{8}|\d{4}-\d{2}-\d{2})$")


class CaseFailure(Exception):
    """An attempt that produced nothing scorable. Goes to errors.jsonl, never results.jsonl."""

    def __init__(self, failure_class: str, message: str, *, model: str | None = None, usage: dict | None = None):
        super().__init__(message)
        self.failure_class = failure_class
        self.model = model
        self.usage = usage


# --------------------------------------------------------------------------
# Small pure helpers (unit-tested)
# --------------------------------------------------------------------------


def served_ok(requested: str, served: str) -> bool:
    """The requested model, or a documented alias -> dated snapshot of it, and nothing else."""
    if served == requested:
        return True
    base = re.sub(r"-latest$|-0$", "", requested)
    return served.startswith(base) and bool(_SNAPSHOT.match(served[len(base):]))


def wilson(successes: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a pass rate. Honest at small n, unlike mean +/- sqrt(p(1-p)/n)."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def harness_sha(state: dict) -> str:
    files = {Path(__file__).resolve()}
    files.update((BACKEND / rel).resolve() for rel in state.get("harness_paths", []))
    digest = hashlib.sha256()
    for f in sorted(files):
        digest.update(os.path.relpath(f, BACKEND).encode() + b"\0")
        try:
            digest.update(f.read_bytes())
        except OSError:
            print(f"warning: harness file {f} is not readable; skipped", file=sys.stderr)
        digest.update(b"\0")
    return digest.hexdigest()


def check_harness(state_path: Path, state: dict, approve: bool) -> int | None:
    """None = approved and unchanged, go ahead. Otherwise the exit code to stop with.

    --approve-harness records the hash and STOPS. It never runs cases, so a human approving
    the harness cannot accidentally start a paid pass.
    """
    sha = harness_sha(state)
    if approve:
        state["harness_sha"] = sha
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        print(f"harness approved: sha256 {sha[:12]} recorded in {state_path.name}")
        return 0
    if state.get("harness_sha") == sha:
        return None
    if state.get("harness_sha") is None:
        print("No approved harness hash yet. Read the harness, then run once with --approve-harness.")
    else:
        print("The harness changed since it was approved. Review the change, then re-run with --approve-harness.")
    return 2


# --------------------------------------------------------------------------
# One case
# --------------------------------------------------------------------------


def _generate_with_backoff(case: Case, client, deadline: float, sleep) -> tuple[Generation, int]:
    """Runs the app; retries transient service errors with jittered exponential backoff."""
    retries, delay = 0, 2.0
    while True:
        try:
            return generate(case.source, client=client), retries
        except TraceServiceError as exc:
            out_of_time = time.monotonic() + delay > deadline
            if not exc.retryable or retries >= MAX_RETRIES or out_of_time:
                kind = "timeout" if exc.retryable and out_of_time else "service_error"
                raise CaseFailure(kind, str(exc)) from exc
            retries += 1
            sleep(delay + random.uniform(0, delay))
            delay *= 2


def _assert_served(model: str, gen: Generation) -> None:
    """A score from a substituted model measures nothing, so it must not be scored."""
    for attempt in gen.attempts:
        served = attempt.reply.model if attempt.reply else None
        if served and not served_ok(model, served):
            raise CaseFailure(
                "serving_substitution",
                f"served model {served} != requested {model}",
                model=served,
                usage=usage_of(gen),
            )


def _dump(result: VisualizeResponse) -> str:
    return RESPONSE.dump_json(result).decode()


def _transcript(case: Case, gen: Generation, graded: GradedRun) -> list[dict]:
    turns = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(case.source)},
    ]
    if gen.prechecked:
        turns.append({"role": "assistant", "content": "[answered by a deterministic check, no model call] " + _dump(gen.result)})
    for i, attempt in enumerate(gen.attempts):
        if i > 0:
            turns.append({"role": "user", "content": build_repair_message(gen.attempts[i - 1].validation_errors)})
        raw = attempt.reply.raw if attempt.reply else f"[no usable output: {attempt.unusable}]"
        turns.append({"role": "assistant", "content": raw})
    last = gen.attempts[-1] if gen.attempts else None
    if last is not None and (last.reply is None or last.reply.result is not gen.result):
        turns.append({"role": "assistant", "content": "[final answer shown to the student] " + _dump(gen.result)})
    verdict = ", ".join(f"{k}={v:g}" for k, v in graded.grade.items()) or f"status={graded.status}"
    turns.append({"role": "assistant", "content": f"[grader] {verdict}: {graded.explanation['correct']}"})
    return turns


def _row(case: Case, rep: int, gen: Generation, graded: GradedRun, retries: int) -> dict:
    row = {
        "prompt_id": case.id,
        "rep": rep,
        "prompt": case.source,
        "tags": [case.category, "should-decline" if case.expect == "unsupported" else "should-trace"],
        "meta": {
            "prechecked": gen.prechecked,
            "retries": retries,
            "unknown_usage_attempts": graded.unknown_usage_attempts,
            "attempt_latencies_s": [round(a.latency_s, 3) for a in gen.attempts],
        },
        "model": graded.model,
        "usage": graded.usage,
        "stop_reason": graded.stop_reason,
        "latency_s": graded.latency_s,
        "attempts": graded.attempts,
        "steps": graded.steps,
        "grade": graded.grade,
        "explanation": graded.explanation,
    }
    if graded.status != "ok":
        row["status"] = graded.status
    return row


# --------------------------------------------------------------------------
# The whole run
# --------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # a torn final line from a crash; the case simply reruns
    return rows


def _heal(path: Path) -> None:
    """A crash can leave a final line with no newline; appending would merge two rows into one."""
    if path.exists() and path.read_bytes()[-1:] not in (b"", b"\n"):
        with path.open("a") as f:
            f.write("\n")


def run_eval(
    *,
    cases: list[Case],
    gold: dict,
    client,
    flow: Path,
    variant: str = "baseline",
    model: str = MODEL,
    reps: int = 1,
    concurrency: int = 4,
    timeout_s: float = 300.0,
    sleep=time.sleep,
    out=print,
) -> dict:
    vdir = flow / variant
    (vdir / "traces").mkdir(parents=True, exist_ok=True)
    results_path, errors_path = vdir / "results.jsonl", vdir / "errors.jsonl"
    _heal(results_path)
    _heal(errors_path)

    done = {(r["prompt_id"], r["rep"]) for r in _read_jsonl(results_path)}
    tasks = [(c, rep) for c in cases for rep in range(reps) if (c.id, rep) not in done]
    out(f"{len(tasks)} to run, {len(done)} already done, {len(cases) * reps} planned in total")

    lock = threading.Lock()
    counts = {"ok": 0, "failed": 0}

    def append(path: Path, obj: dict) -> None:
        with lock, path.open("a") as f:
            f.write(json.dumps(obj) + "\n")

    def work(task) -> None:
        case, rep = task
        started = time.monotonic()
        try:
            gen, retries = _generate_with_backoff(case, client, started + timeout_s, sleep)
            _assert_served(model, gen)
            graded = grade_generation(case, gold.get(case.id), gen)
            append(results_path, _row(case, rep, gen, graded, retries))
            (vdir / "traces" / f"{case.id}_rep{rep}.json").write_text(
                json.dumps(_transcript(case, gen, graded), indent=2)
            )
            counts["ok"] += 1
            mark = "ok " if graded.grade.get("correct") == 1.0 else ("---" if graded.status != "ok" else "BAD")
            out(f"  {mark} {case.id} rep{rep}  {graded.latency_s:>6.1f}s  attempts={graded.attempts}")
        except CaseFailure as exc:
            counts["failed"] += 1
            append(errors_path, {
                "prompt_id": case.id, "rep": rep, "failure_class": exc.failure_class, "error": str(exc),
                "model": exc.model, "usage": exc.usage, "latency_s": round(time.monotonic() - started, 3),
            })
            out(f"  FAILED {case.id} rep{rep}: {exc.failure_class}: {exc}")
        except Exception as exc:  # noqa: BLE001 - a harness bug must not take down the whole pass
            counts["failed"] += 1
            append(errors_path, {
                "prompt_id": case.id, "rep": rep, "failure_class": "harness_error", "error": repr(exc),
                "latency_s": round(time.monotonic() - started, 3),
            })
            traceback.print_exc()
            out(f"  FAILED {case.id} rep{rep}: harness_error: {exc!r}")

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(work, tasks))

    return summarize(_read_jsonl(results_path), _read_jsonl(errors_path), model)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

# Per million tokens, from the Claude API model table: cache writes cost 1.25x input, reads 0.1x.
PRICES = {"claude-opus-5": {"in": 5.0, "out": 25.0}}


def cost_usd(usage: dict, model: str | None) -> float:
    price = PRICES.get(model or "")
    if price is None:
        return 0.0
    per_in = price["in"] / 1e6
    return (
        usage.get("input_tokens", 0) * per_in
        + usage.get("cache_creation_input_tokens", 0) * per_in * 1.25
        + usage.get("cache_read_input_tokens", 0) * per_in * 0.1
        + usage.get("output_tokens", 0) * price["out"] / 1e6
    )


def summarize(rows: list[dict], errors: list[dict], model: str) -> dict:
    scored = [r for r in rows if r.get("status", "ok") == "ok"]
    n = len(scored)
    correct = sum(r["grade"]["correct"] for r in scored)
    lo, hi = wilson(correct, n)

    def mean(key: str, subset: list[dict]) -> float | None:
        return sum(r["grade"][key] for r in subset) / len(subset) if subset else None

    positives = [r for r in scored if "should-trace" in r["tags"]]
    negatives = [r for r in scored if "should-decline" in r["tags"]]
    traced = [r for r in scored if r.get("steps", 0) > 0]
    categories: dict[str, list[dict]] = {}
    for r in scored:
        categories.setdefault(r["tags"][0], []).append(r)

    model_rows = [r for r in rows if r.get("model")]
    attempts_latency = [r["latency_s"] for r in rows if r.get("attempts")]
    error_classes: dict[str, int] = {}
    for e in errors:
        error_classes[e["failure_class"]] = error_classes.get(e["failure_class"], 0) + 1

    return {
        "model": model,
        "rows": len(rows),
        "scored": n,
        "truncated": sum(1 for r in rows if r.get("status") == "truncated"),
        "refused": int(sum(r["grade"].get("refused", 0) for r in scored)),
        "errors": error_classes,
        "correct": (correct, n, lo, hi),
        "first_try": mean("first_try", scored),
        "rescued_by_repair": sum(1 for r in scored if r["grade"]["correct"] == 1 and r["grade"]["first_try"] == 0),
        "spoiled_by_repair": sum(1 for r in scored if r["grade"]["correct"] == 0 and r["grade"]["first_try"] == 1),
        "recall_should_trace": mean("correct", positives),
        "specificity_should_decline": mean("correct", negatives),
        "traced_should_decline": sum(1 for r in traced if "should-decline" in r["tags"]),
        "precision_of_tracing": (
            sum(1 for r in traced if "should-trace" in r["tags"]) / len(traced) if traced else None
        ),
        "by_category": {k: (int(sum(r["grade"]["correct"] for r in v)), len(v)) for k, v in categories.items()},
        "latency_mean_s": sum(attempts_latency) / len(attempts_latency) if attempts_latency else None,
        "latency_max_s": max(attempts_latency, default=None),
        "tokens": {
            k: sum(r["usage"].get(k, 0) for r in model_rows)
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        },
        "cost_usd": sum(cost_usd(r["usage"], r["model"]) for r in model_rows),
        "cost_per_model_case_usd": (
            sum(cost_usd(r["usage"], r["model"]) for r in model_rows) / len(model_rows) if model_rows else None
        ),
        "unknown_usage_attempts": sum(r["meta"].get("unknown_usage_attempts", 0) for r in rows),
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def print_summary(s: dict, out=print) -> None:
    k, n, lo, hi = s["correct"]
    out("")
    out(f"correct       {k:g}/{n} = {_pct(k / n if n else None)}   (95% CI {lo:.0%} to {hi:.0%})")
    out(f"first try     {_pct(s['first_try'])}   repair rescued {s['rescued_by_repair']}, repair spoiled {s['spoiled_by_repair']}")
    out(
        f"should-trace  recall {_pct(s['recall_should_trace'])}   "
        f"should-decline specificity {_pct(s['specificity_should_decline'])}   "
        f"traced-when-it-should-decline: {s['traced_should_decline']}   precision {_pct(s['precision_of_tracing'])}"
    )
    out("by category  " + "   ".join(f"{c} {ok}/{tot}" for c, (ok, tot) in s["by_category"].items()))
    if s["latency_mean_s"] is not None:
        out(f"latency       mean {s['latency_mean_s']:.1f}s   max {s['latency_max_s']:.1f}s  (sum of attempts, what a student waits)")
    t = s["tokens"]
    out(
        f"tokens        in {t['input_tokens']:,}  out {t['output_tokens']:,}  "
        f"cache-write {t['cache_creation_input_tokens']:,}  cache-read {t['cache_read_input_tokens']:,}"
    )
    per = s["cost_per_model_case_usd"]
    out(f"cost          ${s['cost_usd']:.3f} total" + (f", ${per:.3f} per case that reached the model" if per else ""))
    if s["truncated"] or s["refused"] or s["errors"] or s["unknown_usage_attempts"]:
        out(
            f"NOT SCORED    truncated {s['truncated']} (left out of the means), refused {s['refused']}, "
            f"errors {s['errors'] or 0}, billed-but-unreadable attempts {s['unknown_usage_attempts']}"
        )


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--flow", default=str(DEFAULT_FLOW))
    parser.add_argument("--variant", default="baseline", help="baseline, v1, v2, ... (the report requires these names)")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-s", type=float, default=300.0, help="ceiling on backoff and retries per case")
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--dry-run", action="store_true", help="print the plan; call nothing")
    parser.add_argument("--approve-harness", action="store_true", help="record the harness hash and stop")
    args = parser.parse_args(argv)
    if args.reps < 1 or args.concurrency < 1:
        parser.error("--reps and --concurrency must be at least 1")

    cases = CASES
    if args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
        unknown = [w for w in wanted if w not in {c.id for c in CASES}]
        if unknown:
            parser.error(f"unknown case id(s): {', '.join(unknown)}")
        cases = [c for c in CASES if c.id in wanted]

    flow = Path(args.flow)
    if args.dry_run:
        free = [c.id for c in cases if precheck(c.source) is not None]
        calls = len(cases) - len(free)
        print(f"{len(cases)} cases x {args.reps} rep(s) on {args.model}, concurrency {args.concurrency}")
        print(f"{calls} case(s) reach the model (1 call each, 2 if the repair retry fires); {len(free)} answered free: {free}")
        return 0

    state_path = flow / "_state.json"
    if not state_path.exists():
        print(f"missing {state_path}", file=sys.stderr)
        return 2
    state = json.loads(state_path.read_text())
    stop = check_harness(state_path, state, args.approve_harness)
    if stop is not None:
        return stop

    client = anthropic.Anthropic(timeout=120.0, max_retries=0)  # retries are ours, so they are visible
    gold = json.loads(GOLD_PATH.read_text())
    summary = run_eval(
        cases=cases, gold=gold, client=client, flow=flow, variant=args.variant, model=args.model,
        reps=args.reps, concurrency=args.concurrency, timeout_s=args.timeout_s,
    )
    print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
