# Decisions-as-code

Architectural decisions are recorded as lightweight ADRs — one file per
decision, in this directory. Each is a statement of *what was decided, in
what context, and what it costs*. The point is that the "why" is versioned
next to the code, so future readers (human or agent) don't re-litigate closed
calls.

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-real-seats-not-roleplay.md) | The fleet is real agent seats, not in-process role-play | Accepted |
| [0002](0002-fail-loud.md) | Fail loud, never report false success | Accepted |
| [0003](0003-single-auth-source.md) | One shared auth source, no per-seat keys | Accepted |
| [0004](0004-task-appropriate-timeouts.md) | Task-appropriate timeouts per step | Accepted |
| [0005](0005-one-orchestrator.md) | One orchestrator, not a family of twins | Accepted |
| [0006](0006-no-docker-org-runtime.md) | No Docker for the org runtime | Accepted |
| [0007](0007-sqlite-wal-ledger.md) | SQLite (WAL) as the durable task ledger | Accepted |

## Adding a decision

1. Copy the numbering: next free `NNNN`.
2. Use the format: Status, Date, Context, Decision, Consequences.
3. One decision per file. Link it from this index.
