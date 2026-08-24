#!/usr/bin/env python3
"""swarm-dispatch.py — sanitized dispatch layer (Asbury Solutions).

A GENERIC, runnable example of how the fleet dispatches work:

  1. SEAT RESOLUTION   — a planner's seat name resolves to a real seat from a
                         frozen roster (slug, canonical, alias, case-insensitive;
                         non-seats are rejected).
  2. STEP TIMEOUTS     — every step carries a ceiling resolved most-specific
                         first: explicit value > environment override > step-type
                         default > base default.
  3. DISPATCH          — each step launches as an isolated subprocess; a step
                         that exceeds its ceiling is KILLED and surfaced, not
                         left to hang the wave.
  4. FAIL LOUD         — any step that did not finish fails the whole run.
                         There is no path from "nothing ran" to "completed".

No real seats, no credentials, no internal paths, no live endpoints. The roster
below is synthetic and illustrative. Run the self-test demo:

    python3 swarm-dispatch.py --demo

The demo resolves seats, resolves timeouts across all four rungs, launches a
tiny parallel wave of harmless subprocesses (including one that exceeds its
ceiling, to show the kill path), and prints a fail-loud verdict.

What the REAL system does differently: the seat subprocess is built from the
shared configuration (agent binary + seat profile, resolved from the single
auth source — ADR-0003), and steps are read from the planner's plan rather than
a literal list. The mechanisms shown here are unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 1. Seat registry — the fleet is a frozen tuple in code, so the planner, the
#    dispatcher, and name resolution all agree on who exists (ADR-0001).
#    Roles only; this example carries no personas, no contact details.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Seat:
    slug: str
    role: str
    aliases: tuple[str, ...] = ()


FLEET: tuple[Seat, ...] = (
    Seat("chief-executive", "Strategy and final decisions"),
    Seat("liaison", "External communications — the front door"),
    Seat("business-ops", "Proposals and bookkeeping"),
    Seat("sales-pipeline", "Pipeline and forecasting"),
    Seat("engineering", "Full-stack application code"),
    Seat("devops", "Pipelines, deployment, security"),
    Seat("service-health", "Monitoring, watchdog, quality gates"),
    Seat("research", "Deep sourced research"),
    Seat("marketing", "Go-to-market and campaigns"),
    Seat("creative-direction", "Brand system and design"),
    Seat("personal-assistant", "Scheduling and coordination"),
    Seat("operations", "Hygiene and mechanical tasks"),
    Seat("automation", "Workflow graphs and non-LLM automation"),
    Seat("data-analytics", "Databases, reporting, analysis"),
    Seat("platform-ops", "Kernel, scheduler, task ledger"),
)

# Names that must never resolve to a seat.
NOT_SEATS = ("default", "shared")


def _build_index() -> dict[str, Seat]:
    """Index every name form (slug, underscore form, aliases, any case)."""
    idx: dict[str, Seat] = {}
    for seat in FLEET:
        keys = (seat.slug, seat.slug.replace("-", "_"), *seat.aliases)
        for key in keys:
            idx[key] = seat
            idx[key.lower()] = seat
    return idx


_SEAT_INDEX = _build_index()


def resolve_seat(name: str) -> Seat | None:
    """Resolve a planner/CLI name to a live seat. None if unknown or a non-seat."""
    if not name:
        return None
    raw = name.strip()
    if raw.lower() in NOT_SEATS:
        return None
    return _SEAT_INDEX.get(raw) or _SEAT_INDEX.get(raw.lower())


# ---------------------------------------------------------------------------
# 2. Step timeouts — most specific first (ADR-0004). A step is killed if it
#    exceeds its resolved ceiling; the ceiling is never a silent assumption.
# ---------------------------------------------------------------------------

BASE_TIMEOUT = 600      # safety floor if nothing else applies
_LONG_TIMEOUT = 1200    # build / research / write steps
_QUICK_TIMEOUT = 300    # verify / check / probe steps
_MIN_TIMEOUT = 30       # a step may never be allowed less than this

_LONG_KEYWORDS = (
    "build", "write", "implement", "create", "generate", "research",
    "refactor", "migrat", "test", "produce", "compile",
)
_QUICK_KEYWORDS = (
    "verify", "check", "probe", "status", "health", "reply",
    "summar", "list", "read-only",
)


def _env_override() -> int | None:
    """Live SEAT_TIMEOUT override, or None if unset/invalid."""
    raw = os.getenv("SEAT_TIMEOUT")
    if raw is None:
        return None
    try:
        return max(_MIN_TIMEOUT, int(raw))
    except ValueError:
        return None


def resolve_step_timeout(step: dict) -> int:
    """Pick the timeout (seconds) for one step: explicit > env > type > base."""
    explicit = step.get("timeout_seconds")
    if explicit is not None:
        try:
            return max(_MIN_TIMEOUT, int(explicit))
        except (TypeError, ValueError):
            pass

    env_t = _env_override()
    if env_t is not None:
        return env_t

    task = (step.get("task") or "").lower()
    if any(k in task for k in _LONG_KEYWORDS):
        return _LONG_TIMEOUT
    if any(k in task for k in _QUICK_KEYWORDS):
        return _QUICK_TIMEOUT
    return BASE_TIMEOUT


# ---------------------------------------------------------------------------
# 3. Dispatch — one step as an isolated subprocess, with a hard ceiling.
#    In the real system, build_command reads the shared configuration; here it
#    is a placeholder so nothing external is ever invoked by this example.
# ---------------------------------------------------------------------------

def build_command(seat: Seat, task: str) -> list[str]:
    """Return the subprocess argv for a seat step.

    Real system: agent binary + seat profile, e.g. ``<AGENT_BINARY> -p
    <seat.slug> <task>``, with the binary path resolved from the shared config
    (ADR-0003). This example returns a placeholder that will fail loudly if
    ever executed directly, because the demo passes its own harmless commands.
    """
    return ["<AGENT_BINARY>", "-p", seat.slug, task]


async def dispatch_seat(
    seat: Seat,
    task: str,
    timeout: int,
    command: list[str] | None = None,
) -> dict:
    """Run one step as a subprocess. Kill it if it exceeds its ceiling.

    Returns a dict with ok / seat / output / exit_code / error.
    """
    argv = command if command is not None else build_command(seat, task)
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False, "seat": seat.slug, "output": "",
            "exit_code": -3, "error": f"executable not found: {exc.filename}",
        }

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {
            "ok": False, "seat": seat.slug, "output": "",
            "exit_code": -2, "error": f"timed out after {timeout}s — killed",
        }

    out = stdout.decode(errors="replace").strip()
    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()[:300]
        return {
            "ok": False, "seat": seat.slug, "output": out,
            "exit_code": proc.returncode, "error": err or f"exit {proc.returncode}",
        }
    return {"ok": True, "seat": seat.slug, "output": out,
            "exit_code": 0, "error": None}


async def dispatch_many(steps: list[dict]) -> list[dict]:
    """Launch a wave of steps in parallel; each gets its own resolved timeout.

    A step that names an unknown seat fails that step, not the whole wave —
    but the run still fails loud at the aggregate below.
    """
    async def _run(step: dict) -> dict:
        seat = resolve_seat(step.get("agent", ""))
        if seat is None:
            return {
                "ok": False, "seat": step.get("agent", "<none>"), "output": "",
                "exit_code": -1, "error": f"unknown seat: {step.get('agent')!r}",
            }
        return await dispatch_seat(seat, step.get("task", ""),
                                   resolve_step_timeout(step),
                                   command=step.get("command"))

    return await asyncio.gather(*(_run(s) for s in steps))


# ---------------------------------------------------------------------------
# 4. Fail loud — any step that did not finish fails the whole run (ADR-0002).
# ---------------------------------------------------------------------------

def aggregate_failed(results: list[dict]) -> bool:
    """True if any step did not finish. Empty wave is also a failure."""
    if not results:
        return True
    return any(not r.get("ok") for r in results)


def _fmt_result(r: dict) -> str:
    mark = "ok " if r.get("ok") else "FAIL"
    err = f" — {r['error']}" if r.get("error") else ""
    return f"  {mark} {r.get('seat'):<18} exit={r.get('exit_code')}{err}"


# ---------------------------------------------------------------------------
# 5. Demo — proves the mechanisms with harmless subprocesses only.
# ---------------------------------------------------------------------------

def _demo_seat_resolution() -> int:
    print("== seat resolution ==")
    cases = [
        ("engineering", "engineering"),
        ("data-analytics", "data-analytics"),
        ("Data-Analytics", "data-analytics"),   # case-insensitive
        ("DEVOPS", "devops"),                   # uppercase form
        ("platform_ops", "platform-ops"),       # underscore form
        ("ghost", None),
        ("default", None),                      # a non-seat name
        ("", None),
    ]
    bad = 0
    for name, expected in cases:
        seat = resolve_seat(name)
        got = seat.slug if seat else None
        flag = "PASS" if got == expected else "FAIL"
        if got != expected:
            bad += 1
        print(f"  {flag} resolve_seat({name!r:>16}) -> {got!r}")
    return bad


def _demo_timeout_resolution() -> int:
    print("== step-timeout resolution ==")
    # Rung 4 — base default (nothing matches, no override).
    base = {"agent": "operations", "task": "tidy the workspace"}
    # Rung 3 — step-type default (quick keyword).
    quick = {"agent": "devops", "task": "verify the service is healthy"}
    # Rung 3 — step-type default (long keyword).
    long = {"agent": "engineering", "task": "build the release artifact"}
    # Rung 1 — explicit value always wins.
    explicit = {"agent": "engineering", "task": "run the long migration",
                "timeout_seconds": 45}

    checks = [
        ("base default", resolve_step_timeout(base), BASE_TIMEOUT),
        ("step-type: quick", resolve_step_timeout(quick), _QUICK_TIMEOUT),
        ("step-type: long", resolve_step_timeout(long), _LONG_TIMEOUT),
    ]
    # Rung 2 — environment override; set it only around the resolution that
    # must observe it, so it cannot leak into the other checks.
    os.environ["SEAT_TIMEOUT"] = "900"
    checks.append(
        ("environment override",
         resolve_step_timeout({"agent": "research",
                               "task": "produce a briefing"}),
         900)
    )
    del os.environ["SEAT_TIMEOUT"]
    # Explicit per-step still wins over an env override when both are present.
    os.environ["SEAT_TIMEOUT"] = "900"
    checks.append(("explicit beats env", resolve_step_timeout(explicit), 45))
    del os.environ["SEAT_TIMEOUT"]

    bad = 0
    for label, got, expected in checks:
        flag = "PASS" if got == expected else "FAIL"
        if got != expected:
            bad += 1
        print(f"  {flag} {label:<24} -> {got}s (expected {expected}s)")
    return bad


async def _demo_dispatch() -> int:
    print("== parallel dispatch ==")
    # A harmless wave: one fast step, one long step given a short ceiling to
    # prove the kill path, one unknown seat. Nothing external is invoked.
    wave = [
        {"agent": "engineering", "task": "echo a line",
         "timeout_seconds": 10,
         "command": ["python3", "-c", "print('step one finished')"]},
        {"agent": "research", "task": "produce a deep briefing",
         "timeout_seconds": 1,           # deliberate: too short on purpose
         "command": ["python3", "-c", "import time; time.sleep(30)"]},
        {"agent": "ghost", "task": "do nothing"},
    ]
    results = await dispatch_many(wave)
    for r in results:
        print(_fmt_result(r))

    # Expected behaviors (the point of the demo): the fast step finishes, the
    # step whose ceiling is too short is KILLED (exit -2), the unknown seat is
    # rejected (exit -1), and the aggregate correctly fails loud. If any of
    # these behave differently, the demo fails.
    fast, killed, unknown = results
    checks = [
        ("fast step finished", fast["ok"] is True and fast["exit_code"] == 0),
        ("over-ceiling step killed", killed["ok"] is False
         and killed["exit_code"] == -2 and "killed" in killed["error"]),
        ("unknown seat rejected", unknown["ok"] is False
         and unknown["exit_code"] == -1
         and "unknown seat" in unknown["error"]),
        ("fail-loud aggregate caught it", aggregate_failed(results) is True),
    ]
    bad = 0
    for label, ok in checks:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            bad += 1
        print(f"  {flag} {label}")
    return bad


async def demo() -> int:
    bad = _demo_seat_resolution()
    bad += _demo_timeout_resolution()
    bad += await _demo_dispatch()
    print("=" * 60)
    if bad:
        print("DEMO: FAILED (fail loud — exit 1)")
    else:
        print("DEMO: PASSED (exit 0)")
    return 1 if bad else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swarm-dispatch.py",
        description="Sanitized dispatch layer — seat resolution, per-step "
                    "timeouts, parallel waves, fail-loud. Example only.")
    parser.add_argument("--demo", action="store_true",
                        help="run the self-test demo (no real agents, no "
                             "credentials, harmless subprocesses only)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.demo:
        print("No action requested. Run with --demo to exercise the layer.",
              file=sys.stderr)
        return 2
    return asyncio.run(demo())


if __name__ == "__main__":
    raise SystemExit(main())
