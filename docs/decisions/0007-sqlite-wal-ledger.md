# ADR-0007 — SQLite (WAL) as the durable task ledger

- **Status:** Accepted
- **Date:** 2026-07

## Context

The system needed durable state for tasks, schedules, memory, alerts, and
latency history — without standing up and operating a database server on the
single host.

## Decision

Use **SQLite in WAL mode** as the core ledger, with a shared connection
factory (sibling modules reuse one FD-safe factory), checkpointing and
periodic vacuum maintained by the kernel.

## Consequences

- Zero-ops durability: no server to run, no credentials to manage.
- WAL mode gives concurrent readers while the writer thread checkpoints.
- The ledger is a single file — easy to back up, easy to audit.
