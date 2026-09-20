import type { Changed, ObjectEntry } from "@/lib/types";
import type { HeapColor } from "@/lib/colors";
import ValueChip from "./ValueChip";

export default function ObjectCard({
  entry,
  color,
  colors,
  changed,
  stepKey = 0,
}: {
  entry: ObjectEntry;
  color: HeapColor;
  colors: Map<string, HeapColor>;
  changed: Changed | null;
  stepKey?: number;
}) {
  return (
    // `spawn` fires on mount only, and cards are keyed by heap id — so the
    // animation plays exactly when the object is allocated, and never again.
    <div className="panel spawn relative">
      <span aria-hidden className={`absolute inset-y-0 left-0 w-[3px] ${color.rail}`} />
      <div className={`flex items-baseline gap-2 border-b border-line px-3.5 py-2 ${color.header}`}>
        <span className={`id-badge ${color.chip}`}>{entry.id}</span>
        <span className="font-mono text-[11px] text-ink-faint">{entry.type}</span>
      </div>
      <ul className="divide-y divide-line/70">
        {entry.fields.map((field) => {
          const highlighted =
            changed?.kind === "field" &&
            changed.id === entry.id &&
            changed.field === field.name;
          return (
            <li
              key={highlighted ? `${field.name}@${stepKey}` : field.name}
              className={`flex items-center justify-between gap-4 px-3.5 py-2 ${
                highlighted
                  ? "flash bg-mutation-soft ring-1 ring-inset ring-mutation-line"
                  : ""
              }`}
            >
              <span className="font-mono text-[13px] text-ink-muted">{field.name}</span>
              <ValueChip value={field.value} colors={colors} />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
