# Decisions

## 2026-09-18 — Delivery remote and missing sources

- **Attached Cloud Agent repo** is `peterbyrnes-asburyaisolutions/asbury-solutions-system`,
  not `byrnespe/agentic-os`. `byrnespe/agentic-os` returns 404 and cannot be created
  with this token. Work ships on branch `claude/consolidate-repos-update-501d9y`
  here until the target repo exists.
- **`byrnespe/agentic-operating-system`** returns 404. Firmware under
  `firmware/genesis-mini/` is reconstructed from the consolidation task
  specification (layout, APIs, SD card image, PlatformIO env). No upstream
  git history was available to preserve via `git subtree`.
- **EverOS import source**: `EverMind-AI/EverOS` `main` (canonical upstream,
  currently v1.3.x). `byrnespe/EverOS` is a stale public fork (last synced
  ~2026-06) without release tags; using upstream preserves full history and a
  green baseline for Phase 1 upgrades.
