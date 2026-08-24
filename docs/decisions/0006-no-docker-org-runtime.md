# ADR-0006 — No Docker for the org runtime

- **Status:** Accepted
- **Date:** 2026-07

## Context

The org runs on a single Linux host. Containers add orchestration overhead,
image maintenance, and a layer of indirection between the agent processes and
the host filesystem/ports they depend on.

## Decision

The org runtime runs **natively** — the kernel and side services are systemd
user units launching plain processes directly. No containerization for the
core system.

## Consequences

- Simpler ops: one host, native process management, direct filesystem access.
- The trade-off (less isolation, no portability to arbitrary hosts) is
  accepted because the system is a single-machine deployment by design.
- Anything that *does* benefit from isolation is handled at the edge, not the
  core.
