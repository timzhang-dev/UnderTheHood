export default function StdoutPanel({ lines }: { lines: string[] }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Output
      </h3>
      <div className="min-h-14 rounded-lg border border-slate-800 bg-slate-900 p-3">
        {lines.length === 0 ? (
          <p className="font-mono text-xs text-slate-500">
            (nothing printed yet)
          </p>
        ) : (
          <ul className="space-y-0.5">
            {lines.map((line, i) => (
              <li key={i} className="font-mono text-xs text-emerald-300">
                {line}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
