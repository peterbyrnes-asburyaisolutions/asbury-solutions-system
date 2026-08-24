# Running 15 Agents in Production

**Asbury Solutions** runs its business on one machine: fifteen specialized
agents that take real tasks, run them as real processes, and report real
results back into a task ledger. This document is the engineering truth of how
that fleet stays honest — the contracts that make it safe to let software
operate a company, and the exact ways it refuses to lie to us.

It is written in plain words on purpose. The principles are not complicated.
The discipline is.

---

## The one rule: nothing reports done that did not finish

Every design decision in this system hangs off a single sentence: **an agent
may never report success it did not earn.** A task that runs and fails is a
failure. A task that runs and returns nothing is a failure. A task that never
runs because the plan was empty is a failure. There is no path from "nothing
happened" to "completed".

This is not a nice-to-have. The entire value of an autonomous fleet is that it
frees a person from watching every step. That only works if the absence of a
watchdog is not mistaken for the absence of a problem. So the contract is
enforced in code, in three places:

1. **The planner** refuses to emit an empty plan. If a task cannot be broken
   into at least one real step, that is an error, not a no-op.
2. **The runner** fails loud: any step that errors, times out, or returns
   nothing marks the whole run failed and exits non-zero.
3. **The ledger** records the outcome — `completed` only when every step
   finished, `failed` otherwise. The recorded state is what operators and
   other agents trust, and it cannot be produced by a silent skip.

We proved this with a test that forces the failure: give the planner a task
that yields an empty plan, and the run must exit non-zero and the ledger must
say `failed`. It does. The test lives in the eval harness
([`examples/evals/`](../examples/evals/)) so it keeps proving it.

---

## Timeouts: every step has a ceiling

An autonomous agent with no timeout is a leaky faucet — it will happily spend
your entire morning on a task that should take ninety seconds. So every step
in every run carries a timeout, resolved by a single rule with four rungs,
most specific first:

1. **Explicit per-step value** — the task itself says how long it may take.
   This always wins.
2. **Environment override** — an operator can raise or lower the global
   ceiling for a whole run without touching code.
3. **Step-type default** — long-tail work (build, research, write) gets long
   headroom; quick work (verify, check, probe) stays tight.
4. **Base default** — the safety floor if nothing else applies.

When a step exceeds its ceiling it is killed — not asked nicely, killed — and
the run is marked failed. The lesson here came from production: a build step
was being cut off at the generic base ceiling, long before it had a chance to
finish, and the run reported a false failure. The fix was the resolution rule
above: *explicit beats default, and the right default for the work is applied
before anything runs.* No silent 600-second assumption.

---

## Evals: how we know an agent works before it ships

"Looks right" is not a test. Before any agent behavior ships, it must pass a
three-layer harness ([`examples/evals/`](../examples/evals/)):

1. **Golden datasets** — a frozen set of labeled (input, expected) pairs the
   behavior must reproduce. Frozen matters: a dataset that changes between
   runs proves nothing.
2. **Regression suites** — deterministic exact checks that must keep passing.
   Green today must mean the same behavior as green last week. If behavior
   intentionally changes, the golden labels change in the same commit as the
   code — never silently.
3. **LLM-as-judge** — for outputs that cannot be exact-matched (summaries,
   style, reasoning), a rubric-scored grader issues a verdict. Two rules:
   penalize hallucination hard, and remember a judge is still a model — judge
   results are spot-checked, and high-stakes behavior always pairs a judge
   score with a deterministic check.

The harness exits non-zero on any failure. An empty golden set is an error,
not a pass. There is no "all green with nothing run" state.

---

## Guardrails: what an agent may and may not do

Autonomy without boundaries is just chaos with a nice interface. Every agent
runs inside explicit guardrails:

- **A fixed roster.** The fleet is a frozen tuple in code: fifteen seats, each
  with an identity, a memory, a tool allow-list, and a responsibility. The
  planner, dispatcher, and name resolution all read the same roster, so they
  always agree on who exists. (See [ADR-0001](decisions/0001-real-seats-not-roleplay.md).)
- **A single auth source.** All seats resolve credentials from one shared
  location at runtime. No per-seat keys to leak, to rotate, or to lose track
  of. (See [ADR-0003](decisions/0003-single-auth-source.md).)
- **No Docker for the runtime.** The fleet runs natively as service units on
  one Linux host — single-machine by design, no container indirection between
  the agent and the thing it operates. (See [ADR-0006](decisions/0006-no-docker-org-runtime.md).)
- **A secret sweep before any public surface.** Nothing ships to the public
  repository until a scanner
  ([`tools/secret_sweep.py`](../tools/secret_sweep.py)) confirms the tree is
  clean of credentials, addresses, and denied terms. What this repository
  shows is real; what it *doesn't* show is deliberate
  ([`docs/sanitization.md`](sanitization.md)).

---

## What this repository is for

This repository is the public, sanitized face of a production system. It shows
the architecture, the decisions, and the patterns — the *how* of running a
fleet of agents that a person can trust. It does not show where the system
lives, who it serves, what it holds, or how to reach it. The line is simple:
**show how it works, never where it is.**

Everything here is real and running — the live status badges on the README
probe the public endpoints every time the page loads. But nothing here is
operationally sensitive, because a public architecture document is valuable
precisely because anyone can open it.

---

## Never ship before verified

The last sentence of the rulebook: **never ship before verified.** A green
result is only trustworthy if the checks are frozen, deterministic, and fail
loud — and even then, the human sees the diff before anything goes out. This
document, the decisions in `docs/decisions/`, and the examples in
`examples/` exist so the bar is visible, not assumed.

Fifteen agents, one machine, one rule: nothing reports done that did not
finish. Everything else is detail.

— **Asbury Solutions**, engineering · plain words, real systems, zero fabrication.
