# Examples — eval harness (non-secret)

How this organization knows an agent works **before** it ships.

A green result is only trustworthy if the checks are frozen, deterministic,
and fail loud. This example shows the three layers used for that, with
synthetic data only — no real clients, tasks, or credentials anywhere in this
directory (see [docs/sanitization.md](../../docs/sanitization.md)).

| File | What it shows |
|------|---------------|
| [`eval_harness.example.py`](eval_harness.example.py) | The harness itself: config validation, regression run, LLM-as-judge, and a fail-loud reporter. |
| [`golden.example.json`](golden.example.json) | A frozen golden dataset — labeled (input, expected) pairs the behavior must reproduce. |

## The three layers

### 1. Golden datasets
A frozen set of labeled cases. The behavior under test must reproduce the
expected label for every case. Freezing matters: a golden set that changes
between runs cannot prove anything. Every release pins the dataset it was
measured against.

### 2. Regression suites
Deterministic, exact checks that must keep passing. The point is
**stability**: green today must mean the same behavior as green last week.
If an intentional behavior change lands, the golden labels change *in the
same commit* as the code — never silently.

### 3. LLM-as-judge
For outputs that cannot be checked by exact match (summaries, style,
reasoning), a rubric-scored grader issues a verdict. Two rules apply:

- **Penalize hallucination hard** — any invented fact caps the score.
- **A judge is still a model** — judge results are spot-checked, and
  high-stakes behavior always pairs judge scores with a deterministic check.

## Fail-loud contract (ADR-0002)

The harness exits non-zero if any regression check fails or any judge verdict
falls below threshold. There is no path from "nothing ran" to "all green".
An empty golden dataset is treated as an error, not a pass — zero returned
with no alert is unacceptable.

## Config validation (no silent defaults)

Required inputs are declared in a resource manifest at the top of the file
and validated at import time. A missing file or a malformed golden row raises
`RuntimeError` with the offending case id instead of running with a wrong
default.

## How to run

```bash
# Python 3, no third-party dependencies, no credentials
python3 eval_harness.example.py
```

Exit code `0` = every check passed. Non-zero = regression or judge failure.

## Taking it from here

Copy `eval_harness.example.py`, then:

1. Replace the `triage_ticket` stand-in with a real seat/model call — keep the
   signature so the suite is unchanged.
2. Wire the `REPLACE:` block in `judge_case` to your own judge model call.
   Resolve credentials from the shared auth source at runtime (ADR-0003) —
   never commit keys.
3. Swap `golden.example.json` for your own frozen labeled dataset.

---

**Asbury Solutions** · Generic example, zero real data.
