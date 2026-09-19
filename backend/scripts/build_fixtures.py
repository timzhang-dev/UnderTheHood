"""Builds the golden fixture traces in fixtures/.

These four traces are hand-authored, not LLM-generated. They are the shared
contract (frontend renders them, backend tests assert on them) and they are
served for the built-in examples without ever calling the model — so the demo
path is instant, free, and cannot regress.

Writes to TWO places, on purpose:

  fixtures/                     repo-root copy; the backend test suite reads this
  frontend/lib/fixtures/        bundler-visible copy

The frontend copy is not a convenience. Next refuses to bundle modules outside
its project root, and Vercel building from frontend/ would not see ../fixtures
at all. Rather than a separate sync step that can be forgotten, one generator
writes both — so they cannot drift.

Run: uv run python scripts/build_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import TypeAdapter

from app.models.execution import VisualizeResponse

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = [ROOT / "fixtures", ROOT / "frontend" / "lib" / "fixtures"]


# --- terse builders -------------------------------------------------------

def prim(type_, value):
    return {"kind": "primitive", "type": type_, "value": value}


def ref(type_, target):
    return {"kind": "reference", "type": type_, "target": target}


def obj(id_, type_, **fields):
    return {
        "kind": "object",
        "id": id_,
        "type": type_,
        "fields": [{"name": k, "value": v} for k, v in fields.items()],
    }


def arr(id_, type_, *elements):
    return {"kind": "array", "id": id_, "type": type_, "elements": list(elements)}


def frame(name, **variables):
    return {
        "name": name,
        "variables": [{"name": k, "value": v} for k, v in variables.items()],
    }


def build(source: str, raw_steps: list[dict]) -> dict:
    """Numbers the steps and fills `source` from `line`, so the two cannot drift."""
    lines = source.split("\n")
    steps = []
    for i, s in enumerate(raw_steps, start=1):
        line = s["line"]
        steps.append(
            {
                "step": i,
                "line": line,
                "source": lines[line - 1],
                "stackFrames": s["stackFrames"],
                "heap": s.get("heap", []),
                "stdout": s.get("stdout", []),
                "explanation": s["explanation"],
                "changed": s.get("changed"),
            }
        )
    return {"status": "ok", "steps": steps}


# --- MyData boilerplate, shared by two examples ---------------------------
# D1: classes referenced by a snippet must be defined in that snippet. No magic
# auto-injection — it would break line-number mapping and teach a Java that
# doesn't exist.
MYDATA = """class MyData {
    int value;

    MyData(int value) {
        this.value = value;
    }
}

"""


# --------------------------------------------------------------------------
# 1. Primitive copy
# --------------------------------------------------------------------------

primitive_copy_src = """public class Main {
    public static void main(String[] args) {
        int x = 5;
        int y = x;
        y = 10;

        System.out.println(x);
        System.out.println(y);
    }
}"""

primitive_copy = build(
    primitive_copy_src,
    [
        {
            "line": 3,
            "stackFrames": [frame("main", x=prim("int", 5))],
            "explanation": "The variable x is created on the stack and holds the value 5 directly. Primitives store their value, not a reference.",
            "changed": {"kind": "variable", "frame": 0, "name": "x"},
        },
        {
            "line": 4,
            "stackFrames": [frame("main", x=prim("int", 5), y=prim("int", 5))],
            "explanation": "y is created and given a COPY of x's value. There are now two independent 5s on the stack.",
            "changed": {"kind": "variable", "frame": 0, "name": "y"},
        },
        {
            "line": 5,
            "stackFrames": [frame("main", x=prim("int", 5), y=prim("int", 10))],
            "explanation": "y is changed to 10. x is untouched, because y only ever held a copy — the two variables were never linked.",
            "changed": {"kind": "variable", "frame": 0, "name": "y"},
        },
        {
            "line": 7,
            "stackFrames": [frame("main", x=prim("int", 5), y=prim("int", 10))],
            "stdout": ["5"],
            "explanation": "Printing x gives 5. Assigning to y never affected it.",
        },
        {
            "line": 8,
            "stackFrames": [frame("main", x=prim("int", 5), y=prim("int", 10))],
            "stdout": ["5", "10"],
            "explanation": "Printing y gives 10. Each primitive variable holds its own separate value.",
        },
    ],
)


# --------------------------------------------------------------------------
# 2. Reference aliasing
# --------------------------------------------------------------------------

reference_aliasing_src = MYDATA + """public class Main {
    public static void main(String[] args) {
        MyData a = new MyData(1);
        MyData b = a;

        b.value = 5;

        System.out.println(a.value);
    }
}"""

reference_aliasing = build(
    reference_aliasing_src,
    [
        {
            "line": 11,
            "stackFrames": [frame("main", a=ref("MyData", "obj_1"))],
            "heap": [obj("obj_1", "MyData", value=prim("int", 1))],
            "explanation": "A new MyData object is created on the heap. The variable a does NOT contain the object — it holds a reference pointing to it.",
            "changed": {"kind": "variable", "frame": 0, "name": "a"},
        },
        {
            "line": 12,
            "stackFrames": [
                frame("main", a=ref("MyData", "obj_1"), b=ref("MyData", "obj_1"))
            ],
            "heap": [obj("obj_1", "MyData", value=prim("int", 1))],
            "explanation": "b = a copies the REFERENCE, not the object. No new object is created — a and b now both point at the same obj_1.",
            "changed": {"kind": "variable", "frame": 0, "name": "b"},
        },
        {
            "line": 14,
            "stackFrames": [
                frame("main", a=ref("MyData", "obj_1"), b=ref("MyData", "obj_1"))
            ],
            "heap": [obj("obj_1", "MyData", value=prim("int", 5))],
            "explanation": "Following b's reference leads to obj_1, and its value field becomes 5. Because a points to that same object, a.value changed too.",
            "changed": {"kind": "field", "id": "obj_1", "field": "value"},
        },
        {
            "line": 16,
            "stackFrames": [
                frame("main", a=ref("MyData", "obj_1"), b=ref("MyData", "obj_1"))
            ],
            "heap": [obj("obj_1", "MyData", value=prim("int", 5))],
            "stdout": ["5"],
            "explanation": "This prints 5, not 1. We only ever assigned through b — but a and b are two names for one object.",
        },
    ],
)


# --------------------------------------------------------------------------
# 3. Array aliasing
# --------------------------------------------------------------------------

array_aliasing_src = """public class Main {
    public static void main(String[] args) {
        int[] a = {1, 2, 3};
        int[] b = a;

        b[0] = 10;

        System.out.println(a[0]);
    }
}"""

array_aliasing = build(
    array_aliasing_src,
    [
        {
            "line": 3,
            "stackFrames": [frame("main", a=ref("int[]", "obj_1"))],
            "heap": [
                arr("obj_1", "int[]", prim("int", 1), prim("int", 2), prim("int", 3))
            ],
            "explanation": "Arrays are objects in Java. The array lives on the heap, and a holds a reference to it.",
            "changed": {"kind": "variable", "frame": 0, "name": "a"},
        },
        {
            "line": 4,
            "stackFrames": [
                frame("main", a=ref("int[]", "obj_1"), b=ref("int[]", "obj_1"))
            ],
            "heap": [
                arr("obj_1", "int[]", prim("int", 1), prim("int", 2), prim("int", 3))
            ],
            "explanation": "b = a copies the reference. The array itself is NOT copied — there is still exactly one array.",
            "changed": {"kind": "variable", "frame": 0, "name": "b"},
        },
        {
            "line": 6,
            "stackFrames": [
                frame("main", a=ref("int[]", "obj_1"), b=ref("int[]", "obj_1"))
            ],
            "heap": [
                arr("obj_1", "int[]", prim("int", 10), prim("int", 2), prim("int", 3))
            ],
            "explanation": "Writing to b[0] changes slot 0 of the one shared array to 10.",
            "changed": {"kind": "element", "id": "obj_1", "index": 0},
        },
        {
            "line": 8,
            "stackFrames": [
                frame("main", a=ref("int[]", "obj_1"), b=ref("int[]", "obj_1"))
            ],
            "heap": [
                arr("obj_1", "int[]", prim("int", 10), prim("int", 2), prim("int", 3))
            ],
            "stdout": ["10"],
            "explanation": "a[0] prints 10. a and b are two references to the same array, so a change through one is visible through the other.",
        },
    ],
)


# --------------------------------------------------------------------------
# 4. Independent objects (the contrast case for #2)
# --------------------------------------------------------------------------

independent_objects_src = MYDATA + """public class Main {
    public static void main(String[] args) {
        MyData a = new MyData(1);
        MyData b = new MyData(1);

        b.value = 5;

        System.out.println(a.value);
    }
}"""

independent_objects = build(
    independent_objects_src,
    [
        {
            "line": 11,
            "stackFrames": [frame("main", a=ref("MyData", "obj_1"))],
            "heap": [obj("obj_1", "MyData", value=prim("int", 1))],
            "explanation": "The first MyData object is created, and a references it.",
            "changed": {"kind": "variable", "frame": 0, "name": "a"},
        },
        {
            "line": 12,
            "stackFrames": [
                frame("main", a=ref("MyData", "obj_1"), b=ref("MyData", "obj_2"))
            ],
            "heap": [
                obj("obj_1", "MyData", value=prim("int", 1)),
                obj("obj_2", "MyData", value=prim("int", 1)),
            ],
            "explanation": "`new` runs a second time, so a SECOND object appears on the heap. Equal contents, but a separate object — b points to obj_2.",
            "changed": {"kind": "variable", "frame": 0, "name": "b"},
        },
        {
            "line": 14,
            "stackFrames": [
                frame("main", a=ref("MyData", "obj_1"), b=ref("MyData", "obj_2"))
            ],
            "heap": [
                obj("obj_1", "MyData", value=prim("int", 1)),
                obj("obj_2", "MyData", value=prim("int", 5)),
            ],
            "explanation": "Only obj_2 is modified. obj_1 is a different object and is unaffected.",
            "changed": {"kind": "field", "id": "obj_2", "field": "value"},
        },
        {
            "line": 16,
            "stackFrames": [
                frame("main", a=ref("MyData", "obj_1"), b=ref("MyData", "obj_2"))
            ],
            "heap": [
                obj("obj_1", "MyData", value=prim("int", 1)),
                obj("obj_2", "MyData", value=prim("int", 5)),
            ],
            "stdout": ["1"],
            "explanation": "This prints 1. Compare with the aliasing example, where the same code printed 5 — the difference is one `new`.",
        },
    ],
)


# --------------------------------------------------------------------------

EXAMPLES = [
    {
        "id": "primitive_copy",
        "title": "Primitive Copy",
        "teaches": "Assigning a primitive copies the value.",
        "source": primitive_copy_src,
        "trace": primitive_copy,
    },
    {
        "id": "reference_aliasing",
        "title": "Reference Aliasing",
        "teaches": "Assigning a reference copies the reference, not the object.",
        "source": reference_aliasing_src,
        "trace": reference_aliasing,
    },
    {
        "id": "array_aliasing",
        "title": "Array Aliasing",
        "teaches": "Arrays are objects, so two variables can share one array.",
        "source": array_aliasing_src,
        "trace": array_aliasing,
    },
    {
        "id": "independent_objects",
        "title": "Independent Objects",
        "teaches": "Two `new` calls make two objects — contrast with aliasing.",
        "source": independent_objects_src,
        "trace": independent_objects,
    },
]


def main() -> None:
    adapter = TypeAdapter(VisualizeResponse)
    for ex in EXAMPLES:
        adapter.validate_python(ex["trace"])  # fail loudly before writing anything
    for directory in OUTPUTS:
        directory.mkdir(parents=True, exist_ok=True)
        for ex in EXAMPLES:
            path = directory / f"{ex['id']}.json"
            path.write_text(json.dumps(ex, indent=2) + "\n")
        print(f"wrote {len(EXAMPLES)} fixtures to {directory.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
