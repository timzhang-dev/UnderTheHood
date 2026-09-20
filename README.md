# UnderTheHood

**See what your Java code is actually doing.**

**Live:** https://tryunderthehood.vercel.app/

ExplainMyCode helps beginner Java students understand program execution. Paste a small Java
program, click **Visualize Code**, and step through it line by line while the page shows the
stack, the heap, references between them, arrays, stdout, and a short explanation of each step.

It is built to make reference semantics obvious. After

```java
int[] a = {1, 2, 3};
int[] b = a;
b[0] = 10;
```

you see two stack variables pointing at **one** array on the heap, and both of them see the `10`.

## How it works

```text
Java source
    ↓
FastAPI backend ── cheap prechecks (size, has a main method)
    ↓
Claude (claude-opus-5) with strict structured output
    ↓
schema validation (Pydantic) + semantic validator
    ↓  (on failure: one repair attempt with the validator's errors, then decline)
execution trace JSON
    ↓
Next.js frontend renders one step at a time
```

The frontend never reads free-form model text. The model must return JSON matching the trace
schema in `backend/app/models/execution.py`, and `backend/app/services/validator.py` checks
things a schema can't, such as heap objects keeping stable ids, types and array lengths across
steps, and stdout only ever growing. A trace that still fails after one repair attempt comes
back as `unsupported` instead. A wrong trace would teach a student something false.

The four built-in examples (primitive copy, reference aliasing, array aliasing, independent
objects) are served from golden fixtures in `fixtures/`, so they load instantly and never call
the model.

## What it supports

Supported:

- primitives and `String`, with arithmetic, comparison, boolean and concatenation expressions
- classes with fields and constructors, `new`
- one-dimensional arrays (`int[]`, `String[]`, `MyData[]`, …)
- reference assignment, aliasing, `null`
- `System.out.println`
- `if`/`else`, `for`, `while`, `break`, `continue`
- static methods and instance methods declared in the same file

Not supported (you get an `unsupported` response that names the feature): generics and
collections, lambdas/streams, inheritance and interfaces, multi-dimensional arrays, library
calls other than `println`, `switch`, for-each, `try`/`catch`, user input, multiple files.
Programs need a `main` method and must finish within 60 steps. The prompt lists the exact
scope in `backend/app/prompts/execution_trace.py`.

## Repository layout

```text
frontend/            Next.js 16 + React 19 + Tailwind 4 (TypeScript)
  app/page.tsx         landing page, editor, examples, visualization
  components/          StackView, HeapView, ObjectCard, ArrayCard, CodePanel, ...
  lib/api.ts           the single call to POST /api/visualize
  lib/types.ts         TypeScript mirror of the trace schema
backend/             FastAPI + Pydantic (Python 3.11+, managed with uv)
  app/models/          trace schema (the API contract)
  app/prompts/         system prompt and repair message
  app/services/        llm.py (Anthropic API), trace_generator.py, validator.py
  app/routes/          POST /api/visualize
  evals/               trace eval against JVM ground truth
  tests/
fixtures/            golden traces for the built-in examples
```

## Running locally

**Backend** (needs [uv](https://docs.astral.sh/uv/) and an Anthropic API key):

```bash
cd backend
cp .env.example .env        # then set ANTHROPIC_API_KEY
uv run --env-file .env uvicorn app.main:app --reload    # http://localhost:8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

The frontend calls `http://localhost:8000` by default. Point it elsewhere with
`NEXT_PUBLIC_API_URL`.

## API

`POST /api/visualize`

```json
{ "language": "java", "code": "public class Main { public static void main(String[] args) { int x = 5; } }" }
```

It returns `200` with either `{"status": "ok", "steps": [...]}` or
`{"status": "unsupported", "message": "...", "unsupportedFeatures": [...]}`. If the model
service itself fails (no key, rate limit, network), it returns `503` with a `detail` message.
`GET /api/health` returns `{"status": "ok"}`.

## Testing

```bash
cd backend && uv run pytest          # schema, validator, generator, route, eval harness
cd frontend && npm test              # vitest: API client and visualization components
cd frontend && npm run typecheck && npm run lint
```

The backend tests use a fake model client and don't need an API key.

### Trace eval

`backend/evals/` measures real model output. The expected stdout, exceptions and compile errors
come from running each program on a real JVM (`evals/gold.json`), not from the model. The eval
also checks structural facts such as aliasing and heap size, and checks that out-of-scope
programs get declined.

```bash
cd backend
uv run python -m evals.run --dry-run                 # show the plan, no API calls
uv run --env-file .env python -m evals.run           # run the full set
```

Current baseline: **35/36 cases correct (97%) on `claude-opus-5`**. The metric definitions are
in `.claude/hillclimb/tracing/metrics.md`.

## Deployment

Both apps are deployed on Vercel as separate projects from this repo:

- **Frontend** (`frontend/`): https://tryunderthehood.vercel.app/. Set `NEXT_PUBLIC_API_URL`
  to the backend's URL. It is inlined at build time, so redeploy after changing it.
- **Backend** (`backend/`): a Python function running `app/main.py` (`backend/vercel.json`,
  300 s max duration). Set `ANTHROPIC_API_KEY`, plus `CORS_ORIGINS=https://tryunderthehood.vercel.app`
  so the browser is allowed to call it. `backend/.vercelignore` keeps tests, evals and `.env` out
  of the bundle.
