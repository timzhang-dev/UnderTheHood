/**
 * Mirror of backend/app/models/execution.py.
 *
 * Hand-written for now, deliberately: the FastAPI endpoint doesn't exist yet, so
 * there is no OpenAPI document to generate from. Once POST /api/visualize lands,
 * replace this file with `openapi-typescript` output plus a CI drift check —
 * that's the plan's answer to schema drift between Dev B and Devs A/C.
 *
 * Until then, this file and execution.py must be changed together.
 */

export type PrimitiveType =
  | "int" | "long" | "short" | "byte"
  | "double" | "float" | "boolean" | "char"
  | "String";

export interface PrimitiveValue {
  kind: "primitive";
  type: PrimitiveType;
  value: boolean | number | string;
}

export interface ReferenceValue {
  kind: "reference";
  /** Declared type, e.g. "MyData" or "int[]". */
  type: string;
  /** Heap entry id, or null for a null reference. */
  target: string | null;
}

/** Non-recursive on purpose — see the note in execution.py. */
export type Value = PrimitiveValue | ReferenceValue;

export interface ObjectField {
  name: string;
  value: Value;
}

export interface ObjectEntry {
  kind: "object";
  id: string;
  type: string;
  fields: ObjectField[];
}

export interface ArrayEntry {
  kind: "array";
  id: string;
  type: string;
  elements: Value[];
}

export type HeapEntry = ObjectEntry | ArrayEntry;

export interface Variable {
  name: string;
  value: Value;
}

export interface Frame {
  name: string;
  variables: Variable[];
}

export type Changed =
  | { kind: "variable"; frame: number; name: string }
  | { kind: "field"; id: string; field: string }
  | { kind: "element"; id: string; index: number };

export interface Step {
  step: number;
  /** 1-based into the submitted source. */
  line: number;
  source: string;
  /** Index 0 is the bottom of the stack (main); the last entry is executing. */
  stackFrames: Frame[];
  heap: HeapEntry[];
  /** Cumulative — render directly, no accumulation. */
  stdout: string[];
  explanation: string;
  changed: Changed | null;
}

export type VisualizeResponse =
  | { status: "ok"; steps: Step[] }
  | { status: "unsupported"; message: string; unsupportedFeatures: string[] };

export interface Example {
  id: string;
  title: string;
  teaches: string;
  source: string;
  trace: VisualizeResponse;
}
