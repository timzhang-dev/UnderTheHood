/**
 * Read-only source display with the executing line highlighted.
 *
 * Deliberately NOT a code editor. The input textarea and this panel are separate
 * components, which is what makes line highlighting a one-line change instead of
 * a CodeMirror integration.
 */
export default function CodePanel({
  source,
  activeLine,
}: {
  source: string;
  activeLine: number;
}) {
  const lines = source.split("\n");

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Code
      </div>
      <pre className="py-2 text-sm leading-6">
        {lines.map((line, i) => {
          const number = i + 1;
          const active = number === activeLine;
          return (
            <div
              key={number}
              className={`flex ${active ? "bg-amber-100" : ""}`}
              aria-current={active ? "step" : undefined}
            >
              <span
                className={`w-6 shrink-0 select-none text-center font-mono text-xs leading-6 ${
                  active ? "text-amber-700" : "text-transparent"
                }`}
                aria-hidden
              >
                ▶
              </span>
              <span className="w-8 shrink-0 select-none pr-3 text-right font-mono text-xs leading-6 text-slate-400">
                {number}
              </span>
              <code
                className={`whitespace-pre pr-4 font-mono ${
                  active ? "font-semibold text-slate-900" : "text-slate-700"
                }`}
              >
                {line || " "}
              </code>
            </div>
          );
        })}
      </pre>
    </div>
  );
}
