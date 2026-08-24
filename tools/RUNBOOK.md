# RUNBOOK — secret_sweep.py

**Tool:** `tools/secret_sweep.py` · **Owner:** devops · **Version:** 1.0.0
**Stack:** Python 3 (stdlib only — no dependencies)
**Use:** pre-publish gate for any public surface (this repo, badges, docs).

A read-only secret sweep and health watchdog. It never modifies files and it
never contacts anything on its own — `watch` probes only the URLs you give it.

---

## When to run this

- **Before every push / publish** — `scan` the full tree. Any finding blocks
  publish until removed (zero-leak rule, see `docs/sanitization.md`).
- **Before wiring uptime badges** — `watch` the public endpoints to confirm
  they are healthy and return only public-safe data.
- **In CI** — run `scan` as a gate step. Any finding exits 1 and fails the
  build.

## Quick start

```bash
# 1. Full-tree scan (clean = exit 0)
python3 tools/secret_sweep.py scan .

# 2. Scan including org-specific deny terms (keep the terms file LOCAL)
python3 tools/secret_sweep.py scan . --deny-file /path/to/local-terms.json

# 3. Probe public endpoints before wiring badges
python3 tools/secret_sweep.py watch https://example.com/health https://example.com

# 4. Machine-readable report (for CI / logging)
python3 tools/secret_sweep.py scan . --json
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | Clean (scan) / all endpoints healthy (watch) |
| 1    | Findings found (scan) / one or more endpoints failed (watch) |
| 2    | Usage or configuration error (bad path, bad deny file, no URLs) |

## What `scan` detects

Detection is **value-shaped**: patterns match actual secret-shaped strings,
not prose. A sentence like "we rotate our keys" will not trip the scanner.

| Rule | Detects |
|------|---------|
| `private-key` | PEM/OpenSSH `BEGIN ... PRIVATE KEY` blocks |
| `*-style-key` | `sk-*`, `sk-ant-*`, Stripe `sk_live_`/`sk_test_` keys |
| `google-api-key` | `AIza...` cloud keys |
| `aws-access-key` | `AKIA`/`ASIA` access-key ids |
| `github-token` | `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` tokens |
| `slack-token` | `xox[baprs]-...` tokens |
| `jwt` | `eyJ...` signed credentials |
| `bearer-auth` | inline `Bearer <credential>` headers |
| `credential-assignment` | `KEY=value` / `key: value` credential pairs |
| `ipv4-address` | literal IPv4 addresses (labeled private/public/loopback/...) |
| `port-number` | `:NNNN` service port numbers |
| `email-address` | personal/contact email addresses |
| filename rules | committed `.env`, `*.pem`, `*.key`, `id_rsa`, ... |

### Org-specific deny terms (never baked into the repo)

Put client names, personal names, internal hostnames, or internal paths in a
local JSON file and pass it with `--deny-file`. The committed
`tools/deny-terms.example.json` ships with an empty `terms` array — the real
list stays local so nothing org-specific is ever committed.

```json
{ "terms": ["term-one", "term-two"] }
```

### What `scan` skips

- `.git`, `.venv`, `node_modules`, `__pycache__`, other cache dirs
- binary files (containing NUL bytes)
- its own source file (so the pattern table is not misread as findings);
  pass `--include-self` to also scan the detector
- extra dirs via `--exclude DIR` (repeatable)

## What `watch` does

Sends a GET to each URL (10s timeout by default), reports status code and
latency, and requires `2xx`/`3xx` to count as healthy. Use it to confirm the
badge endpoints return `200` and expose no sensitive data *before* wiring
badges.

## Remediation when a finding appears

1. Remove or replace the value with a placeholder (e.g. `sk-xxx` → `<KEY>`).
2. If the value was ever live, **rotate/revoke it** — removing it from the
   repo is not enough.
3. Re-run `scan` until it exits 0.
4. If the finding is a false positive (prose describing policy, placeholder,
   intentional sample), note it in the sweep log and record the rationale —
   do not silently waive it.

## FABLE 5 compliance

- **CONFIRM-GATE SAFETY** — read-only; nothing is applied, patched, or deleted.
- **CONTRACT-FIRST DATA** — deny-file schema (`{"terms": [...]}`) is validated
  at load and fails loudly on any deviation.
- **NO SILENT DEFAULTS** — every flag has an explicit value; invalid paths,
  bad JSON, and missing URLs abort with remediation text.
- **SELF-DOCUMENTING RUNBOOKS** — this file is the runbook.
- **ROLE-AGNOSTIC THINKING** — a generic scanner any seat can run; org-specific
  policy is injected at runtime, not compiled in.

— devops · Asbury Solutions · 2026-08-24
