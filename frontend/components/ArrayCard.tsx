import type { ArrayEntry, Changed } from "@/lib/types";
import type { HeapColor } from "@/lib/colors";
import ValueChip from "./ValueChip";

export default function ArrayCard({
  entry,
  color,
  colors,
  changed,
  stepKey = 0,
}: {
  entry: ArrayEntry;
  color: HeapColor;
  colors: Map<string, HeapColor>;
  changed: Changed | null;
  stepKey?: number;
}) {
  const last = entry.elements.length - 1;

  return (
    <div className="panel spawn relative">
      <span aria-hidden className={`absolute inset-y-0 left-0 w-[3px] ${color.rail}`} />
      <div className={`flex items-baseline gap-2 border-b border-line px-3.5 py-2 ${color.header}`}>
        <span className={`id-badge ${color.chip}`}>{entry.id}</span>
        <span className="font-mono text-[11px] text-ink-faint">{entry.type}</span>
      </div>
      {/* Indices sit under the cells: beginners need to see that b[0] is a slot,
          not a name. Cells share borders so the array reads as one contiguous
          block of memory rather than a row of loose chips. Horizontal scroll
          keeps long arrays from breaking layout. */}
      <div className="overflow-x-auto px-3.5 py-3">
        <div className="flex">
          {entry.elements.map((element, index) => {
            const highlighted =
              changed?.kind === "element" &&
              changed.id === entry.id &&
              changed.index === index;
            return (
              <div
                key={highlighted ? `${index}@${stepKey}` : index}
                className={`flex flex-col items-center gap-1 ${index > 0 ? "-ml-px" : ""}`}
              >
                <div
                  data-testid="array-cell"
                  className={`relative flex h-10 min-w-12 items-center justify-center border px-2.5 transition-colors duration-200 ${
                    index === 0 ? "rounded-l-md" : ""
                  } ${index === last ? "rounded-r-md" : ""} ${
                    highlighted
                      ? "z-10 border-mutation-line bg-mutation-soft flash"
                      : "border-line bg-sunken/50"
                  }`}
                >
                  <ValueChip value={element} colors={colors} />
                </div>
                <span className="font-mono text-[10px] tabular-nums text-ink-faint">
                  {index}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
