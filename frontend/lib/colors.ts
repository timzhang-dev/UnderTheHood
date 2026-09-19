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
 * Class strings are written out in full because Tailwind scans source text; a
 * template literal like `bg-${hue}-100` would be silently dropped at build.
 */
export interface HeapColor {
  /** Badge shown next to a stack variable. */
  chip: string;
  /** Heap card border. */
  border: string;
  /** Heap card header background. */
  header: string;
  /** Heap card id text. */
  title: string;
}

const PALETTE: HeapColor[] = [
  { chip: "bg-sky-100 text-sky-800 border-sky-300", border: "border-sky-300", header: "bg-sky-50", title: "text-sky-800" },
  { chip: "bg-violet-100 text-violet-800 border-violet-300", border: "border-violet-300", header: "bg-violet-50", title: "text-violet-800" },
  { chip: "bg-amber-100 text-amber-800 border-amber-300", border: "border-amber-300", header: "bg-amber-50", title: "text-amber-800" },
  { chip: "bg-emerald-100 text-emerald-800 border-emerald-300", border: "border-emerald-300", header: "bg-emerald-50", title: "text-emerald-800" },
  { chip: "bg-rose-100 text-rose-800 border-rose-300", border: "border-rose-300", header: "bg-rose-50", title: "text-rose-800" },
  { chip: "bg-teal-100 text-teal-800 border-teal-300", border: "border-teal-300", header: "bg-teal-50", title: "text-teal-800" },
];

export const NULL_COLOR: HeapColor = {
  chip: "bg-slate-100 text-slate-500 border-slate-300",
  border: "border-slate-300",
  header: "bg-slate-50",
  title: "text-slate-600",
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
