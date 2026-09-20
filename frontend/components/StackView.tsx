import type { Changed, Frame } from "@/lib/types";
import type { HeapColor } from "@/lib/colors";
import ValueChip from "./ValueChip";

/**
 * `stepKey` is a rendering detail, not data: it is folded into the React key of
 * a highlighted row so that row remounts when the step changes, which is what
 * re-fires the mutation flash. Without it, CSS would consider the animation
 * already played and a second write to the same variable would flash nothing.
 */
export default function StackView({
  frames,
  colors,
  changed,
  stepKey = 0,
}: {
  frames: Frame[];
  colors: Map<string, HeapColor>;
  changed: Changed | null;
  stepKey?: number;
}) {
  return (
    <section>
      <h3 className="label mb-2 flex items-center gap-3">
        Stack
        <span className="label-rule" aria-hidden />
      </h3>
      <div className="space-y-2.5">
        {frames.map((frame, frameIndex) => {
          // The last frame is the one executing; giving it the accent keeps
          // "where are we?" answerable without reading any text.
          const executing = frameIndex === frames.length - 1;
          return (
            <div
              key={`${frame.name}-${frameIndex}`}
              className={`panel ${executing ? "border-accent-line" : ""}`}
            >
              <div
                className={`flex items-baseline gap-2 border-b px-3.5 py-1.5 font-mono text-xs ${
                  executing
                    ? "border-accent-line bg-accent-soft/70 text-accent-ink"
                    : "border-line bg-sunken/70 text-ink-muted"
                }`}
              >
                <span className="font-semibold">{frame.name}</span>
              </div>
              {frame.variables.length === 0 ? (
                <p className="px-3.5 py-2.5 text-xs italic text-ink-faint">
                  no variables yet
                </p>
              ) : (
                <ul className="divide-y divide-line/70">
                  {frame.variables.map((variable) => {
                    const highlighted =
                      changed?.kind === "variable" &&
                      changed.frame === frameIndex &&
                      changed.name === variable.name;
                    return (
                      <li
                        key={
                          highlighted
                            ? `${variable.name}@${stepKey}`
                            : variable.name
                        }
                        className={`flex items-center justify-between gap-4 px-3.5 py-2 ${
                          highlighted
                            ? "flash bg-mutation-soft ring-1 ring-inset ring-mutation-line"
                            : ""
                        }`}
                      >
                        <span className="font-mono text-[13px] text-ink-muted">
                          {variable.name}
                        </span>
                        <ValueChip value={variable.value} colors={colors} />
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
