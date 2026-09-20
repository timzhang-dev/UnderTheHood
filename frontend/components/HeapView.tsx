import type { Changed, HeapEntry } from "@/lib/types";
import { colorFor, type HeapColor } from "@/lib/colors";
import ObjectCard from "./ObjectCard";
import ArrayCard from "./ArrayCard";

export default function HeapView({
  heap,
  colors,
  changed,
  stepKey = 0,
}: {
  heap: HeapEntry[];
  colors: Map<string, HeapColor>;
  changed: Changed | null;
  stepKey?: number;
}) {
  return (
    <section>
      <h3 className="label mb-2 flex items-center gap-3">
        Heap
        <span className="label-rule" aria-hidden />
      </h3>
      {heap.length === 0 ? (
        <p className="rounded-[10px] border border-dashed border-line-strong bg-surface/40 px-4 py-7 text-center text-xs leading-relaxed text-ink-faint">
          Nothing on the heap yet — these values live entirely on the stack.
        </p>
      ) : (
        <div className="space-y-2.5">
          {heap.map((entry) => {
            const color = colorFor(colors, entry.id);
            return entry.kind === "object" ? (
              <ObjectCard key={entry.id} entry={entry} color={color} colors={colors} changed={changed} stepKey={stepKey} />
            ) : (
              <ArrayCard key={entry.id} entry={entry} color={color} colors={colors} changed={changed} stepKey={stepKey} />
            );
          })}
        </div>
      )}
    </section>
  );
}
