# Asbury Solutions — Autonomous Agent Organization

A production **multi-agent operating system** that runs a real business from one
machine: 15 specialized autonomous agent seats, coordinated by a scheduling
kernel, dispatched as real agent processes, and tracked in a durable task
ledger.

This repository is the **public architecture** of that system. It intentionally
contains only the *system* — design, stack, decisions, and non-secret
configuration examples. It contains **no credentials, no live endpoints, no
ports, no client data, and no internal operational details** (see
[`docs/sanitization.md`](docs/sanitization.md)).

> **Who this is for:** engineers and technical reviewers who want to see how a
> small autonomous software company is actually built and run — not a demo, a
> live production system with real workload history.

---

## The idea in one paragraph

Most "agent" demos are one prompt in a loop. This is the opposite: a
**company of agents**. Fifteen distinct agent personas — CEO, engineering,
devops, research, marketing, design, monitoring, sales ops, and more — each
with its own identity, memory, tool access, and decision scope. A Flask kernel
schedules their work, a Python orchestrator turns tasks into plans and
dispatches each step to the right seat as a **real agent process**, and every
task is written to a SQLite ledger so the system has *actual history* — not a
chat log.

The result is an organization that writes code, ships products, answers
customers, monitors itself, and keeps itself honest — and that organization
is the artifact on display here.

---

## System overview

```
                       ┌────────────────────────────────────────┐
                       │         CLIENT SURFACES                │
                       │  Web dashboard · APIs · Webhooks       │
                       └───────────────┬────────────────────────┘
                                       │ HTTP
                       ┌───────────────▼────────────────────────┐
                       │         SCHEDULING KERNEL              │
                       │  Flask app · threaded                   │
                       │  scheduler · task runner · watchdog     │
                       │  memory · health · rate limiting        │
                       └───────┬──────────────────────┬─────────┘
                               │                      │
                  ┌────────────▼──────────┐   ┌───────▼──────────┐
                  │     ORCHESTRATOR      │   │   TASK LEDGER    │
                  │  plan → steps →       │   │   SQLite (WAL)   │
                  │  dispatch seats       │   │   tasks·memory   │
                  └────────────┬──────────┘   └──────────────────┘
                               │ subprocess
        ┌──────────────────────▼───────────────────────┐
        │            THE FLEET — 15 AGENT SEATS        │
        │  each a real agent process with identity,    │
        │  memory, skills, tools, and decision scope   │
        └──────────────────────────────────────────────┘
```

Full diagrams in [`docs/architecture.md`](docs/architecture.md).

---

## The fleet — 15 seats

The system's "employees" are agent personas, each with a real Hermes agent
profile (identity file, config, memory, skills, tool allow-list).

| # | Seat | Persona | Responsibility |
|---|------|---------|----------------|
| 1 | Chief Executive | Ward | Strategy, prioritization, routing, final decisions |
| 2 | Liaison | Eli | External communications — the single front door |
| 3 | Business Ops | Marcus | Proposals, bookkeeping, engagement framing |
| 4 | Sales Pipeline | Vance | Revenue ops, CRM, pipeline, forecasting |
| 5 | Engineering | Frank | Full-stack application code |
| 6 | DevOps | Frank | Pipelines, deployment, security, runbooks |
| 7 | Service Health | Argus | 24/7 monitoring, watchdog, quality gates |
| 8 | Research | Isidore | Deep multi-source research, citations |
| 9 | Marketing | Homer | Go-to-market, copy, campaigns |
| 10 | Creative Direction | Delacroix | Brand system, visual design, quality bar |
| 11 | Personal Assistant | Donna | Scheduling, personal coordination |
| 12 | Operations | Mop | Hygiene, cleanup, mechanical tasks |
| 13 | Automation | Gage | Workflow graphs, webhooks, non-LLM automation |
| 14 | Data Analytics | Victor | Databases, reporting, analysis |
| 15 | Platform Ops | Halcyon | Kernel, scheduler, task ledger, platform health |

The fleet is **not role-play**: each step of a plan is dispatched to a real
agent subprocess with that seat's own configuration and memory. This is a
deliberate, recorded decision — see
[`docs/decisions/0001-real-seats-not-roleplay.md`](docs/decisions/0001-real-seats-not-roleplay.md).

---

## How a task flows

1. A task arrives (scheduled, webhook, or API).
2. The **kernel** records it in the task ledger and hands it to the orchestrator.
3. The **orchestrator planner** breaks it into steps — each step names a seat,
   a task, and dependencies.
4. **Dispatch** runs each step as that seat's agent process, in parallel waves
   where dependencies allow.
5. Results are synthesized into a final answer.
6. **Fail-loud:** an empty plan or all-steps-failed raises an error, the
   process exits non-zero, and the task is recorded as *failed* — the system
   never reports a false success.

```
Task → Planner (plan: steps → seat + task + deps)
     → dispatch_seat(seat, task)          # real agent subprocess
     → parallel wave via dispatch_many    # each leaf = a real seat
     → synthesize final result
Failure (no plan / all steps failed) → error → exit non-zero → task 'failed'
```

---

## Operating principles

- **Real seats, not role-play.** Leaves are real agent processes, not
  in-process simulated specialists.
- **Fail loud.** False success is forbidden; errors propagate to the ledger.
- **One shared auth source.** No per-seat API keys — a single shared
  credential, resolved by the dispatcher.
- **Task-appropriate timeouts.** A step is killed if it exceeds its timeout
  (explicit > environment override > step-type default > base default).
- **Durable history.** Every task, schedule, memory entry, and alert lives in
  SQLite (WAL), so claims are checkable and nothing is a fresh demo state.

---

## Repository layout

```
.
├── README.md                 # this file — public overview
├── LICENSE                   # MIT
├── .gitignore
├── docs/
│   ├── architecture.md       # system + kernel + task-flow diagrams
│   ├── tech-stack.md         # every technology and why
│   ├── sanitization.md       # what is deliberately excluded, and why
│   └── decisions/            # decisions-as-code (ADR style)
│       ├── 0001-real-seats-not-roleplay.md
│       ├── 0002-fail-loud.md
│       ├── 0003-single-auth-source.md
│       ├── 0004-task-appropriate-timeouts.md
│       ├── 0005-one-orchestrator.md
│       ├── 0006-no-docker-org-runtime.md
│       └── 0007-sqlite-wal-ledger.md
├── diagrams/                 # Mermaid source for architecture diagrams
│   ├── system-overview.mmd
│   ├── kernel-internals.mmd
│   └── task-flow.mmd
└── examples/                 # non-secret sample configuration
    ├── config/
    │   ├── seat.example.yaml
    │   ├── preset.example.yaml
    │   └── env.example
    └── README.md
```

---

## Read next

- [`docs/architecture.md`](docs/architecture.md) — the full picture
- [`docs/tech-stack.md`](docs/tech-stack.md) — the stack, with rationale
- [`docs/decisions/`](docs/decisions/) — how and why key calls were made
- [`examples/`](examples/) — non-secret configuration to learn from

---

## License

MIT — see [`LICENSE`](LICENSE).
