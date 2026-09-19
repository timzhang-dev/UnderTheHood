import type { Example } from "./types";

// lib/fixtures/ is GENERATED — edit backend/scripts/build_fixtures.py, not these
// files. That script writes both this copy and the repo-root fixtures/ the
// backend tests assert against, in one pass, so the two cannot drift.
// (Next refuses to bundle modules outside its project root, which is why the
// frontend needs its own copy rather than importing ../../fixtures.)
import primitiveCopy from "./fixtures/primitive_copy.json";
import referenceAliasing from "./fixtures/reference_aliasing.json";
import arrayAliasing from "./fixtures/array_aliasing.json";
import independentObjects from "./fixtures/independent_objects.json";

// Ordered as a lesson, not alphabetically: copy semantics, then the reference
// twist, then arrays, then the contrast case that rules out "new always shares".
export const EXAMPLES: Example[] = [
  primitiveCopy as Example,
  referenceAliasing as Example,
  arrayAliasing as Example,
  independentObjects as Example,
];

export function findExampleBySource(source: string): Example | undefined {
  const normalized = source.trim();
  return EXAMPLES.find((e) => e.source.trim() === normalized);
}
