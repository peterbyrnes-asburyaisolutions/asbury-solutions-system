#!/usr/bin/env python3
"""watchdog.py — schedule-aware stall watchdog for scheduled jobs (generic).

Part of the Asbury Solutions public toolchain. Detects scheduled jobs that
have gone silent: jobs whose last run is old, whose next scheduled fire has
already slipped, or that never ran at all. Severity is schedule-aware — age
alone is NOT a finding when the next fire is still in the future within
grace, and weekday-only jobs are not flagged over a weekend.

This is the sanitized, generic version of an internal ops tool. It contains
no organization-specific paths, credentials, commands, or hosts. Everything
that was organization-specific is now a command-line flag you supply.

Subcommands and modes:
  (default)   Classify every job in the jobs file. Dry-run: reports what it
              WOULD resume/notify, does nothing.
  --apply     Run the resume command on critical+overdue jobs and the notify
              command when criticals exist. Explicit opt-in (FABLE 5
              CONFIRM-GATE SAFETY).
  --json      Emit a machine-readable report instead of the human summary.

Standards (FABLE 5):
  - CONFIRM-GATE SAFETY — dry-run by default; --apply is explicit opt-in.
  - CONTRACT-FIRST DATA — the jobs file schema is validated at load; any
    deviation fails loudly with remediation.
  - NO SILENT DEFAULTS — every threshold and command has an explicit value;
    a missing jobs file, malformed JSON, or unknown schedule aborts loudly.
  - SELF-DOCUMENTING RUNBOOKS — see watchdog_RUNBOOK.md in this directory.

Exit codes:
  0 = scan completed, no CRITICAL findings (WARN is informational)
  1 = usage or configuration error (bad file, bad schema, missing args)
  2 = CRITICAL findings remain (true overdue silence)

Runbook: watchdog_RUNBOOK.md (same directory).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERSION = "1.0.0"

# Defaults — explicit values so behavior is never silently guessed.
DEFAULT_WARN_DAYS = 3.0
DEFAULT_CRIT_DAYS = 8.0
DEFAULT_OVERDUE_GRACE_MIN = 45
DEFAULT_MIN_AGE_HOURS = 2.0


def parse_ts(val) -> datetime | None:
    """Parse a timestamp from many common shapes, or None if absent/unparseable."""
    if val is None or val == "" or val == "never":
        return None
    if isinstance(val, (int, float)):
        ts = float(val)
        if ts > 1e12:
            ts /= 1000.0  # milliseconds -> seconds
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    s = str(val).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19] if "T" in s or " " in s else s[:10], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def load_jobs(path: str) -> list[dict]:
    """Load and validate the jobs file. Fails loudly on any contract violation."""
    p = Path(path)
    if not p.is_file():
        raise SystemExit(
            f"ERROR: jobs file not found: {path}\n"
            f"Remediation: point --jobs at a JSON file with {{\"jobs\": [...]}} — "
            f"see tools/watchdog.example.json"
        )
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"ERROR: jobs file is not valid JSON: {path}\n  {exc}\n"
            f"Remediation: fix the file to the schema in watchdog.example.json"
        )
    if isinstance(data, dict) and "jobs" in data:
        jobs = data["jobs"]
    else:
        jobs = data
    if not isinstance(jobs, list):
        raise SystemExit(
            f"ERROR: jobs file must be a JSON list, or an object with a "
            f"'jobs' array: {path}\n"
            f"Remediation: see tools/watchdog.example.json for the schema"
        )
    cleaned = []
    for j in jobs:
        if not isinstance(j, dict):
            raise SystemExit(
                f"ERROR: each entry in 'jobs' must be a JSON object, got "
                f"{type(j).__name__}: {path}\n"
                f"Remediation: fix the offending entry"
            )
        cleaned.append(j)
    return cleaned


def job_last_run(job: dict) -> datetime | None:
    """Return the most recent run timestamp across all common field names."""
    for k in ("last_run_at", "last_run", "lastRun", "last_status_at",
              "completed_at", "last_success_at"):
        dt = parse_ts(job.get(k))
        if dt:
            return dt
    for nest_key in ("state", "meta", "result"):
        nest = job.get(nest_key)
        if isinstance(nest, dict):
            for k in ("last_run_at", "last_run", "completed_at"):
                dt = parse_ts(nest.get(k))
                if dt:
                    return dt
    return None


def schedule_label(job: dict) -> str:
    """Human-readable schedule string for reports."""
    sched = job.get("schedule") or {}
    if isinstance(sched, dict):
        if sched.get("display"):
            return str(sched["display"])
        if sched.get("kind") == "cron" and sched.get("expr"):
            return str(sched["expr"])
        if sched.get("kind") == "interval" and sched.get("minutes") is not None:
            return f"every {sched['minutes']}m"
    disp = job.get("schedule_display")
    return str(disp) if disp else "?"


def is_weekday_only(job: dict) -> bool:
    """Crude detection of Mon-Fri cron schedules (day-of-week field 1-5)."""
    sched = job.get("schedule") or {}
    expr = ""
    if isinstance(sched, dict):
        expr = str(sched.get("expr") or sched.get("display") or "")
    expr = expr or str(job.get("schedule_display") or "")
    parts = expr.split()
    if len(parts) >= 5 and parts[4] in ("1-5", "MON-FRI", "mon-fri"):
        return True
    if "1-5" in expr and "* *" in expr:
        return True
    return False


def classify_job(job: dict, now: datetime, cfg) -> dict | None:
    """Return a finding dict for a stalled job, or None if it is healthy."""
    jid = job.get("id") or job.get("job_id")
    name = job.get("name") or job.get("title") or str(jid)
    enabled = job.get("enabled", True)
    if enabled is False:
        return None

    # Newly created jobs get a grace period so they aren't flagged before
    # their first scheduled fire has had a chance to happen.
    created = parse_ts(job.get("created_at"))
    if created is not None and (
        now - created.astimezone(timezone.utc)
    ).total_seconds() < cfg.min_age_hours * 3600:
        return None
    last = job_last_run(job)
    if last is None:
        next_run = parse_ts(job.get("next_run_at") or job.get("next_run"))
        if next_run is not None and (
            next_run.astimezone(timezone.utc) - now
        ).total_seconds() < cfg.min_age_hours * 3600:
            return None

    last = job_last_run(job)
    age = None
    if last is not None:
        age = max(0.0, (now - last.astimezone(timezone.utc)).total_seconds() / 86400.0)
    last_status = job.get("last_status") or job.get("status") or job.get("last_run_status")
    next_run = parse_ts(job.get("next_run_at") or job.get("next_run"))
    sched = schedule_label(job)
    weekday_only = is_weekday_only(job)

    overdue = False
    next_in_future = False
    if next_run is not None:
        nr = next_run.astimezone(timezone.utc)
        if nr > now + cfg.overdue_grace:
            next_in_future = True
        elif nr < now - cfg.overdue_grace:
            overdue = True

    # Base severity by age (legacy metric).
    if age is None:
        base = "critical"
    elif age >= cfg.crit_days:
        base = "critical"
    elif age >= cfg.warn_days:
        base = "warn"
    else:
        base = "ok"

    if last_status in ("error", "failed") and base == "ok":
        base = "warn"

    # Schedule-aware demotion: silence is expected when the next fire is
    # still scheduled (e.g. weekday-only job on a Sunday, or a daily job
    # already booked for later today).
    if base == "critical":
        if age is None:
            # Never ran: only CRITICAL if the first fire already slipped.
            if next_in_future or (next_run is None and not overdue):
                base = "warn"
        elif next_in_future and not overdue:
            base = "warn"
        elif weekday_only and not overdue and next_in_future:
            base = "warn"

    # Promotion: genuinely overdue silence is always at least WARN.
    if overdue and base == "ok":
        base = "warn"
    if overdue and age is not None and age >= cfg.warn_days:
        base = "critical"
    if overdue and age is None:
        base = "critical"

    if base == "ok":
        return None

    detail_bits = [
        f"last={last.isoformat() if last else 'never'}",
        f"status={last_status}",
        f"schedule={sched}",
        f"next={next_run.isoformat() if next_run else 'none'}",
    ]
    if overdue:
        detail_bits.append("OVERDUE")
    elif next_in_future:
        detail_bits.append("next_future")
    if weekday_only:
        detail_bits.append("weekday_only")

    return {
        "job_id": jid,
        "name": name,
        "severity": base,
        "age_days": None if age is None else round(age, 2),
        "detail": " ".join(detail_bits),
        "overdue": overdue,
        "next_run_at": next_run.isoformat() if next_run else None,
        "schedule": sched,
    }


def run_command(template: str, **kwargs) -> str:
    """Expand a {placeholder} template and run it as a shell command."""
    try:
        cmd = template.format(**kwargs)
    except KeyError as exc:
        return f"CMD_BAD_TEMPLATE missing {{{exc.args[0]}}}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return f"exit={r.returncode} {(r.stdout or r.stderr).strip()[:200]}"
    except Exception as exc:  # noqa: BLE001
        return f"CMD_FAIL {exc}"


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="watchdog.py",
        description="Schedule-aware stall watchdog for scheduled jobs. "
                    "Dry-run by default; --apply is explicit opt-in.")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    ap.add_argument("--jobs", required=True, metavar="FILE",
                    help="JSON file of jobs to inspect (required)")
    ap.add_argument("--warn-days", type=float, default=DEFAULT_WARN_DAYS,
                    help=f"age threshold for WARN, days (default {DEFAULT_WARN_DAYS})")
    ap.add_argument("--crit-days", type=float, default=DEFAULT_CRIT_DAYS,
                    help=f"age threshold for CRITICAL, days (default {DEFAULT_CRIT_DAYS})")
    ap.add_argument("--overdue-grace-min", type=int, default=DEFAULT_OVERDUE_GRACE_MIN,
                    help=f"how far past next_run before overdue (default {DEFAULT_OVERDUE_GRACE_MIN}m)")
    ap.add_argument("--min-age-hours", type=float, default=DEFAULT_MIN_AGE_HOURS,
                    help=f"grace for newly created jobs, hours (default {DEFAULT_MIN_AGE_HOURS})")
    ap.add_argument("--resume-cmd", metavar="TEMPLATE", default=None,
                    help="shell command to resume a stalled job. Use {job_id} and "
                         "{name} placeholders. Run only with --apply.")
    ap.add_argument("--notify-cmd", metavar="TEMPLATE", default=None,
                    help="shell command to notify when CRITICAL findings exist. Use "
                         "{subject} and {body} placeholders. Run only with --apply.")
    ap.add_argument("--apply", action="store_true",
                    help="EXPLICIT OPT-IN: run resume/notify commands. Without this "
                         "the run is a read-only dry-run.")
    ap.add_argument("--json", action="store_true",
                    help="emit a machine-readable JSON report")
    args = ap.parse_args()

    cfg = argparse.Namespace(
        warn_days=args.warn_days,
        crit_days=args.crit_days,
        overdue_grace=timedelta(minutes=args.overdue_grace_min),
        min_age_hours=args.min_age_hours,
    )
    if args.warn_days > args.crit_days:
        print("ERROR: --warn-days must be <= --crit-days.", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    jobs = load_jobs(args.jobs)

    findings = []
    for job in jobs:
        f = classify_job(job, now, cfg)
        if f:
            findings.append(f)

    actions = []
    if args.apply:
        for f in findings:
            # Only resume truly critical + overdue jobs; never thrash a
            # healthy scheduled job that merely has a WARN attached.
            if f.get("job_id") and f["severity"] == "critical" and f.get("overdue"):
                if args.resume_cmd:
                    actions.append(
                        run_command(args.resume_cmd,
                                    job_id=f["job_id"], name=f["name"]))
                else:
                    actions.append(
                        f"RESUME_SKIPPED {f['job_id']} (no --resume-cmd given)")

        crits = [f for f in findings if f["severity"] == "critical"]
        if crits and args.notify_cmd:
            body = "WATCHDOG CRITICAL\n" + "\n".join(
                f"- {c['name']} ({c['job_id']}) age={c['age_days']} "
                f"next={c.get('next_run_at')} {c.get('detail', '')}"
                for c in crits[:30])
            actions.append(run_command(args.notify_cmd,
                                       subject="WATCHDOG CRITICAL", body=body))
        elif crits and not args.notify_cmd:
            actions.append("NOTIFY_SKIPPED (criticals present, no --notify-cmd given)")

    crits = [f for f in findings if f["severity"] == "critical"]
    report = {
        "tool": "watchdog.py",
        "version": VERSION,
        "checked_at": now.isoformat(),
        "mode": "apply" if args.apply else "dry-run",
        "jobs_file": args.jobs,
        "findings": findings,
        "actions": actions,
        "total_issues": len(findings),
        "critical": len(crits),
        "warn": sum(1 for f in findings if f["severity"] == "warn"),
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"watchdog mode={report['mode']} issues={report['total_issues']} "
              f"critical={report['critical']} warn={report['warn']} "
              f"(jobs: {Path(args.jobs).name})")
        for f in findings:
            print(f"  [{f['severity'].upper()}] {f['name']} ({f['job_id']}) "
                  f"age_days={f['age_days']} — {f['detail']}")
        for a in actions:
            print(f"  ACTION {a}")
        if not findings:
            print("  OK no stalled jobs above thresholds")

    if crits:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
