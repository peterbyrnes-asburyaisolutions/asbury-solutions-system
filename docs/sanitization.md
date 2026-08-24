# Sanitization Policy

This repository is the **public** face of a production system. It is built to
show *how* the system works — never *where* it lives, *who* it serves, or
*what* it holds.

## Deliberately excluded

The following are **never** committed here, by policy:

| Category | Examples that must not appear |
|----------|-------------------------------|
| Credentials | API keys, tokens, bearer secrets, private keys, `sk-*`, `ghp_*`, passwords |
| Identity | Personal names, emails, phone numbers, physical addresses |
| Client data | Client names, customer records, contact lists, internal costs |
| Live endpoints | Hostnames, DNS records, cloud tunnel URLs, public URLs |
| Network topology | IP addresses, tailnet addresses, ports, bind addresses |
| Internal state | Live task counts, revenue, latency figures, database contents, runbooks with operational detail |
| File paths | Any user home path, profile directories, internal repo paths |

## Why

- **Zero-fabrication rule:** this repo only ever shows what the system really
  is — nothing invented, nothing dressed up.
- **Zero-leak rule:** a public architecture repo is valuable precisely because
  it can be opened by anyone. Anything that would let someone reach the live
  system, identify a customer, or read internal state stays out.

## The boundary in practice

- Architecture diagrams: **in** (no addresses).
- Tech stack: **in** (technology names are public facts).
- Decisions-as-code: **in** (rationale is not sensitive).
- Sample configs: **in** (placeholders only — real values live nowhere in this
  repo).
- Deployment runbook, live endpoints, port registry, security posture: **out**.

## Verification

Before any publish, a secret sweep is run across the full tree and git
history (fresh repo = clean history by construction). Any hit on the excluded
categories above blocks publish until removed.
