# Architecture

This document describes how the Asbury Solutions autonomous agent
organization is built. All diagrams are Mermaid source (render natively on
GitHub) and are also stored standalone in [`../diagrams/`](../diagrams/).

Everything here describes the **system**. It contains no credentials, no live
endpoints, no ports, no client data, and no internal operational state. See
[`sanitization.md`](sanitization.md) for the boundary.

---

## 1. System overview

The system has four layers: client surfaces, a scheduling kernel, an
orchestrator, and the agent fleet. A durable SQLite ledger sits beneath it all.

```mermaid
flowchart TB
    subgraph SURFACES["Client Surfaces"]
        UI["Web Dashboard"]
        API["HTTP API"]
        WH["Webhooks"]
    end

    subgraph KERNEL["Scheduling Kernel (Flask app, threaded)"]
        SCHED["Scheduler<br/>tick · next_run"]
        RUNNER["Task Runner<br/>dispatch shell cmds · track pid"]
        WD["Watchdog<br/>3-tier service probes"]
        MEM["Memory API"]
        RL["Rate Limiter"]
    end

    subgraph ORCH["Orchestrator"]
        PLAN["Planner<br/>task → steps (seat + task + deps)"]
        DISPATCH["Dispatcher<br/>real seat subprocess"]
        SYNC["Result synthesis"]
    end

    subgraph FLEET["The Fleet — 15 agent seats"]
        S1["CEO"]
        S2["Engineering"]
        S3["DevOps"]
        S4["Research"]
        S5["Marketing"]
        SN["... + 10 more seats"]
    end

    subgraph LEDGER["Task Ledger (SQLite, WAL)"]
        TASKS["tasks"]
        MEMS["memory"]
        SCHS["schedules"]
        ALERTS["alerts"]
    end

    UI --> KERNEL
    API --> KERNEL
    WH --> KERNEL
    KERNEL --> ORCH
    PLAN --> DISPATCH
    DISPATCH --> FLEET
    FLEET --> SYNC
    KERNEL --> LEDGER
    ORCH --> LEDGER
```

---

## 2. Kernel internals

A single threaded application process owns scheduling, task execution, health
monitoring, memory, and rate limiting. It is the hub the fleet runs through.

```mermaid
flowchart LR
    subgraph PROC["Kernel process"]
        T1["Task Runner"]
        T2["Scheduler"]
        T3["Watchdog"]
        T4["WAL Checkpoint"]
        T5["Agent Heartbeat"]
        T6["Rate Limiter"]
    end

    DB[("SQLite os.db — WAL mode")]

    T1 --> DB
    T2 --> DB
    T3 --> DB
    T4 --> DB
    T5 --> DB
    T6 --> DB
```

Background responsibilities:

- **Task Runner** — executes scheduled commands, tracks process groups, and
  records outcomes in the ledger.
- **Scheduler** — ticks on a cadence, fires due schedules, and computes the
  next run time.
- **Watchdog** — probes registered services with per-service latency budgets
  and severity tiers, so a slow service doesn't take down the probe itself.
- **WAL Checkpoint** — maintains the SQLite write-ahead log and vacuums on a
  schedule.
- **Agent Heartbeat** — pushes the kernel's own health pulse into memory so
  other seats can see it.
- **Rate Limiter** — sliding-window per-IP throttling on the HTTP surface.

---

## 3. Task flow (dispatch)

This is the heart of the system: how a task becomes real work done by a real
seat, and how failure is never reported as success.

```mermaid
sequenceDiagram
    participant C as Caller (API / schedule / webhook)
    participant K as Kernel
    participant O as Orchestrator Planner
    participant D as Dispatcher
    participant S as Seat (agent subprocess)
    participant L as Task Ledger

    C->>K: task
    K->>L: record task (pending)
    K->>O: plan(task)
    O->>O: steps = [ (seat, task, deps), ... ]
    alt no steps OR all steps fail
        O-->>K: OrchestrationError
        K->>L: mark task failed
        K-->>C: exit non-zero
    else steps produced
        loop each step (parallel wave)
            O->>D: dispatch_seat(seat, step)
            D->>S: launch real agent subprocess
            S-->>D: step result
            D-->>O: collect
        end
        O->>O: synthesize final result
        O->>L: mark task completed
        O-->>K: final answer
    end
```

Fail-loud is enforced end to end: an empty plan or zero successful steps
raises an error, the process exits non-zero, and the ledger records `failed` —
never a false `completed`.

---

## 4. Fleet design

Each seat is a full agent profile — identity, configuration, memory, skills,
and an explicit tool allow-list. The roster is a single frozen tuple in code
(`fleet.py`), so the planner, dispatcher, and name resolution all agree on who
exists and who does not.

```mermaid
flowchart TD
    ROSTER["fleet.py — frozen 15-seat roster"]

    subgraph DOMAINS["Seat domains"]
        A["Leadership / strategy"]
        B["Engineering / delivery"]
        C["Commercial / customer"]
        D["Operations / monitoring"]
    end

    ROSTER --> A
    ROSTER --> B
    ROSTER --> C
    ROSTER --> D

    A --> A1["CEO"]
    A --> A2["Liaison"]
    B --> B1["Engineering"]
    B --> B2["DevOps"]
    B --> B3["Platform Ops"]
    C --> C1["Business Ops"]
    C --> C2["Sales Pipeline"]
    C --> C3["Marketing"]
    C --> C4["Research"]
    C --> C5["Data Analytics"]
    D --> D1["Service Health"]
    D --> D2["Creative Direction"]
    D --> D3["Automation"]
    D --> D4["Personal Assistant"]
    D --> D5["Operations"]
```

Name resolution is case-insensitive and accepts legacy aliases (e.g. "Coder"
→ Engineering), but unknown names resolve to nothing — the system refuses to
dispatch a seat that doesn't exist.

---

## 5. Failure handling

Three layers keep the system honest:

1. **Fail-loud dispatch** — no plan or all-steps-failed ⇒ error ⇒ non-zero exit
   ⇒ task marked `failed`.
2. **Per-step timeouts** — a step is killed if it exceeds its resolved timeout
   (explicit step value > environment override > step-type default > base
   default).
3. **Watchdog** — services are probed with per-service latency budgets; a
   dead or hung service is surfaced instead of silently skipped.

The point: **the system never reports a success it didn't achieve.** That is
the single most important property of the whole design.
