import { TOKEN_CLASS, tokenize } from "@/lib/highlight";

/**
 * Read-only source display with the executing line highlighted.
 *
 * Deliberately NOT a code editor. The input textarea and this panel are separate
 * components, which is what makes line highlighting a one-line change instead of
 * a CodeMirror integration.
 *
 * The highlight is the accent colour and a solid gutter rail, because "where
 * execution is" is the single most important thing on this screen. Rows carry a
 * background transition so that stepping reads as the highlight *moving* down
 * the program rather than blinking from one place to another.
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
    <div className="panel">
      <div className="panel-head">
        <span className="label">Code</span>
      </div>
      <pre className="overflow-x-auto py-2 text-[13px] leading-6">
        {lines.map((line, i) => {
          const number = i + 1;
          const active = number === activeLine;
          return (
            <div
              key={number}
              className={`relative flex transition-colors duration-200 ease-out ${
                active ? "bg-accent-soft" : "bg-transparent"
              }`}
              aria-current={active ? "step" : undefined}
            >
              <span
                aria-hidden
                className={`absolute inset-y-0 left-0 w-[2px] transition-colors duration-200 ${
                  active ? "bg-accent" : "bg-transparent"
                }`}
              />
              <span
                className={`w-10 shrink-0 select-none border-r border-line/70 pr-2.5 text-right font-mono text-[11px] leading-6 tabular-nums transition-colors duration-200 ${
                  active ? "font-semibold text-accent" : "text-ink-faint"
                }`}
              >
                {number}
              </span>
              <code className="whitespace-pre pl-3 pr-4 font-mono">
                {line
                  ? tokenize(line).map((token, t) => (
                      <span key={t} className={TOKEN_CLASS[token.kind]}>
                        {token.text}
                      </span>
                    ))
                  : " "}
              </code>
            </div>
          );
        })}
      </pre>
    </div>
  );
}
