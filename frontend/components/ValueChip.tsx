import type { Value } from "@/lib/types";
import { colorFor, type HeapColor } from "@/lib/colors";
import { TOKEN_CLASS } from "@/lib/highlight";

function formatPrimitive(value: boolean | number | string, type: string): string {
  if (type === "String") return `"${value}"`;
  if (type === "char") return `'${value}'`;
  return String(value);
}

/** Literals wear the same colours here as in the code panel, so that a value
 *  the student reads in the source is recognisably the same value in memory. */
function primitiveClass(type: string, value: boolean | number | string): string {
  if (type === "String" || type === "char") return TOKEN_CLASS.string;
  if (type === "boolean" || typeof value === "boolean") return TOKEN_CLASS.keyword;
  return TOKEN_CLASS.number;
}

/**
 * The single place a Value becomes pixels, so a primitive never accidentally
 * renders like a reference anywhere in the app.
 *
 * Primitives show their value inline — that IS the teaching point: the variable
 * holds the value. References show an arrow plus a coloured id badge, so the
 * variable visibly holds a pointer, not the thing.
 *
 * The badge is the same `.id-badge` shape worn by the heap card it points at.
 * Matching shape plus matching colour is what lets two aliased variables read as
 * "the same object" at a glance, with no arrow drawn between them.
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
      <span className={`font-mono text-[13px] tabular-nums ${primitiveClass(value.type, value.value)}`}>
        {formatPrimitive(value.value, value.type)}
      </span>
    );
  }

  if (value.target === null) {
    return (
      <span className="font-mono text-[13px] italic text-ink-faint">null</span>
    );
  }

  const color = colorFor(colors, value.target);
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="font-mono text-[11px] leading-none text-ink-faint" aria-hidden>
        →
      </span>
      <span className={`id-badge ${color.chip}`}>{value.target}</span>
    </span>
  );
}
