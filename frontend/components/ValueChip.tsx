import type { Value } from "@/lib/types";
import { colorFor, type HeapColor } from "@/lib/colors";

function formatPrimitive(value: boolean | number | string, type: string): string {
  if (type === "String") return `"${value}"`;
  if (type === "char") return `'${value}'`;
  return String(value);
}

/**
 * The single place a Value becomes pixels, so a primitive never accidentally
 * renders like a reference anywhere in the app.
 *
 * Primitives show their value inline — that IS the teaching point: the variable
 * holds the value. References show an arrow plus a coloured id badge, so the
 * variable visibly holds a pointer, not the thing.
 */
export default function ValueChip({
  value,
  colors,
}: {
  value: Value;
  colors: Map<string, HeapColor>;
}) {
  if (value.kind === "primitive") {
    return (
      <span className="font-mono text-sm text-slate-900">
        {formatPrimitive(value.value, value.type)}
      </span>
    );
  }

  if (value.target === null) {
    return (
      <span className="font-mono text-sm text-slate-400 italic">null</span>
    );
  }

  const color = colorFor(colors, value.target);
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-slate-400" aria-hidden>→</span>
      <span
        className={`rounded border px-1.5 py-0.5 font-mono text-xs font-medium ${color.chip}`}
      >
        {value.target}
      </span>
    </span>
  );
}
