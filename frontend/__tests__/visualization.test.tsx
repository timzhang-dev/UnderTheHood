/**
 * Milestone 1's exit criterion, asserted rather than eyeballed:
 * "we can visually demonstrate aliasing from a hard-coded trace."
 *
 * These render the real components against the real golden fixtures, so they
 * fail if the visualization stops *showing* correct semantics — which is a
 * different failure from the backend tests, which only check the data is right.
 */

import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import CodePanel from "@/components/CodePanel";
import HeapView from "@/components/HeapView";
import StackView from "@/components/StackView";
import StdoutPanel from "@/components/StdoutPanel";
import { buildColorMap } from "@/lib/colors";
import { EXAMPLES } from "@/lib/examples";
import type { Example, Step } from "@/lib/types";

function example(id: string): { source: string; steps: Step[] } {
  const found = EXAMPLES.find((e) => e.id === id) as Example;
  if (found.trace.status !== "ok") throw new Error(`${id} fixture is not ok`);
  return { source: found.source, steps: found.trace.steps };
}

function renderState(steps: Step[], index: number) {
  const colors = buildColorMap(steps);
  const step = steps[index];
  return render(
    <>
      <StackView frames={step.stackFrames} colors={colors} changed={step.changed} />
      <HeapView heap={step.heap} colors={colors} changed={step.changed} />
      <StdoutPanel lines={step.stdout} />
    </>,
  );
}

describe("array aliasing", () => {
  const { steps } = example("array_aliasing");

  it("shows a and b carrying the SAME heap id after `int[] b = a`", () => {
    renderState(steps, 1);
    const stack = screen.getByRole("heading", { name: /stack/i }).parentElement!;
    const badges = within(stack)
      .getAllByText(/^obj_\d+$/)
      .map((el) => el.textContent);
    expect(badges).toEqual(["obj_1", "obj_1"]);
  });

  it("renders exactly one array card, not one per variable", () => {
    renderState(steps, 1);
    const heap = screen.getByRole("heading", { name: /heap/i }).parentElement!;
    expect(within(heap).getAllByText("obj_1")).toHaveLength(1);
    expect(within(heap).queryByText("obj_2")).toBeNull();
  });

  it("gives a and b the same colour, which is how aliasing reads visually", () => {
    renderState(steps, 1);
    const stack = screen.getByRole("heading", { name: /stack/i }).parentElement!;
    const [first, second] = within(stack).getAllByText(/^obj_\d+$/);
    expect(first.className).toBe(second.className);
  });

  it("shows the mutation through b landing in the shared array", () => {
    const before = renderState(steps, 1);
    expect(
      screen.getAllByTestId("array-cell").map((c) => c.textContent),
    ).toEqual(["1", "2", "3"]);
    before.unmount();

    renderState(steps, 2); // b[0] = 10;
    expect(
      screen.getAllByTestId("array-cell").map((c) => c.textContent),
    ).toEqual(["10", "2", "3"]);
  });

  it("prints 10 from a[0] at the end", () => {
    renderState(steps, steps.length - 1);
    const output = screen.getByRole("heading", { name: /output/i }).parentElement!;
    expect(within(output).getByText("10")).toBeTruthy();
  });
});

describe("independent objects", () => {
  const { steps } = example("independent_objects");

  it("renders two distinct heap cards after two `new` calls", () => {
    renderState(steps, 1);
    const heap = screen.getByRole("heading", { name: /heap/i }).parentElement!;
    expect(within(heap).getByText("obj_1")).toBeTruthy();
    expect(within(heap).getByText("obj_2")).toBeTruthy();
  });

  it("gives the two objects DIFFERENT colours", () => {
    renderState(steps, 1);
    const stack = screen.getByRole("heading", { name: /stack/i }).parentElement!;
    const [first, second] = within(stack).getAllByText(/^obj_\d+$/);
    expect(first.textContent).not.toBe(second.textContent);
    expect(first.className).not.toBe(second.className);
  });

  it("prints 1, because mutating b never touched a", () => {
    renderState(steps, steps.length - 1);
    const output = screen.getByRole("heading", { name: /output/i }).parentElement!;
    expect(within(output).getByText("1")).toBeTruthy();
  });
});

describe("primitives", () => {
  const { steps } = example("primitive_copy");

  it("shows values inline and never touches the heap", () => {
    renderState(steps, 2); // y = 10;
    const stack = screen.getByRole("heading", { name: /stack/i }).parentElement!;
    expect(within(stack).getByText("5")).toBeTruthy();
    expect(within(stack).getByText("10")).toBeTruthy();
    expect(within(stack).queryByText(/^obj_\d+$/)).toBeNull();
    expect(screen.getByText(/nothing on the heap yet/i)).toBeTruthy();
  });
});

describe("code panel", () => {
  const { source, steps } = example("array_aliasing");

  it("highlights the line the current step is executing", () => {
    const step = steps[2]; // b[0] = 10;
    const { container } = render(<CodePanel source={source} activeLine={step.line} />);
    const active = container.querySelector('[aria-current="step"]');
    expect(active?.textContent).toContain("b[0] = 10;");
  });

  it("moves the highlight as steps advance", () => {
    const seen = steps.map((step) => {
      const { container, unmount } = render(
        <CodePanel source={source} activeLine={step.line} />,
      );
      const text = container
        .querySelector('[aria-current="step"]')!
        .textContent!.trim();
      unmount();
      return text;
    });
    expect(new Set(seen).size).toBe(steps.length);
  });
});
