import type { Step } from "./types";

/**
 * Colour is how this product teaches aliasing (decision D3).
 *
 * Every heap object gets one colour for the whole trace. A stack variable shows
 * its target id in that colour, and the heap card wears the same colour. Two
 * variables carrying the same coloured badge IS the aliasing lesson — no arrows
 * required. Real SVG arrows are a polish-day upgrade on top of this, not a
 * prerequisite for it.
 *
 * Visual constraints the palette has to respect:
 *
 *  - Identity hues appear as TINTS only (soft badge, hairline rail, pale header
 *    wash). Solid saturated fill belongs to the accent, which means "execution
 *    is here", and a heap object must never be mistaken for a button.
 *  - No amber, and nothing warm enough to read as amber. Warm means "this just
 *    changed", and that has to stay the only warm signal on screen.
 *  - No indigo, which is the accent.
 *
 * Class strings are written out in full because Tailwind scans source text; a
 * template literal like `bg-${hue}-100` would be silently dropped at build.
 */
export interface HeapColor {
  /** Badge shown next to a stack variable, and on the heap card itself. */
  chip: string;
  /** 3px identity rail down the left edge of the heap card. */
  rail: string;
  /** Heap card header wash. */
  header: string;
  /** Heap card id text. */
  title: string;
}

const PALETTE: HeapColor[] = [
  { chip: "border-sky-200 bg-sky-50 text-sky-700", rail: "bg-sky-400", header: "bg-sky-50/60", title: "text-sky-700" },
  { chip: "border-violet-200 bg-violet-50 text-violet-700", rail: "bg-violet-400", header: "bg-violet-50/60", title: "text-violet-700" },
  { chip: "border-teal-200 bg-teal-50 text-teal-700", rail: "bg-teal-400", header: "bg-teal-50/60", title: "text-teal-700" },
  { chip: "border-rose-200 bg-rose-50 text-rose-700", rail: "bg-rose-400", header: "bg-rose-50/60", title: "text-rose-700" },
  { chip: "border-emerald-200 bg-emerald-50 text-emerald-700", rail: "bg-emerald-400", header: "bg-emerald-50/60", title: "text-emerald-700" },
  { chip: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700", rail: "bg-fuchsia-400", header: "bg-fuchsia-50/60", title: "text-fuchsia-700" },
];

export const NULL_COLOR: HeapColor = {
  chip: "border-line bg-sunken text-ink-faint",
  rail: "bg-line-strong",
  header: "bg-sunken/60",
  title: "text-ink-muted",
};

/**
 * Assigns colours in order of first appearance across the WHOLE trace, not
 * per-step. Per-step assignment would make an object change colour the moment
 * another is allocated before it — exactly the wrong signal.
 */
export function buildColorMap(steps: Step[]): Map<string, HeapColor> {
  const map = new Map<string, HeapColor>();
  for (const step of steps) {
    for (const entry of step.heap) {
      if (!map.has(entry.id)) {
        map.set(entry.id, PALETTE[map.size % PALETTE.length]);
      }
    }
  }
  return map;
}

export function colorFor(map: Map<string, HeapColor>, id: string | null): HeapColor {
  return (id && map.get(id)) || NULL_COLOR;
}
