import { findExampleBySource } from "./examples";
import type { VisualizeResponse } from "./types";

/**
 * The single seam between the UI and trace generation.
 *
 * Right now it resolves the built-in examples from their golden fixtures and
 * declines anything else — which is exactly Milestone 1: prove the visualization
 * works against a known-good trace before any model is involved.
 *
 * When POST /api/visualize lands, only this function changes:
 *
 *   const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/visualize`, {
 *     method: "POST",
 *     headers: { "Content-Type": "application/json" },
 *     body: JSON.stringify({ language: "java", code }),
 *   });
 *   return res.json();
 *
 * The fixture lookup stays in front of that call regardless: the four built-in
 * examples should never cost a model round-trip, and should never be able to
 * regress. Keys live server-side only — nothing here ever sees one.
 */
export async function visualize(code: string): Promise<VisualizeResponse> {
  const example = findExampleBySource(code);
  if (example) return example.trace;

  return {
    status: "unsupported",
    message:
      "Custom programs aren't wired up yet — trace generation lands with the backend. " +
      "Try one of the built-in examples below.",
    unsupportedFeatures: [],
  };
}
