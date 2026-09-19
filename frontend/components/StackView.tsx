import type { Changed, Frame } from "@/lib/types";
import type { HeapColor } from "@/lib/colors";
import ValueChip from "./ValueChip";

export default function StackView({
  frames,
  colors,
  changed,
}: {
  frames: Frame[];
  colors: Map<string, HeapColor>;
  changed: Changed | null;
}) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Stack
      </h3>
      <div className="space-y-3">
        {frames.map((frame, frameIndex) => (
          <div
            key={`${frame.name}-${frameIndex}`}
            className="rounded-lg border border-slate-200 bg-white"
          >
            <div className="border-b border-slate-200 bg-slate-50 px-3 py-1.5 font-mono text-xs font-semibold text-slate-600">
              {frame.name}
            </div>
            {frame.variables.length === 0 ? (
              <p className="px-3 py-2 text-xs italic text-slate-400">
                no variables yet
              </p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {frame.variables.map((variable) => {
                  const highlighted =
                    changed?.kind === "variable" &&
                    changed.frame === frameIndex &&
                    changed.name === variable.name;
                  return (
                    <li
                      key={variable.name}
                      className={`flex items-center justify-between gap-4 px-3 py-2 ${
                        highlighted ? "bg-amber-50 ring-1 ring-inset ring-amber-300" : ""
                      }`}
                    >
                      <span className="font-mono text-sm text-slate-700">
                        {variable.name}
                      </span>
                      <ValueChip value={variable.value} colors={colors} />
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
