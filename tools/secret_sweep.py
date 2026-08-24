#!/usr/bin/env python3
"""secret_sweep.py — secret sweep + health watchdog (Asbury Solutions).

Part of the Asbury Solutions public toolchain. Two subcommands:

  scan   Recursively inspect a tree for secret-shaped values, restricted
         addresses, and org-specific deny terms. Read-only: it only
         reports. Exits 0 when clean, 1 when findings exist, 2 on error.
  watch  HTTP(S) health probe for public endpoints (use this before wiring
         uptime badges). Exits 0 when every endpoint is healthy, 1 otherwise.

Standards (FABLE 5):
  - NO SILENT DEFAULTS — every option has an explicit value; rule and deny
    configuration is validated at load and fails loudly with remediation.
  - CONFIRM-GATE SAFETY — this tool is read-only. There is no --apply and
    nothing destructive.
  - SELF-DOCUMENTING — see RUNBOOK.md in this directory.

The scanner detects values (secret-shaped strings, addresses, port numbers)
and named deny terms. Prose describing a policy is not a finding: patterns
here match only actual secret-shaped values, so a sentence like "we rotate
our keys monthly" does not trip the scanner.

Runbook: RUNBOOK.md (same directory).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VERSION = "1.0.0"
PROBE_UA = "AsburySolutions-HealthProbe/1.0"
_SELF = Path(__file__).resolve()

# ---------------------------------------------------------------------------
# Rule table — (name, compiled regex, severity, remediation)
# Patterns are value-shaped so they do not flag prose.
# ---------------------------------------------------------------------------

def _rule(name: str, pattern: str, severity: str, remediation: str):
    return {"name": name, "regex": re.compile(pattern), "severity": severity,
            "remediation": remediation}

RULES = [
    _rule(
        "private-key",
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----",
        "critical",
        "Private key material must never be committed. Rotate if this was ever live.",
    ),
    _rule(
        "openai-style-key",
        r"sk-[A-Za-z0-9]{20,}",
        "critical",
        "Provider API key found. Revoke and replace, then purge from history.",
    ),
    _rule(
        "anthropic-style-key",
        r"sk-ant-[A-Za-z0-9_-]{20,}",
        "critical",
        "Provider API key found. Revoke and replace, then purge from history.",
    ),
    _rule(
        "stripe-style-key",
        r"sk_(?:live|test)_[A-Za-z0-9]{16,}",
        "critical",
        "Payment API key found. Revoke in the dashboard and replace.",
    ),
    _rule(
        "google-api-key",
        r"AIza[0-9A-Za-z_-]{20,}",
        "critical",
        "Cloud API key found. Revoke and scope-down the replacement.",
    ),
    _rule(
        "aws-access-key",
        r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
        "critical",
        "Cloud access key id found. Revoke in IAM and replace.",
    ),
    _rule(
        "github-token",
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        "critical",
        "Source-hosting token found. Revoke and replace.",
    ),
    _rule(
        "slack-token",
        r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
        "critical",
        "Messaging token found. Revoke and replace.",
    ),
    _rule(
        "jwt",
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
        "critical",
        "Signed session/API credential found. Revoke and replace.",
    ),
    _rule(
        "bearer-auth",
        r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}\b",
        "critical",
        "In-flight authorization header value found. Revoke and replace.",
    ),
    _rule(
        "credential-assignment",
        r"(?i)\b(?:api[_-]?key|secret|passwd|password|token|client[_-]?secret"
        r"|auth[_-]?token|access[_-]?key)\b\s*[=:]\s*['\"]?(?!<)[A-Za-z0-9._~+/=-]{8,}",
        "critical",
        "A credential-shaped assignment was found. Replace with a placeholder.",
    ),
    _rule(
        "port-word",
        r"(?i)\bport\s+\d{4,5}\b",
        "high",
        "A service port number appears in prose. Use ':PORT' or omit it.",
    ),
    _rule(
        "ipv4-address",
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "high",
        "Replace any literal network address with a non-address placeholder.",
    ),
    _rule(
        "port-number",
        r"(?<![\d:.]):\d{4,5}(?!\d)",
        "high",
        "Service port numbers must not appear here. Use ':PORT' or omit.",
    ),
    _rule(
        "email-address",
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "high",
        "Personal contact detail must not appear. Replace with a placeholder.",
    ),
]

# Filename rules: a file whose name matches is a finding regardless of body.
FILENAME_RULES = [
    (re.compile(r"(?:^\.env(?:$|[^.]|\.(?!example))|\.env$)", re.I),
     "dot-env file",
     "critical",
     "Environment files must not be committed. See .gitignore and keep a template only."),
    (re.compile(r"\.(?:pem|p12|p8|pfx|key)$", re.I),
     "key/certificate file",
     "critical",
     "Key material must not be committed. Rotate if it was ever live."),
    (re.compile(r"^(?:id_rsa|id_ed25519|id_ecdsa)$"),
     "ssh private key file",
     "critical",
     "SSH key material must not be committed."),
]

# Paths always skipped, plus --exclude additions.
DEFAULT_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache"}


def classify_address(addr: str) -> str:
    """Return a human label for an IPv4 address (private, loopback, ...)."""
    try:
        parts = [int(p) for p in addr.split(".")]
    except ValueError:
        return "unknown"
    if len(parts) != 4:
        return "unknown"
    a, b = parts[0], parts[1]
    if a == 127:
        return "loopback"
    if a == 169 and b == 254:
        return "link-local"
    if a == 10 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168):
        return "private"
    if a == 100 and 64 <= b <= 127:
        return "shared mesh address space"
    if a == 0 or a >= 224:
        return "reserved/multicast"
    return "public"


def load_deny_terms(path: str | None) -> list[str]:
    """Load org-specific deny terms from a JSON file. Fails loudly if invalid."""
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"ERROR: deny file not found: {path}\n"
                         "Remediation: point --deny-file at a JSON file like "
                         "tools/deny-terms.example.json")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: deny file is not valid JSON: {path}\n  {exc}\n"
                         "Remediation: fix the file to {\"terms\": [...]}")
    if not isinstance(data, dict) or "terms" not in data:
        raise SystemExit(f"ERROR: deny file must be a JSON object with a "
                         f"'terms' array: {path}")
    terms = data["terms"]
    if not isinstance(terms, list) or not all(isinstance(t, str) and t.strip()
                                               for t in terms):
        raise SystemExit(f"ERROR: 'terms' must be a list of non-empty strings: {path}")
    return [t.strip() for t in terms]


def scan_tree(root: Path, extra_skip: set[str], deny_terms: list[str],
              include_self: bool) -> tuple[list[dict], int]:
    """Walk root and return (findings, files_scanned)."""
    skip_dirs = DEFAULT_SKIP_DIRS | set(extra_skip)
    findings: list[dict] = []
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs
                       and not d.startswith(".")]
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if not include_self and fpath.resolve() == _SELF:
                continue
            files_scanned += 1

            # Filename-based rules.
            for pat, label, sev, remed in FILENAME_RULES:
                if pat.search(fname):
                    findings.append({
                        "file": str(fpath.relative_to(root)),
                        "line": 1, "col": 1, "rule": label, "severity": sev,
                        "snippet": fname, "remediation": remed,
                    })
                    break

            try:
                raw = fpath.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw[:4096]:
                continue  # binary
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                continue

            for line_no, line in enumerate(text.splitlines(), start=1):
                for rule in RULES:
                    for m in rule["regex"].finditer(line):
                        snippet = line.strip()[:200]
                        # Addresses: refine the label.
                        rem = rule["remediation"]
                        sev = rule["severity"]
                        if rule["name"] == "ipv4-address":
                            kind = classify_address(m.group(0))
                            rem = f"Found a {kind} address. " + rem
                            if kind in ("loopback", "link-local", "reserved/multicast"):
                                sev = "medium"
                        findings.append({
                            "file": str(fpath.relative_to(root)),
                            "line": line_no,
                            "col": m.start() + 1,
                            "rule": rule["name"],
                            "severity": sev,
                            "snippet": snippet,
                            "remediation": rem,
                        })

                for term in deny_terms:
                    low = line.lower()
                    if term.lower() in low:
                        findings.append({
                            "file": str(fpath.relative_to(root)),
                            "line": line_no,
                            "col": low.index(term.lower()) + 1,
                            "rule": f"deny-term: {term}",
                            "severity": "high",
                            "snippet": line.strip()[:200],
                            "remediation": "Org-specific term present. Remove or "
                                           "redact before publishing.",
                        })

    return findings, files_scanned


def cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"ERROR: scan path is not a directory: {args.path}", file=sys.stderr)
        return 2
    deny_terms = load_deny_terms(args.deny_file)
    findings, files_scanned = scan_tree(root, args.exclude, deny_terms,
                                        args.include_self)

    if args.json:
        print(json.dumps({
            "tool": "secret_sweep.py", "version": VERSION,
            "root": str(root), "files_scanned": files_scanned,
            "findings": findings,
            "clean": not findings,
        }, indent=2))
    else:
        if findings:
            print(f"FINDINGS ({len(findings)}) in {root}:")
            for f in findings:
                loc = f"{f['file']}:{f['line']}:{f['col']}"
                print(f"  [{f['severity']:>8}] {f['rule']}")
                print(f"           at {loc}")
                print(f"           {f['snippet']}")
                print(f"           fix: {f['remediation']}")
        else:
            print(f"CLEAN — {files_scanned} files scanned in {root}, "
                  f"no findings.")
        print(f"Summary: {files_scanned} files, {len(findings)} finding(s).")

    return 1 if findings else 0


def probe(url: str, timeout: int) -> dict:
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": PROBE_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"url": url, "status": resp.status,
                    "elapsed": round(time.monotonic() - start, 3),
                    "ok": 200 <= resp.status < 400}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": exc.code,
                "elapsed": round(time.monotonic() - start, 3),
                "ok": 200 <= exc.code < 400}
    except Exception as exc:
        return {"url": url, "status": None,
                "elapsed": round(time.monotonic() - start, 3),
                "ok": False, "error": str(exc)}


def cmd_watch(args: argparse.Namespace) -> int:
    if not args.urls:
        print("ERROR: watch requires at least one URL.", file=sys.stderr)
        return 2
    print(f"Probing {len(args.urls)} endpoint(s), timeout={args.timeout}s ...")
    with ThreadPoolExecutor(max_workers=min(len(args.urls), 8)) as pool:
        results = list(pool.map(lambda u: probe(u, args.timeout), args.urls))
    failed = 0
    for r in results:
        if r["ok"]:
            print(f"  OK   {r['status']} {r['url']} ({r['elapsed']}s)")
        else:
            failed += 1
            err = r.get("error", "unhealthy status")
            print(f"  FAIL {r.get('status', 'ERR')} {r['url']} "
                  f"({r['elapsed']}s) — {err}")
    print(f"Summary: {len(results) - failed}/{len(results)} healthy.")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secret_sweep.py",
        description="Secret sweep + health watchdog (Asbury Solutions). "
                    "Read-only; see RUNBOOK.md.")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="scan a tree for secrets/addresses")
    scan.add_argument("path", help="directory to scan")
    scan.add_argument("--deny-file", metavar="FILE",
                      help="JSON file of org-specific terms ({\"terms\": [...]})")
    scan.add_argument("--exclude", action="append", default=[],
                      help="extra directory name to skip (repeatable)")
    scan.add_argument("--json", action="store_true", help="emit JSON report")
    scan.add_argument("--include-self", action="store_true",
                      help="also scan this tool's own source (default: skip "
                           "the detector so its pattern table is not "
                           "misread as findings)")
    scan.set_defaults(func=cmd_scan)

    watch = sub.add_parser("watch", help="probe HTTP(S) endpoints for health")
    watch.add_argument("urls", nargs="+", help="endpoints to probe")
    watch.add_argument("--timeout", type=int, default=10,
                       help="per-request timeout in seconds (default: 10)")
    watch.set_defaults(func=cmd_watch)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
