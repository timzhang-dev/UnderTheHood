# UnderTheHood

# ExplainMyCode — 4–7 Day MVP

You are helping us build a small but polished MVP called **ExplainMyCode**.

We are a team of 3 developers and want to build, deploy, and test this with real users within **4–7 days**.

The product helps beginner Java students understand program execution visually.

The core experience is:

> Paste a small Java program → AI converts it into a structured execution trace → user steps through execution line-by-line → UI visualizes variables, stack/heap state, references, arrays, and explanations.

This is NOT intended to be a full Java interpreter, debugger, IDE, or production-scale platform.

The most important goal is to ship a focused, working MVP quickly.

---

# 1. Product Goal

Beginner Java students often struggle to mentally understand:

* primitive values
* references
* objects
* aliasing
* arrays
* assignment
* mutation
* stack vs heap
* basic method execution

For example:

```java
int[] a = {1, 2, 3};
int[] b = a;
b[0] = 10;

System.out.println(a[0]);
```

A beginner may think `b = a` copies the array.

ExplainMyCode should make it visually obvious that both variables point to the same object.

The user should be able to step through the program and see:

```text
STACK                    HEAP

a ────────────────┐
                  ├────→ [1, 2, 3]
b ────────────────┘
```

Then after:

```java
b[0] = 10;
```

the heap visualization becomes:

```text
STACK                    HEAP

a ────────────────┐
                  ├────→ [10, 2, 3]
b ────────────────┘
```

The product should teach through execution rather than simply generating a textual explanation.

---

# 2. MVP Scope

## Required

The MVP must support small Java snippets involving:

* primitive variable declarations
* primitive assignments
* reference variables
* simple object creation
* object fields
* reference assignment / aliasing
* arrays
* array mutation
* simple arithmetic
* `System.out.println`
* sequential execution

If reasonably achievable during the week, also support:

* simple methods
* simple `if` statements
* simple `for` / `while` loops

These are secondary.

## Explicitly Out of Scope

Do NOT attempt to build support for:

* arbitrary Java programs
* multiple source files
* external libraries
* full Java language semantics
* generics
* concurrency
* complex inheritance
* complex polymorphism
* reflection
* JVM bytecode
* package management
* arbitrary GitHub repositories
* production-scale infrastructure
* microservices
* Kubernetes
* elaborate authentication/permissions
* a complete Java parser/interpreter unless absolutely necessary

We want a narrow product that works well.

---

# 3. Core User Flow

The main page should contain:

1. Product name and short explanation.
2. Java code editor/input area.
3. Several example programs users can load.
4. A **Visualize** button.

After clicking Visualize:

```text
Java code
   ↓
backend
   ↓
LLM
   ↓
structured execution trace
   ↓
frontend visualization
```

The user enters visualization mode.

The screen should roughly contain:

```text
-----------------------------------------------------
| CODE                     | PROGRAM STATE           |
|                          |                         |
| > MyData a = ...         | STACK       HEAP        |
|   MyData b = a;          |                         |
|   b.value = 5;           | a --------> Object #1   |
|                          |             value: 1    |
-----------------------------------------------------

       [ Previous ]   Step 1 / 3   [ Next ]

-----------------------------------------------------
Explanation:

A new MyData object was created. Variable `a`
stores a reference to this object.
-----------------------------------------------------
```

The currently executing line should be visually highlighted.

Users must be able to move:

* Next
* Previous

through the execution trace.

---

# 4. Architecture

Keep the architecture simple.

Preferred stack:

## Frontend

* Next.js
* TypeScript
* React
* Tailwind CSS

Responsibilities:

* code input/editor
* examples
* execution controls
* line highlighting
* stack visualization
* heap visualization
* references/arrows
* arrays
* explanation panel
* loading/error states

Do NOT spend significant time integrating a heavyweight IDE.

A textarea or lightweight code editor is acceptable for V1.

## Backend

Use:

* Python
* FastAPI
* Pydantic

Responsibilities:

* accept Java code
* construct LLM request
* request structured execution trace
* validate model response
* return normalized JSON
* handle malformed/unsupported programs gracefully

Example endpoint:

```http
POST /api/visualize
```

Request:

```json
{
  "language": "java",
  "code": "int x = 5;"
}
```

Response:

```json
{
  "steps": [...]
}
```

## Database

A database is NOT required for the initial core product.

Do not add PostgreSQL simply because it is common.

Only introduce persistence if we later implement saved/shareable visualizations or analytics requiring it.

---

# 5. Critical Design Principle

The frontend must NOT depend directly on natural-language LLM output.

The LLM should produce a strictly structured execution representation.

The frontend renders this representation.

Architecture:

```text
Java source
     ↓
LLM / execution-trace generator
     ↓
validated structured representation
     ↓
frontend renderer
```

This separation is important.

---

# 6. Execution Trace Schema

Design a clean TypeScript/Pydantic-compatible schema.

A conceptual version:

```json
{
  "steps": [
    {
      "step": 1,
      "line": 1,
      "source": "MyData a = new MyData(1);",
      "stackFrames": [
        {
          "name": "main",
          "variables": {
            "a": {
              "kind": "reference",
              "type": "MyData",
              "target": "obj_1"
            }
          }
        }
      ],
      "heap": {
        "obj_1": {
          "kind": "object",
          "type": "MyData",
          "fields": {
            "value": {
              "kind": "primitive",
              "type": "int",
              "value": 1
            }
          }
        }
      },
      "stdout": [],
      "explanation": "A new MyData object is created on the heap. Variable a stores a reference to it."
    }
  ]
}
```

This is only a starting point.

Improve the schema if necessary.

It should cleanly represent:

### Primitive

```json
{
  "kind": "primitive",
  "type": "int",
  "value": 5
}
```

### Reference

```json
{
  "kind": "reference",
  "type": "MyData",
  "target": "obj_1"
}
```

### Null

```json
{
  "kind": "reference",
  "type": "MyData",
  "target": null
}
```

### Object

```json
{
  "kind": "object",
  "type": "MyData",
  "fields": {}
}
```

### Array

```json
{
  "kind": "array",
  "type": "int[]",
  "elements": [
    {
      "kind": "primitive",
      "type": "int",
      "value": 1
    },
    {
      "kind": "primitive",
      "type": "int",
      "value": 2
    }
  ]
}
```

References must use stable object IDs so multiple variables can visibly point to the same heap object.

For example:

```text
a ──────┐
        ├────→ obj_1
b ──────┘
```

Do NOT duplicate `obj_1` in the representation merely because multiple variables reference it.

That would teach incorrect Java semantics.

---

# 7. LLM Behavior

The model's job is to transform a supported Java snippet into the execution trace.

The prompt sent to the model should strongly instruct it to:

1. Execute the code one meaningful step at a time.
2. Preserve correct Java reference semantics.
3. Distinguish primitive values from references.
4. Give every heap object a stable unique ID.
5. Preserve aliasing.
6. Track mutations.
7. Track array contents.
8. Track stdout.
9. Identify the corresponding source line.
10. Provide a concise beginner-friendly explanation for every step.
11. Return ONLY data matching the required structured schema.
12. Mark unsupported/ambiguous code rather than inventing behavior.

Use structured output / schema validation if supported by the selected model API.

Do not trust arbitrary model JSON without validation.

---

# 8. Visualization

The visualization is the core product.

Prioritize clarity over visual complexity.

## Stack

Show variables inside the current stack frame.

Example:

```text
STACK

main

x    5
name "Tim"

a    ────────────────→
b    ────────────────→
```

Primitive values should display directly.

References should visually connect to heap objects.

## Heap

Example:

```text
HEAP

┌─────────────────┐
│ obj_1 : MyData  │
│                 │
│ value     10    │
└─────────────────┘
```

For arrays:

```text
obj_2 : int[]

┌────┬────┬────┐
│ 10 │  2 │  3 │
└────┴────┴────┘
  0    1    2
```

## References

If:

```java
MyData a = new MyData(1);
MyData b = a;
```

the visualization MUST clearly communicate:

```text
a ─────┐
       ├────→ obj_1
b ─────┘
```

rather than rendering two objects.

Use a simple arrow/connection library if useful, or SVG/CSS if easier.

Do not introduce a huge visualization dependency unnecessarily.

---

# 9. Step Navigation

Maintain something equivalent to:

```typescript
const [currentStep, setCurrentStep] = useState(0);
```

The UI should render only the state associated with that execution step.

Controls:

```text
Previous       Step 3 / 8       Next
```

Disable Previous on first step.

Disable Next on final step.

When moving between steps:

* highlight the appropriate source line
* update stack
* update heap
* update stdout
* update explanation

Animations are optional.

Correctness and clarity matter more.

---

# 10. Example Programs

Ship several built-in examples.

## Primitive Copy

```java
int x = 5;
int y = x;
y = 10;

System.out.println(x);
System.out.println(y);
```

Purpose:

Teach that primitive assignment copies the value.

## Reference Aliasing

```java
MyData a = new MyData(1);
MyData b = a;

b.value = 5;

System.out.println(a.value);
```

Purpose:

Teach that reference assignment copies the reference.

## Array Aliasing

```java
int[] a = {1, 2, 3};
int[] b = a;

b[0] = 10;

System.out.println(a[0]);
```

Purpose:

Teach that arrays are objects referenced by variables.

## Independent Objects

```java
MyData a = new MyData(1);
MyData b = new MyData(1);

b.value = 5;

System.out.println(a.value);
```

Purpose:

Contrast two objects with two references to one object.

---

# 11. Educational Layer

For the initial 4-day version, explanations are sufficient.

If core functionality is working early, add prediction questions.

Before an interesting line executes:

```java
b.value = 10;
```

show:

> What do you think will happen?

For example:

```text
A. Only b.value becomes 10
B. Both a.value and b.value appear as 10
C. A new object is created
D. The program crashes
```

Then let the user execute the next step and visually discover the answer.

This is OPTIONAL until the core visualization works.

---

# 12. Error Handling

Handle unsupported input gracefully.

Never silently hallucinate an execution trace when confidence is low.

Possible response:

```json
{
  "status": "unsupported",
  "message": "This example uses Java features that ExplainMyCode V1 does not support yet.",
  "unsupportedFeatures": [
    "generics"
  ]
}
```

Frontend should display a useful message and suggest trying one of the built-in examples.

---

# 13. Testing

Correctness matters because this is an educational tool.

Create tests for at least:

* primitive assignment
* primitive reassignment
* one object reference
* two references to same object
* two references to different objects
* object field mutation
* array creation
* array aliasing
* array mutation
* null reference
* stdout tracking

For important examples, define expected invariants.

Example:

After:

```java
int[] a = {1, 2, 3};
int[] b = a;
```

assert:

```text
a.target === b.target
```

After:

```java
b[0] = 10;
```

assert:

```text
heap[a.target].elements[0].value === 10
```

Do not rely exclusively on visually inspecting model responses.

---

# 14. UX Requirements

Keep the UI clean and student-friendly.

Landing page should immediately communicate:

> **See what your Java code is actually doing.**

Possible subtitle:

> Step through your code and visualize variables, objects, references, arrays, and memory.

Main CTA:

> Visualize Code

Do not clutter the product with:

* dashboards
* accounts
* settings
* pricing
* social features
* elaborate navigation

The product should basically be:

```text
LANDING
   ↓
PASTE CODE
   ↓
VISUALIZE
   ↓
STEP THROUGH
```

---

# 15. Suggested Repository Structure

A monorepo is fine.

For example:

```text
explain-my-code/

  frontend/
    app/
    components/
      CodePanel.tsx
      ExecutionControls.tsx
      StackView.tsx
      HeapView.tsx
      ObjectCard.tsx
      ArrayCard.tsx
      ExplanationPanel.tsx
    lib/
      api.ts
      types.ts

  backend/
    app/
      main.py
      models/
        execution.py
      services/
        trace_generator.py
        llm.py
      prompts/
        execution_trace.py
      routes/
        visualize.py
    tests/

  README.md
```

Adjust this if there is a simpler organization.

Do not introduce architectural layers unless they serve an actual purpose.

---

# 16. Team-Friendly Development

Three people will work on this repository concurrently.

Keep boundaries clean enough that work can happen in parallel.

Suggested ownership:

### Developer A — Frontend visualization

Own:

* StackView
* HeapView
* ObjectCard
* ArrayCard
* reference visualization
* execution controls

### Developer B — AI/backend

Own:

* FastAPI
* execution schema
* model integration
* prompts
* validation
* tests

### Developer C — Product/integration

Own:

* Next.js application shell
* code input/editor
* example selector
* API integration
* loading/errors
* responsive layout
* deployment
* polish

Avoid unnecessary overlapping edits to the same files.

---

# 17. Development Order

Do NOT attempt to build everything at once.

Work in vertical slices.

## Milestone 1 — Static prototype

Before using an LLM, hard-code one execution trace for:

```java
int[] a = {1, 2, 3};
int[] b = a;
b[0] = 10;
```

Build the frontend capable of stepping through it.

Success means:

> We can visually demonstrate aliasing from a hard-coded trace.

## Milestone 2 — Schema

Finalize the execution trace schema.

Make frontend render arbitrary traces matching that schema.

## Milestone 3 — AI generation

Implement:

```text
Java → LLM → validated trace
```

Test against the built-in examples.

## Milestone 4 — End-to-end

Connect:

```text
paste Java
    ↓
Visualize
    ↓
API
    ↓
LLM
    ↓
trace
    ↓
interactive visualization
```

## Milestone 5 — Reliability

Test many beginner-level snippets.

Fix:

* incorrect aliasing
* malformed traces
* confusing explanations
* unsupported syntax
* UI edge cases

## Milestone 6 — Polish + deploy

Only after core behavior works:

* improve styling
* add examples
* add animations if easy
* improve loading state
* deploy

---

# 18. Definition of Done

The MVP is DONE when a student can visit the deployed website and, without help from us:

1. Paste a small supported Java program.
2. Click Visualize.
3. Receive a valid execution trace.
4. Step forward/backward through execution.
5. See the current source line.
6. See primitive variables.
7. See stack references.
8. See heap objects/arrays.
9. See multiple references pointing to the same object.
10. See mutations reflected correctly.
11. See stdout.
12. Read a concise explanation of each step.

The MVP does NOT need to understand arbitrary Java.

A narrow tool that correctly teaches reference semantics is better than a broad tool that occasionally lies.

---

# 19. Engineering Principles

While implementing:

* Prefer simple solutions.
* Do not overengineer.
* Avoid premature abstractions.
* Avoid dependencies unless they save meaningful development time.
* Keep modules understandable.
* Use strong typing.
* Validate all model-generated structured data.
* Make failures explicit.
* Keep API contracts clean.
* Write comments for non-obvious reasoning, not obvious syntax.
* Keep secrets server-side.
* Never expose model API keys to the frontend.
* Prioritize correctness over animation/polish.
* Prioritize shipping over architectural perfection.

We have only 4–7 days.

---

# 20. How I Want You to Work

Do NOT immediately generate the entire application.

First:

1. Inspect the current repository.
2. Tell me what already exists.
3. Propose the minimum architecture for this MVP.
4. Propose the execution-trace schema.
5. Break implementation into small milestones.
6. Identify any important technical decisions we need to make.
7. Identify anything in this specification that is unnecessarily ambitious for a 4–7 day build.

Then STOP and show me the plan.

Do not begin large-scale implementation until I approve the architecture.

Once approved, implement incrementally.

For every meaningful implementation step:

* explain what you're about to change
* keep the change scoped
* tell me which files were created/modified
* explain important design decisions
* run relevant tests/type checks
* report failures instead of hiding them

Most importantly:

**I want to understand the system we are building. Do not treat me as someone who only wants generated code.**

When there are multiple reasonable approaches, explain the tradeoff briefly and recommend the simplest approach appropriate for a 4–7 day MVP.

Start by inspecting the repository and proposing the architecture and execution-trace schema. Do not implement yet.
