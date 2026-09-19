import type { Changed, ObjectEntry } from "@/lib/types";
import type { HeapColor } from "@/lib/colors";
import ValueChip from "./ValueChip";

export default function ObjectCard({
  entry,
  color,
  colors,
  changed,
}: {
  entry: ObjectEntry;
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
      <ul className="divide-y divide-slate-100">
        {entry.fields.map((field) => {
          const highlighted =
            changed?.kind === "field" &&
            changed.id === entry.id &&
            changed.field === field.name;
          return (
            <li
              key={field.name}
              className={`flex items-center justify-between gap-4 px-3 py-2 ${
                highlighted ? "bg-amber-50 ring-1 ring-inset ring-amber-300" : ""
              }`}
            >
              <span className="font-mono text-sm text-slate-600">{field.name}</span>
              <ValueChip value={field.value} colors={colors} />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
