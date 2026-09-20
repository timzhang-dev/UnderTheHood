"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import CodePanel from "@/components/CodePanel";
import ExecutionControls from "@/components/ExecutionControls";
import ExplanationPanel from "@/components/ExplanationPanel";
import HeapView from "@/components/HeapView";
import StackView from "@/components/StackView";
import StdoutPanel from "@/components/StdoutPanel";
import { visualize } from "@/lib/api";
import { buildColorMap } from "@/lib/colors";
import { EXAMPLES } from "@/lib/examples";
import type { Step, VisualizeResponse } from "@/lib/types";

// Preloaded so the page is usable on arrival — this is the flagship lesson.
const INITIAL = EXAMPLES.find((e) => e.id === "array_aliasing") ?? EXAMPLES[0];

export default function Home() {
  const [code, setCode] = useState(INITIAL.source);
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [current, setCurrent] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Colours are assigned once per trace, never per step, so an object keeps its
  // identity as the heap grows around it.
  const colors = useMemo(() => buildColorMap(steps ?? []), [steps]);
  const step = steps?.[current];

  const onVisualize = useCallback(async (source: string) => {
    setLoading(true);
    setNotice(null);
    try {
      const result: VisualizeResponse = await visualize(source);
      if (result.status === "ok") {
        setSteps(result.steps);
        setCurrent(0);
      } else {
        setSteps(null);
        setNotice(result.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const goPrevious = useCallback(
    () => setCurrent((i) => Math.max(0, i - 1)),
    [],
  );
  const goNext = useCallback(
    () => setCurrent((i) => Math.min((steps?.length ?? 1) - 1, i + 1)),
    [steps],
  );

  // Arrow keys are how anyone actually steps through an execution.
  useEffect(() => {
    if (!steps) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrevious();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps, goNext, goPrevious]);

  // ---------------------------------------------------------------- stepping
  if (steps && step) {
    return (
      <main className="mx-auto max-w-6xl px-4 py-8">
        <header className="mb-6 flex items-center justify-between gap-4">
          {/* Monospace wordmark: the product's whole subject is program state,
              and the mono face is where its personality lives. */}
          <h1 className="font-mono text-[15px] font-semibold tracking-tight text-ink">
            ExplainMyCode
          </h1>
          <button
            onClick={() => setSteps(null)}
            className="btn btn-secondary px-3 py-1.5 text-[13px]"
          >
            <span aria-hidden>←</span> Edit code
          </button>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          <CodePanel source={code} activeLine={step.line} />
          <div className="space-y-5">
            <StackView frames={step.stackFrames} colors={colors} changed={step.changed} stepKey={current} />
            <HeapView heap={step.heap} colors={colors} changed={step.changed} stepKey={current} />
          </div>
        </div>

        <div className="my-6">
          <ExecutionControls
            current={current}
            total={steps.length}
            onPrevious={goPrevious}
            onNext={goNext}
          />
          <p className="mt-2.5 flex items-center justify-center gap-1.5 text-center text-xs text-ink-faint">
            Use <kbd className="kbd">←</kbd> and <kbd className="kbd">→</kbd> to step
          </p>
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ExplanationPanel text={step.explanation} />
          </div>
          <StdoutPanel lines={step.stdout} />
        </div>
      </main>
    );
  }

  // ------------------------------------------------------------------ input
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-[-0.02em] text-ink sm:text-[2.5rem] sm:leading-[1.1]">
        See what your Java code is actually doing.
      </h1>
      <p className="mt-3.5 max-w-xl text-[15px] leading-relaxed text-ink-muted">
        Step through your code and visualize variables, objects, references,
        arrays, and memory.
      </p>

      <div className="mt-8">
        <label htmlFor="code" className="sr-only">
          Java code
        </label>
        <textarea
          id="code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          spellCheck={false}
          rows={14}
          className="w-full resize-y rounded-[10px] border border-line bg-surface p-4 font-mono text-[13px] leading-6 text-ink shadow-sm transition
                     placeholder:text-ink-faint focus:border-accent-line focus:outline-none focus:ring-2 focus:ring-accent/20"
        />
      </div>

      {notice && (
        <div className="mt-4 rounded-[10px] border border-danger-line bg-danger-soft px-4 py-3 text-sm leading-relaxed text-danger">
          {notice}
        </div>
      )}

      <button
        onClick={() => onVisualize(code)}
        disabled={loading || code.trim().length === 0}
        className="btn btn-primary mt-4 w-full px-5 py-2.5 font-semibold sm:w-auto"
      >
        {loading ? "Working…" : "Visualize Code"}
      </button>

      <section className="mt-12">
        <h2 className="label flex items-center gap-3">
          Examples
          <span className="label-rule" aria-hidden />
        </h2>
        <div className="mt-3.5 grid gap-3 sm:grid-cols-2">
          {EXAMPLES.map((example) => (
            <button
              key={example.id}
              onClick={() => {
                setCode(example.source);
                setNotice(null);
              }}
              className="group rounded-[10px] border border-line bg-surface p-4 text-left transition duration-150
                         hover:-translate-y-px hover:border-line-strong hover:shadow-[0_2px_8px_-2px_rgb(21_21_28_/_0.10)]
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/35"
            >
              <span className="block text-sm font-semibold text-ink transition-colors group-hover:text-accent">
                {example.title}
              </span>
              <span className="mt-1 block text-xs leading-relaxed text-ink-muted">
                {example.teaches}
              </span>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
