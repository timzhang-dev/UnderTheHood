export default function ExplanationPanel({ text }: { text: string }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
        What just happened
      </h3>
      <p className="text-sm leading-relaxed text-slate-700">{text}</p>
    </section>
  );
}
