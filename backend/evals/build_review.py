"""Renders every eval case as one readable page, for the input sign-off.

  cd backend && uv run python -m evals.build_review

Output: .claude/hillclimb/tracing/inputs.html (opened in a browser; no server needed).
"""

from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path

from evals.build_gold import GOLD_PATH
from evals.cases import CASES, Case

OUT = Path(__file__).resolve().parents[2] / ".claude" / "hillclimb" / "tracing" / "inputs.html"
GOLD = json.loads(GOLD_PATH.read_text())

CATEGORY_TITLES = {
    "core": "Core: the reference-semantics lessons",
    "secondary": "Secondary: loops, branches, methods, recursion, crashes",
    "limits": "Limits: the 60-step cap",
    "decline": "Decline: things V1 does not support, and code that does not compile",
    "adversarial": "Adversarial: program text that tries to steer the model",
}

# Cases added since the draft the owner last reviewed, flagged so a re-review can skip the rest.
NEW_IN_LATEST_DRAFT = {"decline_late_unsupported"}

NOT_COVERED = [
    "`long` / `float` / `char` values and static fields.",
    "Constructs V1 should decline but has no case for: `switch`, `printf`, 2D arrays.",
    "Programs longer than ~40 lines, or with more than 3 classes.",
    "Real student programs. Every case here was written by Claude. Paste a few and they go in as-is.",
]


def badge(case: Case) -> str:
    if case.expect == "ok":
        return '<span class="b ok">must trace</span>'
    if case.expect == "exception":
        return f'<span class="b crash">must trace, then crash: {escape(case.exception)}</span>'
    return '<span class="b no">must decline</span>'


def code_block(source: str) -> str:
    rows = "".join(
        f'<span class="ln">{i:>2}</span>{escape(text)}\n' for i, text in enumerate(source.split("\n"), start=1)
    )
    return f"<pre>{rows}</pre>"


def expectations(case: Case) -> str:
    items = []
    if case.expect == "unsupported":
        if case.id == "decline_bare_snippet":
            items.append("Rejected by a deterministic check <b>before any model call</b> (free).")
        else:
            items.append("Must come back as an <code>unsupported</code> answer, <b>never a trace</b>.")
    else:
        items.append("Every step passes the semantic validator (ids resolve, aliasing consistent, stdout only grows).")
        items.append("Final output equals what the real JVM printed (below).")
        if case.expect == "exception":
            items.append(
                f"The trace <b>ends at line {case.fails_at_line}</b>, and that step's explanation names "
                f"<code>{escape(case.exception)}</code>."
            )
        items.extend(escape(f.describe()) for f in case.facts)
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def jvm_block(case: Case) -> str:
    gold = GOLD.get(case.id)
    if gold is None:
        return '<p class="dim">Not run on the JVM.</p>'
    if not gold["compiles"]:
        return f'<div class="jvm"><div class="crash-line">javac refuses to compile it:</div>{escape(gold["compile_error"])}</div>'
    out = "".join(f"<div>{escape(line)}</div>" for line in gold["stdout"]) or '<div class="dim">(no output)</div>'
    crash = f'<div class="crash-line">then died with {escape(gold["exception"])}</div>' if gold["exception"] else ""
    return f'<div class="jvm">{out}{crash}</div>'


def card(case: Case) -> str:
    note = f'<p class="note"><b>Note for you:</b> {escape(case.note)}</p>' if case.note else ""
    new = '<span class="b new">new</span>' if case.id in NEW_IN_LATEST_DRAFT else ""
    return f"""
<section class="case" id="{case.id}">
  <h3><code>{case.id}</code> {badge(case)}{new}</h3>
  <p class="why">{escape(case.why)}</p>
  {note}
  <div class="cols">
    <div>{code_block(case.source)}</div>
    <div>
      <h4>Real JVM output</h4>{jvm_block(case)}
      <h4>A correct answer must satisfy</h4>{expectations(case)}
    </div>
  </div>
</section>"""


def build() -> str:
    by_category = Counter(c.category for c in CASES)
    ok = sum(c.expect == "ok" for c in CASES)
    crash = sum(c.expect == "exception" for c in CASES)
    declined = sum(c.expect == "unsupported" for c in CASES)
    jdk = next(iter(GOLD.values()))["jdk"]
    counts = " &middot; ".join(f"{by_category[k]} {k}" for k in CATEGORY_TITLES)
    sections = "".join(
        f"<h2>{CATEGORY_TITLES[cat]}</h2>" + "".join(card(c) for c in CASES if c.category == cat)
        for cat in CATEGORY_TITLES
    )
    not_covered = "".join(f"<li>{escape(x)}</li>" for x in NOT_COVERED)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trace eval inputs (draft 3)</title>
<style>
:root {{ --bg:#fafafa; --card:#fff; --ink:#1a1a22; --dim:#6b6b76; --line:#e2e2ea; --code:#f3f3f7;
        --ok:#0a7d55; --okbg:#e6f6ef; --no:#b42318; --nobg:#fdecea; --crash:#a15c00; --crashbg:#fff4e0;
        --new:#4338ca; --newbg:#eceafd; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111116; --card:#191920; --ink:#ececf1; --dim:#9a9aa6;
        --line:#2b2b35; --code:#14141a; --ok:#5fd3a4; --okbg:#12261f; --no:#ff8a80; --nobg:#2c1513;
        --crash:#f3b45a; --crashbg:#2b2110; --new:#a5a0ff; --newbg:#1f1d3d; }} }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ margin:0 0 6px; font-size:26px; }} h2 {{ margin:44px 0 12px; font-size:19px; }}
h3 {{ margin:0 0 4px; font-size:15px; }} h4 {{ margin:14px 0 6px; font-size:12px; text-transform:uppercase;
        letter-spacing:.05em; color:var(--dim); }}
.sum {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 20px; margin:12px 0; }}
.sum li {{ margin:2px 0; }} .dim {{ color:var(--dim); }}
.case {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 20px; margin:14px 0; }}
.why {{ margin:0 0 12px; color:var(--dim); }}
.cols {{ display:grid; grid-template-columns:minmax(0,1.1fr) minmax(0,1fr); gap:20px; }}
@media (max-width:820px) {{ .cols {{ grid-template-columns:1fr; }} }}
pre {{ margin:0; padding:12px; background:var(--code); border-radius:8px; overflow:auto;
        font:12.5px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; }}
.ln {{ display:inline-block; width:2.2em; color:var(--dim); user-select:none; }}
code {{ font:12.5px ui-monospace,Menlo,monospace; }}
ul {{ margin:0; padding-left:18px; }} li {{ margin:3px 0; }}
.jvm {{ background:var(--code); border-radius:8px; padding:8px 12px; font:12.5px ui-monospace,Menlo,monospace; }}
.crash-line {{ color:var(--crash); margin-top:4px; }}
.b {{ font:600 11px system-ui; padding:2px 8px; border-radius:99px; margin-left:8px; vertical-align:1px; }}
.b.ok {{ color:var(--ok); background:var(--okbg); }} .b.no {{ color:var(--no); background:var(--nobg); }}
.b.crash {{ color:var(--crash); background:var(--crashbg); }} .b.new {{ color:var(--new); background:var(--newbg); }}
.note {{ background:var(--crashbg); color:var(--crash); border-radius:8px; padding:8px 12px; margin:0 0 12px; }}
</style></head><body><main>
<h1>Trace eval: proposed inputs <span class="dim">(draft 3, final candidate)</span></h1>
<p class="dim">For your review. Nothing has been run against the model yet.</p>

<div class="sum">
  <p><b>What changed since draft 2</b> (the case marked <span class="b new">new</span> below):</p>
  <ul>
    <li><b>Added one case:</b> <code>decline_late_unsupported</code>, supported code followed by a
      <code>switch</code>. It tests the no-partial-traces rule.</li>
    <li>Nothing else changed. Draft 2 already added instance-method support, the compile errors, the
      unsupported constructs, the recursion case and the orphaned-object case.</li>
    <li>No real student programs are included yet; there were none to add.</li>
  </ul>
</div>

<div class="sum">
  <p><b>{len(CASES)} cases</b>: {counts}.<br>
  <b>{ok + crash}</b> must produce a correct trace ({ok} run cleanly, {crash} crash by design).
  <b>{declined}</b> must be declined. {len(CASES) - 1} of the {len(CASES)} reach the model; the bare snippet is
  stopped by a free check.</p>
  <p><b>Where "correct" comes from.</b> Expected output is not model-written: {len(GOLD)} of the {len(CASES)}
  programs were run through a real JDK ({escape(jdk)}), and the two that must not compile were refused by its
  compiler. The programs themselves and the memory-picture facts were written by Claude, which is why you are
  reading them.</p>
  <p><b>What is not covered:</b></p><ul>{not_covered}</ul>
</div>
{sections}
</main></body></html>"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
