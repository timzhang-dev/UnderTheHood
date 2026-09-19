import type { ArrayEntry, Changed } from "@/lib/types";
import type { HeapColor } from "@/lib/colors";
import ValueChip from "./ValueChip";

export default function ArrayCard({
  entry,
  color,
  colors,
  changed,
}: {
  entry: ArrayEntry;
  color: HeapColor;
  colors: Map<string, HeapColor>;
  changed: Changed | null;
}) {
  return (
    <div className={`overflow-hidden rounded-lg border bg-white ${color.border}`}>
      <div className={`flex items-baseline gap-2 border-b px-3 py-1.5 ${color.border} ${color.header}`}>
        <span className={`font-mono text-xs font-semibold ${color.title}`}>
          {entry.id}
        </span>
        <span className="font-mono text-xs text-slate-500">{entry.type}</span>
      </div>
      {/* Indices sit under the cells: beginners need to see that b[0] is a slot,
          not a name. Horizontal scroll keeps long arrays from breaking layout. */}
      <div className="overflow-x-auto p-3">
        <div className="flex gap-1">
          {entry.elements.map((element, index) => {
            const highlighted =
              changed?.kind === "element" &&
              changed.id === entry.id &&
              changed.index === index;
            return (
              <div key={index} className="flex flex-col items-center gap-1">
                <div
                  data-testid="array-cell"
                  className={`flex h-10 min-w-12 items-center justify-center rounded border px-2 ${
                    highlighted
                      ? "border-amber-400 bg-amber-50 ring-1 ring-amber-300"
                      : "border-slate-200 bg-slate-50"
                  }`}
                >
                  <ValueChip value={element} colors={colors} />
                </div>
                <span className="font-mono text-[10px] text-slate-400">{index}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
