import type { Changed, HeapEntry } from "@/lib/types";
import { colorFor, type HeapColor } from "@/lib/colors";
import ObjectCard from "./ObjectCard";
import ArrayCard from "./ArrayCard";

export default function HeapView({
  heap,
  colors,
  changed,
}: {
  heap: HeapEntry[];
  colors: Map<string, HeapColor>;
  changed: Changed | null;
}) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Heap
      </h3>
      {heap.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-200 px-3 py-6 text-center text-xs text-slate-400">
          Nothing on the heap yet — these values live entirely on the stack.
        </p>
      ) : (
        <div className="space-y-3">
          {heap.map((entry) => {
            const color = colorFor(colors, entry.id);
            return entry.kind === "object" ? (
              <ObjectCard key={entry.id} entry={entry} color={color} colors={colors} changed={changed} />
            ) : (
              <ArrayCard key={entry.id} entry={entry} color={color} colors={colors} changed={changed} />
            );
          })}
        </div>
      )}
    </section>
  );
}
