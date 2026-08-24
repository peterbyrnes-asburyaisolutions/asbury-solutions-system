# ADR-0003 — One shared auth source, no per-seat keys

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

Per-seat API keys meant secrets scattered across profiles, rotation pain, and
leak surface.

## Decision

All seats resolve their model credential from a **single shared auth file** —
the same one the interactive client uses. No per-seat keys, no second provider
as default.

## Consequences

- One secret to protect and rotate, in one place.
- Seats cannot diverge onto different providers accidentally.
- A leaked per-seat token becomes impossible because per-seat tokens no longer
  exist.
