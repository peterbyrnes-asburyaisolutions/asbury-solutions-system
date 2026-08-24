# RUNBOOK — watchdog.py

**Tool:** `tools/watchdog.py` · **Owner:** devops · **Version:** 1.0.0
**Stack:** Python 3 (stdlib only — no dependencies)
**Use:** detect scheduled jobs that have gone silent before they become an incident.

A schedule-aware stall watchdog. It reads a jobs file, classifies each job as
`ok` / `warn` / `critical`, and — only when you pass `--apply` — runs your
resume and notify commands. Everything org-specific (paths, commands, hosts)
is supplied at the command line; nothing is compiled in.

---

## When to run this

- **On a schedule** — a cron/systemd timer runs it periodically; WARN findings
  are informational, CRITICAL findings mean real overdue silence.
- **Before a review** — a dry-run shows the current stall state of every job.
- **After wiring a new job** — confirm the new job classifies as healthy
  within its grace period.

## Quick start

```bash
# 1. Dry-run against the example config (read-only, safe)
python3 tools/watchdog.py --jobs tools/watchdog.example.json

# 2. JSON report (for logging / a cron tick)
python3 tools/watchdog.py --jobs tools/watchdog.example.json --json

# 3. Actual remediation — EXPLICIT OPT-IN
python3 tools/watchdog.py --jobs /path/to/your-jobs.json \
    --resume-cmd 'your-resume-tool --job {job_id}' \
    --notify-cmd 'your-notifier --subject "{subject}" --body "{body}"' \
    --apply
```

Without `--apply`, the watchdog only reports. It never runs anything.

## The jobs file schema (contract)

A JSON list, or an object with a `jobs` array. Every entry is an object:

| Field | Required | Meaning |
|-------|----------|---------|
| `id` | yes | stable identifier |
| `name` | no | human-readable label for reports |
| `enabled` | no (default `true`) | `false` jobs are never flagged |
| `created_at` | no | used for the new-job grace period |
| `last_run_at` (or `last_run`, `last_status_at`, `completed_at`, `last_success_at`) | no | when the job last ran |
| `last_status` | no | `error`/`failed` on a recently-run job → WARN |
| `next_run_at` (or `next_run`) | no | when the next fire is scheduled |
| `schedule` | no | `{"kind":"cron","expr":...}`, `{"kind":"interval","minutes":N}`, or `{"display":...}` |

See `tools/watchdog.example.json` for a complete, valid example covering
healthy, stalled, erroring, disabled, and brand-new jobs.

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | Scan completed; no CRITICAL findings (WARN is informational) |
| 1    | Usage or configuration error (bad file, bad schema, bad flag combo) |
| 2    | CRITICAL findings remain (true overdue silence) |

## How severity is decided (schedule-aware)

Age alone is NOT a finding. The watchdog asks "is this silence expected?":

- **Healthy** — last run is recent and the next fire is still scheduled.
- **WARN** — old last run with a future next fire (a weekday-only job on a
  Sunday), a recent run that errored, or a never-ran job whose first fire
  hasn't slipped.
- **CRITICAL** — a job whose next scheduled fire has already slipped past
  grace (`--overdue-grace-min`, default 45m), or a job whose age is way past
  `--crit-days` with no future schedule to excuse it.

This prevents two classic false alarms: flagging a job that is legitimately
between runs, and flagging a brand-new job before its first fire.

## Thresholds

| Flag | Default | Meaning |
|------|---------|---------|
| `--warn-days` | 3.0 | age of last run that triggers WARN |
| `--crit-days` | 8.0 | age of last run that triggers CRITICAL |
| `--overdue-grace-min` | 45 | how far past `next_run_at` before "overdue" |
| `--min-age-hours` | 2.0 | grace for newly created jobs |

`--warn-days` must be <= `--crit-days`; the tool refuses to run otherwise.

## Remediation commands (`--apply` only)

- `--resume-cmd 'TEMPLATE'` — run for each CRITICAL + overdue job. Use
  `{job_id}` and `{name}` placeholders. If omitted, the tool reports
  `RESUME_SKIPPED` instead.
- `--notify-cmd 'TEMPLATE'` — run once when CRITICAL findings exist. Use
  `{subject}` and `{body}` placeholders.

Commands are shell strings; placeholders are substituted before execution.

## FABLE 5 compliance

- **CONFIRM-GATE SAFETY** — dry-run by default; `--apply` is explicit opt-in.
  Without it, nothing is resumed and nothing is notified.
- **CONTRACT-FIRST DATA** — the jobs-file schema is validated at load; a
  missing file, malformed JSON, or a non-object entry aborts with remediation.
- **NO SILENT DEFAULTS** — every threshold is explicit and printed in
  `--json`; bad flag combinations abort rather than guess.
- **SELF-DOCUMENTING RUNBOOKS** — this file is the runbook.
- **ROLE-AGNOSTIC THINKING** — a generic stall detector any team can run;
  org-specific resume/notify behavior is injected at runtime, not compiled in.

— devops · Asbury Solutions · 2026-08-24
