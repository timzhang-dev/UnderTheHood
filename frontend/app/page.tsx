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
          <h1 className="text-lg font-semibold text-slate-900">ExplainMyCode</h1>
          <button
            onClick={() => setSteps(null)}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            ← Edit code
          </button>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          <CodePanel source={code} activeLine={step.line} />
          <div className="space-y-5">
            <StackView frames={step.stackFrames} colors={colors} changed={step.changed} />
            <HeapView heap={step.heap} colors={colors} changed={step.changed} />
          </div>
        </div>

        <div className="my-6">
          <ExecutionControls
            current={current}
            total={steps.length}
            onPrevious={goPrevious}
            onNext={goNext}
          />
          <p className="mt-2 text-center text-xs text-slate-400">
            Use ← and → to step
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
      <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
        See what your Java code is actually doing.
      </h1>
      <p className="mt-3 text-base text-slate-600">
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
          className="w-full resize-y rounded-lg border border-slate-300 bg-white p-4 font-mono text-sm leading-6 text-slate-800 shadow-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
        />
      </div>

      {notice && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {notice}
        </div>
      )}

      <button
        onClick={() => onVisualize(code)}
        disabled={loading || code.trim().length === 0}
        className="mt-4 w-full rounded-lg bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
      >
        {loading ? "Working…" : "Visualize Code"}
      </button>

      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Examples
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {EXAMPLES.map((example) => (
            <button
              key={example.id}
              onClick={() => {
                setCode(example.source);
                setNotice(null);
              }}
              className="rounded-lg border border-slate-200 bg-white p-4 text-left transition hover:border-slate-400 hover:shadow-sm"
            >
              <span className="block text-sm font-semibold text-slate-900">
                {example.title}
              </span>
              <span className="mt-1 block text-xs leading-relaxed text-slate-600">
                {example.teaches}
              </span>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
