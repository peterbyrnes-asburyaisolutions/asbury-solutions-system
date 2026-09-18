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

## 2026-09-18 — Phase 0 verification

- EverOS subtree import from `EverMind-AI/EverOS` `main` @ `5076683` (v1.3.1).
  `git rev-list --count` on the subtree parent is 102 commits (matches upstream tip).
- Path-filtered `git log -- memory/` shows 1 commit because historical paths lack the
  `memory/` prefix; full history is reachable via the subtree merge parent.
- `make ci` inside `memory/` fails the file-size gate on this orphan monorepo branch
  because there is no merge-base with asbury `origin/main`. Workaround: pass
  `--base 5076683…` (the imported EverOS tip). Root `Makefile` will wire this.
- Firmware reconstructed (no upstream repo). `pio run` succeeds.

## 2026-09-18 — Phase 1 dependency choices

- **Python**: `requires-python = ">=3.12"` already covers 3.12/3.13 (CI tests both).
  No pin change.
- **everalgo-***: left at existing pins (`everalgo-boundary==0.2.1` etc.). Upstream
  comments warn that boundary 0.3.0 breaks `DetectionResult` ABI vs agent-memory 0.4.0.
- **espressif32 platform**: stay on `espressif32 @ ^6.9.0` (Arduino core 2.x).
  Defer `pioarduino` / Arduino 3.x — WiFiClientSecure + SdFat migration risk without
  hardware soak; CA bundle API already works on 6.x via `setCACertBundle`.
- **TLS**: embedded Mozilla CA bundle (~56 KB, 121 certs) generated with ESP-IDF 4.4
  `gen_crt_bundle.py`. `llm.tls_insecure` defaults to false.
