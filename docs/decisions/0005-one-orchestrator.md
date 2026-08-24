# ADR-0005 — One orchestrator, not a family of twins

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

The org had two overlapping swarm implementations (an in-kernel twin and the
standalone swarm repo), plus legacy presets. Divergence risk: two codebases,
two truths.

## Decision

Consolidate to a **single standalone orchestrator** as the kernel's
`multi_agent` dispatch target. The twin is archived (history preserved), and
the legacy presets are tombstoned. One dispatcher owns the fleet.

## Consequences

- One codebase to maintain and test.
- The kernel has a single, stable dispatch command for agent tasks.
- Old preset names are removed from the live set to prevent accidental use.
