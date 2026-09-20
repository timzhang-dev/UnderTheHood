/**
 * lib/api.ts is the only place the UI talks to the backend, and page.tsx has no
 * error state — so the contract under test here is that visualize() never throws
 * and always hands the page something it can display.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { visualize } from "@/lib/api";
import { EXAMPLES } from "@/lib/examples";

const CUSTOM = "public class Main { public static void main(String[] a) { int q = 1; } }";

function respond(body: unknown, init: ResponseInit = { status: 200 }) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), init));
}

afterEach(() => vi.unstubAllGlobals());

describe("visualize", () => {
  it("serves a built-in example from its fixture without any network call", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const result = await visualize(EXAMPLES[0].source);

    expect(result).toEqual(EXAMPLES[0].trace);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts custom code to /api/visualize as java and returns the backend's answer", async () => {
    const answer = { status: "ok", steps: [] };
    const fetchMock = respond(answer);
    vi.stubGlobal("fetch", fetchMock);

    const result = await visualize(CUSTOM);

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/visualize$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ language: "java", code: CUSTOM });
    expect(result).toEqual(answer);
  });

  it("passes an unsupported answer straight through", async () => {
    const answer = { status: "unsupported", message: "Uses generics.", unsupportedFeatures: ["generics"] };
    vi.stubGlobal("fetch", respond(answer));

    expect(await visualize(CUSTOM)).toEqual(answer);
  });

  it("shows the backend's own message for a 503", async () => {
    vi.stubGlobal("fetch", respond({ detail: "The service is busy right now." }, { status: 503 }));

    const result = await visualize(CUSTOM);

    expect(result).toMatchObject({ status: "unsupported", message: "The service is busy right now." });
  });

  it("does not show a 422's validation list to the student", async () => {
    vi.stubGlobal("fetch", respond({ detail: [{ loc: ["body", "code"], msg: "field required" }] }, { status: 422 }));

    const result = await visualize(CUSTOM);

    expect(result).toMatchObject({ status: "unsupported" });
    expect((result as { message: string }).message).toContain("422");
  });

  it("reports an unreachable server instead of throwing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const result = await visualize(CUSTOM);

    expect(result).toMatchObject({ status: "unsupported" });
    expect((result as { message: string }).message).toMatch(/reach the server/i);
  });

  it("reports a timeout as such", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("timed out", "TimeoutError")));

    const result = await visualize(CUSTOM);

    expect((result as { message: string }).message).toMatch(/too long/i);
  });

  it("survives a 200 whose body is not one of ours", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>bad gateway</html>", { status: 200 })));

    const result = await visualize(CUSTOM);

    expect(result).toMatchObject({ status: "unsupported" });
    expect((result as { message: string }).message).toMatch(/unexpected/i);
  });
});
