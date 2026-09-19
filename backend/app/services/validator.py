"""Deterministic semantic validation of an execution trace.

Schema validation proves a trace has the right SHAPE. It does not prove the
trace is honest: a model can emit perfectly-shaped JSON in which `b` silently
stops aliasing `a`, which is precisely the lie this product exists to prevent.

Everything below is a cheap structural check with no LLM involved. The checks
that matter most are the cross-step identity invariants (heap type/kind, field
sets, array lengths, stdout prefix) — those are what catch a model quietly
losing track of an object between steps.

Returns a list of human-readable errors. Empty list means the trace is clean.
The errors are fed back to the model verbatim on the single repair attempt, so
they are written to be actionable.
"""

from __future__ import annotations

from app.models.execution import STEP_CAP, ArrayEntry, ObjectEntry, Step


def _iter_references(step: Step):
    """Yields (description, target) for every reference anywhere in the step."""
    for frame in step.stackFrames:
        for var in frame.variables:
            if var.value.kind == "reference":
                yield f"variable {frame.name}.{var.name}", var.value.target
    for entry in step.heap:
        if isinstance(entry, ObjectEntry):
            for field in entry.fields:
                if field.value.kind == "reference":
                    yield f"field {entry.id}.{field.name}", field.value.target
        else:
            for i, element in enumerate(entry.elements):
                if element.kind == "reference":
                    yield f"element {entry.id}[{i}]", element.target


def validate_trace(steps: list[Step], source: str) -> list[str]:
    errors: list[str] = []
    lines = source.split("\n")

    if not steps:
        return ["Trace contains no steps."]
    if len(steps) > STEP_CAP:
        errors.append(
            f"Trace has {len(steps)} steps, over the {STEP_CAP}-step cap. "
            f"Return status 'unsupported' instead of truncating."
        )

    # Remembers the first shape seen for each heap id, so later steps are checked
    # against it. Java objects don't gain fields and arrays don't resize.
    seen: dict[str, dict] = {}

    for i, step in enumerate(steps):
        where = f"step {step.step}"

        # --- step numbering ------------------------------------------------
        if step.step != i + 1:
            errors.append(f"{where}: steps must be numbered 1..N contiguously; expected {i + 1}.")

        # --- line / source agreement ---------------------------------------
        if not (1 <= step.line <= len(lines)):
            errors.append(f"{where}: line {step.line} is outside the source (1..{len(lines)}).")
        elif step.source.strip() != lines[step.line - 1].strip():
            errors.append(
                f"{where}: source {step.source.strip()!r} does not match "
                f"line {step.line}, which is {lines[step.line - 1].strip()!r}."
            )

        # --- heap ids unique within the step -------------------------------
        ids = [entry.id for entry in step.heap]
        duplicates = {x for x in ids if ids.count(x) > 1}
        if duplicates:
            errors.append(
                f"{where}: duplicate heap ids {sorted(duplicates)}. Each object appears "
                f"exactly once; multiple variables reference it by the same id."
            )
        live = set(ids)

        # --- every reference resolves --------------------------------------
        for description, target in _iter_references(step):
            if target is not None and target not in live:
                errors.append(f"{where}: {description} points to {target!r}, which is not on the heap.")

        # --- heap identity is stable across steps --------------------------
        for entry in step.heap:
            shape = {
                "kind": entry.kind,
                "type": entry.type,
                "fields": tuple(f.name for f in entry.fields) if isinstance(entry, ObjectEntry) else None,
                "length": len(entry.elements) if isinstance(entry, ArrayEntry) else None,
            }
            prior = seen.get(entry.id)
            if prior is None:
                seen[entry.id] = shape
                continue
            if prior["kind"] != shape["kind"]:
                errors.append(
                    f"{where}: {entry.id} is a {shape['kind']} but was a {prior['kind']} earlier. "
                    f"A heap id refers to one object for the whole trace."
                )
            elif prior["type"] != shape["type"]:
                errors.append(
                    f"{where}: {entry.id} has type {shape['type']!r} but was {prior['type']!r} earlier. "
                    f"An object's type never changes."
                )
            elif shape["fields"] is not None and prior["fields"] != shape["fields"]:
                errors.append(
                    f"{where}: {entry.id} has fields {list(shape['fields'])} but had "
                    f"{list(prior['fields'])} earlier. Java objects do not gain or lose fields."
                )
            elif shape["length"] is not None and prior["length"] != shape["length"]:
                errors.append(
                    f"{where}: array {entry.id} has length {shape['length']} but had "
                    f"{prior['length']} earlier. Java arrays are fixed-length."
                )

        # --- stdout only ever grows ----------------------------------------
        if i > 0:
            previous = steps[i - 1].stdout
            if step.stdout[: len(previous)] != previous:
                errors.append(
                    f"{where}: stdout {step.stdout} does not extend the previous step's "
                    f"{previous}. stdout is cumulative and never rewritten."
                )

        # --- the change marker points at something real --------------------
        changed = step.changed
        if changed is None:
            continue
        if changed.kind == "variable":
            if not (0 <= changed.frame < len(step.stackFrames)):
                errors.append(f"{where}: changed.frame {changed.frame} is not a valid stack frame.")
            elif changed.name not in {v.name for v in step.stackFrames[changed.frame].variables}:
                errors.append(f"{where}: changed marks variable {changed.name!r}, which is not in that frame.")
        else:
            entry = next((e for e in step.heap if e.id == changed.id), None)
            if entry is None:
                errors.append(f"{where}: changed marks {changed.id!r}, which is not on the heap.")
            elif changed.kind == "field":
                if not isinstance(entry, ObjectEntry):
                    errors.append(f"{where}: changed marks a field on {changed.id!r}, which is an array.")
                elif changed.field not in {f.name for f in entry.fields}:
                    errors.append(f"{where}: changed marks field {changed.field!r}, absent from {changed.id}.")
            elif changed.kind == "element":
                if not isinstance(entry, ArrayEntry):
                    errors.append(f"{where}: changed marks an element of {changed.id!r}, which is an object.")
                elif not (0 <= changed.index < len(entry.elements)):
                    errors.append(f"{where}: changed marks index {changed.index}, out of bounds for {changed.id}.")

    return errors
