"""D5 spike: does strict structured output accept our union-heavy trace schema?

The schema is acyclic (verified offline) but uses $ref, anyOf/oneOf discriminated
unions, and additionalProperties: false throughout. Whether the API accepts that
exact shape has to be measured, not assumed — and it must be measured BEFORE the
schema is frozen, because the fallback changes the schema.

Fallback if this fails: flatten Value into a single object with a `kind`
discriminator plus optional fields, keep the strict union in Pydantic only.

Run: uv run python scripts/spike_structured_output.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anthropic
from pydantic import TypeAdapter

from app.models.execution import TraceOk
from app.services.validator import validate_trace

SOURCE = """public class Main {
    public static void main(String[] args) {
        int[] a = {1, 2, 3};
        int[] b = a;
        b[0] = 10;
        System.out.println(a[0]);
    }
}"""

PROMPT = f"""Trace this Java program one step at a time.

Rules that matter most:
- Arrays are heap objects. `b = a` copies the REFERENCE, so a and b must share
  one heap id. Never duplicate a heap entry because two variables point at it.
- Heap ids are stable for the whole trace.
- stdout is cumulative.
- `line` is 1-based into the source below, and `source` echoes that exact line.

```java
{SOURCE}
```"""


def main() -> int:
    schema = TypeAdapter(TraceOk).json_schema()
    print(f"schema: {len(json.dumps(schema))} bytes, {len(schema.get('$defs', {}))} defs\n")

    client = anthropic.Anthropic()
    try:
        response = client.messages.parse(
            model="claude-opus-5",
            max_tokens=16000,
            messages=[{"role": "user", "content": PROMPT}],
            output_format=TraceOk,
        )
    except anthropic.APIStatusError as exc:
        print(f"REJECTED by the API ({exc.status_code}): {exc.message}")
        print("\n-> Fall back to the flattened Value schema before freezing.")
        return 1

    trace = response.parsed_output
    print(f"ACCEPTED. {len(trace.steps)} steps, usage={response.usage}\n")

    errors = validate_trace(trace.steps, SOURCE)
    if errors:
        print("Parsed, but failed semantic validation:")
        for e in errors:
            print(f"  - {e}")
        return 1

    # The actual lesson: did aliasing survive?
    final = trace.steps[-1]
    targets = {v.name: v.value.target for v in final.stackFrames[0].variables}
    print(f"final variable targets: {targets}")
    print(f"stdout: {final.stdout}")
    if len(set(targets.values())) == 1 and final.stdout == ["10"]:
        print("\nAliasing preserved and stdout correct. Schema is good to freeze.")
        return 0
    print("\nSchema works but the model got the semantics wrong — tune the prompt.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
