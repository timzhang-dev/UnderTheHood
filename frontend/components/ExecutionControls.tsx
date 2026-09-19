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

  const button =
    "rounded-md border px-4 py-2 text-sm font-medium transition enabled:hover:bg-slate-50 " +
    "disabled:cursor-not-allowed disabled:opacity-40 border-slate-300 bg-white text-slate-700";

  return (
    <div className="flex items-center justify-center gap-4">
      <button className={button} onClick={onPrevious} disabled={atStart}>
        ← Previous
      </button>
      <span className="min-w-28 text-center text-sm tabular-nums text-slate-600">
        Step <strong className="text-slate-900">{current + 1}</strong> / {total}
      </span>
      <button className={button} onClick={onNext} disabled={atEnd}>
        Next →
      </button>
    </div>
  );
}
