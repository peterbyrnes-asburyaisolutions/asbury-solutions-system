# ADR-0001 — The fleet is real agent seats, not in-process role-play

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Early versions of the orchestrator simulated specialists (Researcher, Coder,
Reviewer, …) in-process — one model pretending to be several personas. That
produced plausible-looking "multi-agent" results that were actually a single
agent wearing masks.

## Decision

The leaves of the system are the **15 real agent seats**, each launched as its
own agent subprocess with its own identity, configuration, memory, skills, and
tool allow-list. The dispatcher invokes `hermes -p <seat> chat` per step.
Specialist simulations were removed from the org runtime.

## Consequences

- Each seat has genuine persistent memory and independent configuration — not
  a prompt-wrapped fiction.
- Dispatch is heavier (a real subprocess per step) but honest.
- Name resolution must be strict: an unknown seat refuses to dispatch rather
  than being invented.
