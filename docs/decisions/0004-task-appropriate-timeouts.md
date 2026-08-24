# ADR-0004 — Task-appropriate timeouts per step

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

A fixed per-step timeout killed long build steps (a 600s ceiling truncated
multi-step builds), while quick verify steps didn't need the full budget.

## Decision

Each dispatched step gets a resolved timeout, in precedence order:

1. **Explicit `timeout_seconds`** on the plan step — always wins
2. **`SEAT_TIMEOUT` environment override** — global ceiling for a run
3. **Step-type default** — build/research/write/test → 1200s; quick
   verify/check/reply → 300s
4. **Base default** — 600s

The resolved value is applied to *every* dispatch path (single and parallel
wave).

## Consequences

- Long build steps survive; quick steps fail fast instead of lingering.
- The resolution order is deterministic and documented.
- A step that exceeds its budget is killed and surfaced, not left hung.
