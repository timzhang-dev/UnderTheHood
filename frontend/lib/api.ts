import { findExampleBySource } from "./examples";
import type { VisualizeResponse } from "./types";

// NEXT_PUBLIC_ variables are inlined into the bundle at BUILD time, and only when
// written as a literal `process.env.NEXT_PUBLIC_…` (no destructuring, no dynamic
// lookup). So a deployed build needs this set when it is built, not when it runs.
// The fallback is the local FastAPI dev server.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// The backend may make two model attempts (a first try plus one repair), and each
// can take a while. Without a limit a hung request would spin forever.
const TIMEOUT_MS = 150_000;

/**
 * The single seam between the UI and trace generation.
 *
 * The four built-in examples are resolved from their golden fixtures, in front of
 * any network call: they should never cost a model round-trip, and should never
 * be able to regress. Everything else goes to POST /api/visualize.
 *
 * This function never throws. page.tsx has no error state, but it already shows
 * `message` for any non-"ok" result, so a failed request (server down, timeout, a
 * 503 from the backend) is reported through that same path. Reusing "unsupported"
 * is a deliberate shortcut; a dedicated error status would need a page.tsx change.
 *
 * Keys live server-side only — nothing here ever sees one.
 */
export async function visualize(code: string): Promise<VisualizeResponse> {
  const example = findExampleBySource(code);
  if (example) return example.trace;

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/visualize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: "java", code }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    const timedOut = err instanceof DOMException && err.name === "TimeoutError";
    return failure(
      timedOut
        ? "That took too long. Please try again, or try a shorter program."
        : "Couldn't reach the server. Is the backend running?",
    );
  }

  if (!res.ok) return failure(await errorDetail(res));

  try {
    const body: unknown = await res.json();
    if (isVisualizeResponse(body)) return body;
  } catch {
    // Not JSON (for example an HTML error page from a proxy); handled below.
  }
  return failure("The server sent back something unexpected. Please try again.");
}

function failure(message: string): VisualizeResponse {
  return { status: "unsupported", message, unsupportedFeatures: [] };
}

// FastAPI reports errors as {"detail": "..."}. For a 422 the detail is a list of
// validation problems that mean nothing to a student, so only a string is shown.
async function errorDetail(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") return detail;
  } catch {
    // Body was not JSON.
  }
  return `The server returned an error (${res.status}). Please try again.`;
}

// A light runtime check, not full validation: the backend already validated the
// trace, and this only protects the page from a body that is not ours at all.
function isVisualizeResponse(body: unknown): body is VisualizeResponse {
  if (typeof body !== "object" || body === null) return false;
  const b = body as { status?: unknown; steps?: unknown; message?: unknown };
  return (
    (b.status === "ok" && Array.isArray(b.steps)) ||
    (b.status === "unsupported" && typeof b.message === "string")
  );
}
