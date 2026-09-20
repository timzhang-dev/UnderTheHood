"use client";

export default function ExecutionControls({
  current,
  total,
  onPrevious,
  onNext,
}: {
  current: number;
  total: number;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const atStart = current === 0;
  const atEnd = current === total - 1;

  return (
    <div className="flex items-center justify-center gap-3">
      <button
        className="btn btn-secondary px-3.5 py-2"
        onClick={onPrevious}
        disabled={atStart}
      >
        <span aria-hidden>←</span> Previous
      </button>
      {/* Tabular numerals so the counter does not twitch as the step advances. */}
      <span className="min-w-28 text-center font-mono text-xs tabular-nums text-ink-muted">
        Step <strong className="font-semibold text-ink">{current + 1}</strong>
        <span className="mx-0.5 text-ink-faint">/</span>
        {total}
      </span>
      <button
        className="btn btn-secondary px-3.5 py-2"
        onClick={onNext}
        disabled={atEnd}
      >
        Next <span aria-hidden>→</span>
      </button>
    </div>
  );
}
