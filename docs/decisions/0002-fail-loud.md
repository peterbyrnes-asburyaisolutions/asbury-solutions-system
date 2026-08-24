# ADR-0002 — Fail loud, never report false success

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

A silent-failure bug let a task be recorded as `completed` even when the plan
was empty or every step failed. The ledger told a prettier story than reality.

## Decision

An empty plan or zero successful steps raises an `OrchestrationError`, the
process exits **non-zero**, and the ledger records the task as `failed`.
There is no path from "nothing ran" to "completed".

## Consequences

- Verification harnesses assert the fail-loud path directly (forced empty plan
  ⇒ exit 1).
- Operators trust the ledger's `failed` counts because they cannot be hidden.
- Failure is visible and actionable instead of silently swallowed.
