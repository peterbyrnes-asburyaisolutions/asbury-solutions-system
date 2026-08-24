# A day in the life — running 15 agents

What a real day looks like when fifteen specialized seats run on one machine.
This document describes the **shape** of the work — the flows, the gates, and
the failure modes — not the content. No client names, no task data, no live
endpoints, no personal details appear here (see
[docs/sanitization.md](sanitization.md)).

The cast, by role (seats resolve to real, isolated agent processes; see
[`0001-real-seats-not-roleplay.md`](decisions/0001-real-seats-not-roleplay.md)):

- **Scheduler / kernel** — owns the work queue, fires due tasks, retries, clears stale work.
- **Planner / orchestrator** — turns one task into ordered steps (single orchestrator; see [`0005-one-orchestrator.md`](decisions/0005-one-orchestrator.md)).
- **Dispatcher** — launches each step as a real seat subprocess, enforces timeouts.
- **Engineering / DevOps** — build and ship the artifacts.
- **Research** — gathers and cites sources.
- **Data analytics** — turns raw output into verified numbers and reports.
- **Service health** — always-on watchdog, monitors, quality gates.
- **Operations** — hygiene, cleanup, mechanical tasks.

Every step runs under a resolved timeout — explicit > environment override >
step-type default > base default (see [`0004-task-appropriate-timeouts.md`](decisions/0004-task-appropriate-timeouts.md)) —
and nothing reports done that did not finish. An empty plan or zero successful
steps exits non-zero and the ledger records `failed` (see
[`0002-fail-loud.md`](decisions/0002-fail-loud.md)).

---

## Flow 1 — The morning batch (scheduled, unattended)

**What it is:** the overnight scheduled batch of routine tasks fires at the
start of the day. The shape is the same every morning; the content changes.

1. **Scheduler fires** the due schedules on the tick cadence. Each becomes a
   task in the ledger.
2. **Planner** decomposes the routine batch into steps and orders them.
3. **Dispatcher** runs each step as its seat process — a reporting step, a
   data-quality check, a content refresh. Steps with no dependencies run in
   parallel waves.
4. **Verification gate:** a reporting step is *not* done because it printed
   numbers. It is done because its output passed an exact-check eval against
   the expected schema — row counts match, no empty sections, no silent
   drop of records.
5. **Outcome:** a summary of the batch is produced and reviewed. If any step
   failed, the batch is recorded `failed` — the day starts with a visible,
   actionable list, not a green checkmark that hid a red step.

**Why it matters:** this is the reliability floor. A routine batch that cannot
fail loud would poison every downstream decision made from its output.

---

## Flow 2 — A research-and-report request (interactive)

**What it is:** a request arrives for a sourced briefing on a topic, with a
deadline. Three seats cooperate; the requester sees one deliverable.

1. **Intake:** the task enters the queue with an explicit deadline and
   acceptance criteria ("must cite sources, must answer the N questions, must
   flag uncertainty").
2. **Plan:** the planner breaks it into ordered steps — scope the questions,
   gather sources, extract answers, verify claims, write the briefing.
3. **Parallel research wave:** the research seat gathers and cites multiple
   sources in parallel. Every claim carries a citation back to a retrievable
   source.
4. **Cross-check (the data seat's job):** the extracted answers are verified
   against the sources; contradictions are resolved by re-checking the source,
   not by averaging opinions. Unresolvable ambiguity is flagged in the output,
   never papered over.
5. **Write and gate:** the briefing is drafted, then run through a rubric
   judge — clarity, coverage, citation presence, and honest uncertainty.
   Below-threshold drafts go back for revision, automatically.
6. **Outcome:** the finished briefing is delivered with its verification
   record. The requester can see which claims were checked, which were
   ambiguous, and which sources were used.

**Why it matters:** this is the "trust the output" path. The deliverable is
only as good as the checks between raw research and the final document.

---

## Flow 3 — A small build-and-ship (change management)

**What it is:** a small feature or fix goes from request to shipped, with the
"never ship before verified" rule applied at every hand-off.

1. **Intake and plan:** the request is triaged, sized, and turned into steps —
   implement, test, eval, deploy, verify.
2. **Implement:** the engineering seat writes the change. The change is
   scoped to the named files for the task — no sweeping unstaged edits.
3. **Eval gate:** before anything ships, the change runs against the eval
   harness (see [`examples/evals/`](../examples/evals/)): the golden dataset
   must still pass, the regression suite must stay green, and any
   judge-scored behavior must meet threshold. A regression blocks the ship —
   an intentional behavior change must update the golden labels **in the same
   change** as the code.
4. **Deploy:** the change moves through the deployment path. The deploy step
   is killable by timeout, and its success is confirmed by a health probe
   afterward — the deploy is not "done" when the command returns, only when
   the probe confirms the service came up.
5. **Post-deploy watch:** service health keeps watching. If the probe flaps
   (up, down, up), that is treated as a symptom, not a pass — see Flow 4.
6. **Outcome:** the change is recorded in the ledger with its eval results and
   probe confirmation attached. Any step that failed leaves the whole task
   `failed`, loud and visible.

**Why it matters:** this is the difference between "we shipped it" and "it
works after shipping." The eval gate is what makes the claim checkable.

---

## Flow 4 — A flapping probe (the incident shape)

**What it is:** service health catches a symptom that looks green but is not —
a health probe that returns up, down, up within minutes. The shape below is
what happens; no specific service or endpoint is named.

1. **Detect:** the watchdog flags the flapper. Critically, it does **not**
   declare a clean "up" — a probe that alternates is a symptom, so it is
   reported as an alert, not a pass.
2. **Log before act:** the first transient failure is logged, not acted on.
   The rule is to never auto-execute on a single blip. It is the *second*
   consecutive failure that triggers action — this is what stops a flapper
   from causing a cascade of pointless restarts.
3. **Escalate:** the alert routes to the operations and engineering seats with
   the probe history attached. Timeouts are honored: a stuck step is killed
   rather than allowed to hang the queue.
4. **Remediate:** the root cause is addressed — a config fix, a redeploy, a
   retry policy change — each as its own small task with its own verification.
5. **Post-mortem as a first-class artifact:** a short "what happened, what
   changed, what would we do differently" note is written and stored with the
   incident. The org treats post-mortems as data, not ceremony.
6. **Outcome:** the ledger shows the full arc — detection, the two-strike
   rule in action, the fix, and the lesson. The next person who sees this
   failure mode starts from the last post-mortem, not from scratch.

**Why it matters:** this is where "fail loud" and "log before act" meet. A
system that cannot tell a flapper from a real outage will burn resources on
false alarms or miss a real one — neither is acceptable.

---

## What the day adds up to

- **Every task** has an owner seat, a resolved timeout, and a recorded
  outcome in the ledger — success is not assumed, it is verified.
- **Every deliverable** passes a gate — an exact-check eval, a judge score, or
  a live probe — before it is called done.
- **Every failure** is visible: there is no path from "nothing ran" to
  "completed" (ADR-0002).
- **No seat** is trusted on reputation; every seat is trusted because its
  work was checked.

That is the shape of the day: fifteen seats, one ledger, and a hard rule that
nothing reports done that did not finish.

---

**Asbury Solutions** · Plain words, real systems, zero fabrication.
