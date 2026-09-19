"""Manual harness: run a Java program through the real prompt and model.

This is the dev loop for tuning app/prompts/execution_trace.py. It calls the live
API, so every run costs a little money. The built-in examples are the cheap
sanity check; your own snippets are the real test.

  uv run --env-file .env python scripts/try_prompt.py --example array_aliasing
  uv run --env-file .env python scripts/try_prompt.py --all-examples
  uv run --env-file .env python scripts/try_prompt.py --file Foo.java --out /tmp/foo.json
  uv run python scripts/try_prompt.py --example reference_aliasing --dry-run

Credentials: copy .env.example to .env and set ANTHROPIC_API_KEY. Nothing here loads
.env by itself; `--env-file .env` is what makes uv do it. --dry-run and --replay
need no key.

For a built-in example the model's trace is also compared with the hand-authored
golden trace. Only state is compared (line, stack, heap, stdout); explanations are
prose and are expected to differ.

--replay analyses a saved trace instead of calling the API. It lets you re-inspect
a run made earlier with --out, and it makes the reporting testable for free.

Two output shapes, because the spike never answered whether the model can return
`unsupported` at all:

  --shape wrapped   asks for {"result": <ok | unsupported>} (default)
  --shape ok        asks for a bare TraceOk, as the spike did; cannot express
                    `unsupported`

If the API rejects `wrapped`, fall back to `ok`. The worked example in the prompt
shows the bare shape, so if `wrapped` wins, update the example to match.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic
from pydantic import TypeAdapter

from app.models.execution import Strict, TraceOk, TraceUnsupported, VisualizeResponse
from app.prompts.execution_trace import SYSTEM_PROMPT, build_user_message
from app.services.validator import validate_trace

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
RESPONSE = TypeAdapter(VisualizeResponse)

# Thinking tokens count against this, and a trace near STEP_CAP is large. If a long
# program dies here, that is a finding about the cap, not a bug in the harness.
MAX_TOKENS = 16000

# State that must match the golden trace. `source` is derived from `line`, and
# `explanation` / `changed` are judgement calls, so none of those are compared.
STATE_FIELDS = ("line", "stackFrames", "heap", "stdout")


class Envelope(Strict):
    """Wraps the union in an object: a bare union at the schema root may be rejected."""

    result: VisualizeResponse


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_example(name: str) -> tuple[str, TraceOk]:
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    trace = RESPONSE.validate_python(data["trace"])
    assert isinstance(trace, TraceOk)
    return data["source"], trace


def load_replay(path: str) -> TraceOk | TraceUnsupported:
    data = json.loads(Path(path).read_text())
    # Accept a whole fixture file as well as a trace saved with --out.
    return RESPONSE.validate_python(data.get("trace", data))


# --------------------------------------------------------------------------
# The model call
# --------------------------------------------------------------------------


def ask_model(client: anthropic.Anthropic, model: str, source: str, shape: str):
    """Returns a TraceOk / TraceUnsupported, or None if the call did not produce one."""
    output_format = Envelope if shape == "wrapped" else TraceOk
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            # cache_control makes the cache counters below meaningful: run the same
            # command twice within five minutes and cache_read should be non-zero.
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": build_user_message(source)}],
            output_format=output_format,
        )
    except anthropic.BadRequestError as exc:
        print(f"REJECTED by the API (400): {exc.message}")
        if shape == "wrapped":
            print("-> The wrapped shape may be the problem. Retry with --shape ok.")
        else:
            print("-> The trace schema itself was rejected; see the fallback in spike_structured_output.py.")
        return None
    except anthropic.AuthenticationError:
        print("Authentication failed. Set ANTHROPIC_API_KEY, or run `ant auth login`.")
        return None
    except anthropic.RateLimitError:
        print("Rate limited. Wait a moment and retry.")
        return None
    except anthropic.APIStatusError as exc:
        print(f"API error ({exc.status_code}): {exc.message}")
        return None
    except anthropic.APIConnectionError:
        print("Network error reaching the API.")
        return None
    except TypeError as exc:
        # With no credential at all the SDK raises a bare TypeError, not AuthenticationError.
        if "authentication" not in str(exc).lower():
            raise
        print(
            "No credentials found. Put ANTHROPIC_API_KEY in backend/.env and run with "
            "`uv run --env-file .env ...`, or run `ant auth login`."
        )
        return None
    except Exception as exc:  # noqa: BLE001 - last resort for a dev script
        # Most likely the SDK failing to parse output that was cut off at max_tokens.
        print(f"{type(exc).__name__}: {exc}")
        print(f"-> If the program is long, the output may have hit max_tokens ({MAX_TOKENS}).")
        return None

    u = response.usage
    print(
        f"request {response._request_id}  stop_reason={response.stop_reason}\n"
        f"tokens: in={u.input_tokens} out={u.output_tokens} "
        f"cache_write={u.cache_creation_input_tokens} cache_read={u.cache_read_input_tokens}"
    )
    if response.parsed_output is None:
        print(f"No parsed output (stop_reason={response.stop_reason}).")
        return None
    return response.parsed_output.result if shape == "wrapped" else response.parsed_output


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def _value(v) -> str:
    if v.kind == "reference":
        return f"→{v.target}" if v.target else "null"
    return json.dumps(v.value)


def _heap_entry(e) -> str:
    if e.kind == "array":
        return f"{e.id} {e.type} [{', '.join(_value(x) for x in e.elements)}]"
    fields = ", ".join(f"{f.name}={_value(f.value)}" for f in e.fields)
    return f"{e.id} {e.type} {{{fields}}}"


def _changed(c) -> str:
    if c is None:
        return "-"
    if c.kind == "variable":
        return f"variable {c.name} (frame {c.frame})"
    if c.kind == "field":
        return f"field {c.id}.{c.field}"
    return f"element {c.id}[{c.index}]"


def print_trace(trace: TraceOk) -> None:
    for s in trace.steps:
        frames = " | ".join(
            f"{f.name}: " + (", ".join(f"{v.name}={_value(v.value)}" for v in f.variables) or "(empty)")
            for f in s.stackFrames
        )
        print(f"{s.step:>3}  L{s.line:<3} {s.source.strip()}")
        print(f"       stack  {frames}")
        print(f"       heap   {'; '.join(_heap_entry(e) for e in s.heap) or '(empty)'}")
        print(f"       stdout {s.stdout}")
        print(f"       marked {_changed(s.changed)}")
        print(f"       why    {s.explanation}")


def diff_states(got: TraceOk, golden: TraceOk) -> list[str]:
    diffs = []
    if len(got.steps) != len(golden.steps):
        diffs.append(f"{len(got.steps)} steps, golden has {len(golden.steps)}")
    for mine, theirs in zip(got.steps, golden.steps):
        wrong = [f for f in STATE_FIELDS if getattr(mine, f) != getattr(theirs, f)]
        if wrong:
            diffs.append(f"step {theirs.step}: {', '.join(wrong)} differ from golden")
    return diffs


def analyse(source: str, result: TraceOk | TraceUnsupported, golden: TraceOk | None) -> bool:
    """Prints the report. True means: well-formed, validator-clean, and matches golden."""
    if isinstance(result, TraceUnsupported):
        print(f"UNSUPPORTED: {result.message}")
        print(f"  features: {result.unsupportedFeatures}")
        # Refusing a built-in example is a failure; refusing anything else is a valid answer.
        return golden is None

    print_trace(result)
    errors = validate_trace(result.steps, source)
    print(f"\nvalidator: {'clean' if not errors else f'{len(errors)} error(s)'}")
    for error in errors:
        print(f"  - {error}")
    ok = not errors

    if golden is not None:
        diffs = diff_states(result, golden)
        print(f"golden:    {'matches' if not diffs else f'{len(diffs)} difference(s)'}")
        for diff in diffs:
            print(f"  - {diff}")
        ok = ok and not diffs
    return ok


# --------------------------------------------------------------------------


def main() -> int:
    names = sorted(p.stem for p in FIXTURES.glob("*.json"))
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--example", choices=names, help="a built-in example (compared with its golden trace)")
    what.add_argument("--all-examples", action="store_true", help="every built-in example")
    what.add_argument("--file", help="a .java file")
    parser.add_argument("--model", default="claude-opus-5")
    parser.add_argument("--shape", choices=["wrapped", "ok"], default="wrapped")
    parser.add_argument("--out", help="save the resulting trace JSON here (single program only)")
    parser.add_argument("--replay", help="analyse this saved trace instead of calling the API")
    parser.add_argument("--dry-run", action="store_true", help="print what would be sent; no API call")
    args = parser.parse_args()

    if args.all_examples and (args.out or args.replay):
        parser.error("--out and --replay work on a single program, not --all-examples")

    if args.all_examples:
        work = [(n, *load_example(n)) for n in names]
    elif args.example:
        work = [(args.example, *load_example(args.example))]
    else:
        work = [(args.file, Path(args.file).read_text(), None)]

    client = None if (args.dry_run or args.replay) else anthropic.Anthropic()
    passed = 0
    for name, source, golden in work:
        print(f"\n{'=' * 72}\n{name}\n{'=' * 72}")
        if args.dry_run:
            print(f"system prompt: {len(SYSTEM_PROMPT)} chars (~{len(SYSTEM_PROMPT) // 4} tokens)\n")
            print(build_user_message(source))
            continue
        result = load_replay(args.replay) if args.replay else ask_model(client, args.model, source, args.shape)
        if result is None:
            continue
        if args.out:
            Path(args.out).write_bytes(RESPONSE.dump_json(result, indent=2) + b"\n")
            print(f"saved {args.out}")
        passed += analyse(source, result, golden)

    if args.dry_run:
        return 0
    print(f"\n{passed}/{len(work)} passed")
    return 0 if passed == len(work) else 1


if __name__ == "__main__":
    raise SystemExit(main())
