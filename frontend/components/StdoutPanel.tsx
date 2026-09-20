export default function StdoutPanel({ lines }: { lines: string[] }) {
  return (
    <section>
      <h3 className="label mb-2 flex items-center gap-3">
        Output
        <span className="label-rule" aria-hidden />
      </h3>
      {/* The only dark surface in the product. It earns that by being the one
          thing that is literally a terminal — the program talking back. */}
      <div className="min-h-16 rounded-[10px] border border-term-line bg-term-bg px-3.5 py-3">
        {lines.length === 0 ? (
          <p className="font-mono text-xs text-ink-muted">(nothing printed yet)</p>
        ) : (
          <ul className="space-y-1">
            {lines.map((line, i) => (
              <li
                key={i}
                className="step-fade font-mono text-xs leading-5 text-term-text"
              >
                {line}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
