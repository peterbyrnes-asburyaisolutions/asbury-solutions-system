# Tech Stack

Every technology below is what the system actually runs on. No credentials,
no endpoints, no ports — just the stack and the reason each piece is there.

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3 | The whole org runtime — kernel, orchestrator, fleet harness — is Python. |
| Kernel web app | Flask (threaded) | One lightweight process serves the dashboard/API and hosts the scheduler + watchdog background threads. |
| Task ledger | SQLite (WAL mode) | Durable, zero-ops storage for tasks, schedules, memory, alerts, and latency history. No database server to run. |
| Agent runtime | Hermes agent platform | Each seat is a real Hermes agent profile: identity, config, memory, skills, tool allow-list. |
| Orchestration | Python orchestrator + dispatcher | Planner breaks a task into steps; dispatcher launches each step as a real seat subprocess; parallel waves via `dispatch_many`. |
| Process management | systemd user units | Kernel and side services run as user units with auto-restart; no containerization for the org runtime. |
| Host | Linux (WSL2) | Single-machine deployment — the whole company runs on one box. |
| Frontends | HTML + Tailwind · React (Vite) · PWA · Expo/React Native | Dashboard (server-rendered), product PWAs, and mobile apps share the same backend. |
| Payments | Stripe Checkout + webhooks | Product storefronts and subscriptions; webhooks normalize and persist payment events. |
| Voice | Twilio Media Streams + WebSocket | Real-time phone voice agent (STT → LLM → TTS) with a public HTTPS + WSS path. |
| Edge functions | Cloudflare Workers | Serverless endpoints for storefront APIs, payment webhooks, product delivery, and intake. |
| Auth | Clerk · JWT | Managed auth on web products; signed tokens for internal APIs. |
| Search / research | MCP + web tooling | Research seat gets live web + MCP-backed tooling. |
| Infrastructure as code | Config files + runbooks in-repo | Configs, presets, and runbooks are version-controlled next to the code. |

## Deliberate non-choices

- **No Docker** for the org runtime — a recorded decision
  ([`docs/decisions/0006-no-docker-org-runtime.md`](decisions/0006-no-docker-org-runtime.md)).
- **No per-seat API keys** — one shared auth source
  ([`docs/decisions/0003-single-auth-source.md`](decisions/0003-single-auth-source.md)).
- **SQLite over a client-server DB** for the core ledger — see
  [`docs/decisions/0007-sqlite-wal-ledger.md`](decisions/0007-sqlite-wal-ledger.md).

## Products built on this system (system-level)

- **Agent organization** — this repo.
- **Voice agent** — real-time phone agent (Twilio Media Streams).
- **Digital product storefronts** — Stripe Checkout + edge delivery.
- **Dealership vertical** — config-driven chatbot product + lead capture.
- **Industry tooling** — a niche comparison PWA (React 19 + Express API + Neon
  Postgres), and a permit-automation engine (Flask + PDF generation) with
  client iOS apps.

The stack is deliberately boring in the middle (Flask + SQLite + systemd) and
interesting at the edges (real agents, real voice, real payments). Boring
middle = durable and self-hostable; interesting edges = what the company ships.
