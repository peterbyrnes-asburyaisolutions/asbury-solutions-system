# Post-mortem lessons — what I'd do differently

**Asbury Solutions** · honest post-mortems from running autonomous agents ·
plain words, real incidents, no names and no addresses (see
[sanitization.md](sanitization.md)).

The systems that survive are not the ones that never break. They are the ones
that break, get fixed, and get *better because of it*. Every incident below
left a permanent change in the operating system — a new rule, a new guard, a
new decision. This document is the honest account: what happened, what we
changed, and what we would do differently if we started over.

Post-mortems here are treated as data, not ceremony. They get written down,
filed with the incident, and read by the next person who hits the same wall.

---

## Lesson 1 — A flapping probe looks like everything is fine (and is the worst lie of all)

**What happened.** A service health probe started alternating — up, down, up,
down — within the span of a few minutes. To a naive monitor, that read as a
healthy service with an occasional blip. It was not a blip. It was a real,
intermittent failure that the monitoring was actively hiding.

The danger is subtle and it's worth saying plainly: **a flapping probe is
worse than a down probe.** A down probe makes you look. A flapping probe makes
you feel safe — "it recovered on its own" — while the underlying instability
keeps happening underneath you.

**What we changed.**

- A single transient failure is **logged, not acted on**. The rule is: never
  auto-execute on one blip. It is the *second consecutive* failure that
  triggers action. This is what stops a flapper from causing a cascade of
  pointless restarts.
- A probe that alternates up/down is reported as a **symptom**, never as a
  pass. "It came back" is not the same as "it's healthy."
- Every remediation is its own small task with its own verification — no
  shotgun restarts.

**What I'd do differently.** I'd have built the "flapper" classification into
the watchdog on day one, instead of after the incident taught us it was
needed. The fix wasn't complicated — it was *deciding that a flapping probe
is a finding*. That decision should have been made before we needed it, not
because a flapper burned us.

**Permanent change:** ADR-0002 (fail loud) applies to monitoring itself. A
monitor that can't tell a flapper from an outage is failing silently — the
one thing the whole system is built to never do. See also
[day-in-the-life.md](day-in-the-life.md), Flow 4.

---

## Lesson 2 — One timeout for every job is wrong in both directions

**What happened.** The first version gave every dispatched step the same
timeout. That was wrong twice over:

- **Long steps got chopped off mid-run.** A multi-step build that was 90%
  done hit the ceiling and died. The work was real, the timeout was wrong,
  and we lost the whole run.
- **Quick steps wasted their entire budget.** A fast verification step sat
  there "thinking" for the full timeout doing nothing, because a fast task
  never got to say "I'm fast."

A single number can't be right for a 15-minute build *and* a 5-second check.
Treating them the same didn't just waste time — it produced failures that
were completely avoidable.

**What we changed.** Every step now gets a timeout that is actually right for
the job, resolved in a fixed, deterministic order:

1. The step can ask for its own number — that always wins.
2. Otherwise, an override for the whole run.
3. Otherwise, a default by step type — builds, research, and writing get room
   to breathe; quick verify and reply steps get a short leash.
4. Otherwise, a base default, so there is never no answer.

And the rule on top: a step that blows its budget is **killed and surfaced**.
It does not hang around looking like it's thinking. A hung agent is worse
than a failed agent — a hang looks like progress. ([ADR-0004](decisions/0004-task-appropriate-timeouts.md))

**What I'd do differently.** Timeouts should be a property of the *type of
work*, designed when the step types were designed — not bolted on after a
long build died. I'd make "what timeout does this kind of work deserve?" part
of the initial contract, not an incident-driven patch.

**Permanent change:** the timeout resolution ladder in ADR-0004.

---

## Lesson 3 — Scattered secrets are a slow leak you don't notice until it matters

**What happened.** At one point, seats resolved their credentials the
convenient way: each agent had its own key, tucked into its own profile. It
worked. Nothing leaked. And that's exactly why it was dangerous — scattered
keys are a **leak surface that grows silently**.

- Every new seat meant another copy of a credential.
- Rotation meant finding *every* place the key had been copied — a hunt, not
  a command.
- The blast radius of any single leak was one more than it needed to be.

**What we changed.** All seats now resolve their model credential from a
**single shared auth source** — the same one the interactive client uses. No
per-seat keys. One thing to protect. One thing to rotate. A leaked per-seat
token cannot exist, because per-seat tokens no longer exist.
([ADR-0003](decisions/0003-single-auth-source.md))

**What I'd do differently.** The cost of the shared-source design was small;
the cost of the scattered design was invisible until it was too late. I'd
have made the single auth source the *only* option from the start, because
the "convenient" path looked fine right up until it was the thing that
mattered.

**Permanent change:** one door for secrets (ADR-0003), enforced by the
pre-publish secret sweep in [tools/](../tools/) — anything credential-shaped
fails the gate.

---

## Lesson 4 — "Nothing ran" must not look like "completed"

**What happened.** The foundational incident. A task was recorded as
`completed` even though its plan was empty — nothing had actually run. The
ledger told a prettier story than reality. In a normal company you'd notice
the worker with empty hands claiming done; in software, a ledger that says
"completed" looks exactly like a worker who finished.

This is the one that started everything. If the system's record of what
happened is allowed to lie, then every decision built on that record is
poisoned — and you won't find out until a customer asks why nothing shipped.

**What we changed.**

- An empty plan or zero successful steps raises an error, exits non-zero, and
  the ledger records `failed`. **There is no path from "nothing ran" to
  "completed."** ([ADR-0002](decisions/0002-fail-loud.md))
- We built a test that forces it: the harness tries to run an empty plan and
  expects it to die non-zero. If that test ever starts passing, the system is
  broken — and we want to know right then.

**What I'd do differently.** I'd have started from this rule instead of
arriving at it through an incident. "Nothing reports done that didn't finish"
is not a feature; it is the contract the whole system stands on. Everything
else — the timeouts, the evals, the watchdogs, the pre-publish gate — is
defense in depth around that one line.

**Permanent change:** ADR-0002, enforced at runtime *and* in the eval harness
([examples/evals/](../examples/evals/)).

---

## Lesson 5 — Two overlapping systems is not redundancy, it's two sources of truth

**What happened.** At one point there were two overlapping implementations of
the same swarm idea. It was exactly as dumb as it sounds: two codebases, two
ways of dispatching, two ideas of what "the fleet" meant. They disagreed,
quietly, and every disagreement was a bug waiting for someone to trip over
it.

**What we changed.** One orchestrator owns the fleet. Consolidation hurt once
and fixed it permanently — one codebase, one truth about who exists and who
does what. ([ADR-0005](decisions/0005-one-orchestrator.md))

**What I'd do differently.** I'd have recognized overlap as a liability the
moment the second implementation started, not after the two had diverged.
Duplication in dispatch logic is not resilience; it is a fork in the truth.

**Permanent change:** ADR-0005 — one orchestrator.

---

## What the incidents have in common

Read all five together and a pattern shows up:

1. **They were invisible by design.** The flapping probe *looked* healthy. The
   scattered keys *looked* fine. The empty-plan task *looked* completed. Every
   one of these incidents was a case of the system presenting a prettier story
   than reality.
2. **The fix in every case was the same shape:** make the truth loud and
   verifiable — log-before-act on blips, timeouts per task type, one shared
   auth source, fail-loud on empty plans, one orchestrator.
3. **None of the fixes was technically hard.** The hard part was deciding the
   rule. That's why the permanent changes are written down as decisions, not
   just patched into code — so the *reason* survives and the rule gets
   re-applied everywhere.

The honest summary: the systems that run autonomous agents don't fail on the
happy path. They fail when something is quietly wrong and nothing says so.
Every lesson here is an answer to that one failure mode. Say it out loud —
in the exit code, in the ledger, in the alert, in the post-mortem. Never
silently. Never prettier than reality.

---

**Asbury Solutions** · Plain words, real incidents, zero fabrication. The
changes above are recorded as decisions in
[docs/decisions/](decisions/) and enforced by the tooling in
[tools/](../tools/).
