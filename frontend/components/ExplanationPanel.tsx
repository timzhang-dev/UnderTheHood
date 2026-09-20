export default function ExplanationPanel({ text }: { text: string }) {
  return (
    // The one place the product speaks in plain English, so it gets the accent
    // rail and slightly larger type — it is the teacher's voice, not chrome.
    <section className="panel relative h-full">
      <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-accent/70" />
      <div className="px-4 py-3.5">
        <h3 className="label mb-2">What just happened</h3>
        {/* Keyed on the text so each step's explanation fades in rather than
            swapping silently under the reader's eye. */}
        <p key={text} className="step-fade text-[13.5px] leading-relaxed text-ink">
          {text}
        </p>
      </div>
    </section>
  );
}
