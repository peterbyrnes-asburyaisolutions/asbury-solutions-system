# Harbor Grit — Diagram Style Spec (D7 public skeleton)

**Owner:** creative-director (Delacroix) · **Version:** 1.0 · **2026-08-23**
**Scope:** Every diagram in the public GitHub skeleton (`docs/*.svg`) must follow
this spec. `architecture.svg` and `banner.svg` are the approved references.

---

## 1. The tokens (binding — no exceptions)

| Token | Value | Use |
|-------|-------|-----|
| `paper` | `#F2EFE8` | canvas background (cream) |
| `surface` | `#FFFFFF` | white plates / boxes |
| `ink` | `#111111` | all text, primary strokes |
| `signal` | `#E6441F` | ONE accent per diagram (fail-loud, brand rule, "live" marker) |
| `muted` | `#5A5A5A` | secondary / caption text |
| `line` | `#161616` | 2px hard rules and borders |
| `shadow` | `#171717` | hard offset shadow (drawn as a rect behind a plate, +4/+4px, no blur) |

**Fonts:** `Archivo Black` (headlines, 900 weight) · `IBM Plex Mono` (labels,
captions, metadata). Two weights max. No serif, no extra families.

**Radius: 0.** No rounded corners. No gradients, no glass, no glow, no blur.

## 2. Hard design rules

1. **One signal accent per diagram.** Everything else ink/muted on paper.
2. **2px hard borders** on every box and the canvas frame. Shadows are hard
   offset rects (`#171717`), never soft/diffuse.
3. **Left-aligned text.** Never center-align body labels. Headlines may be
   left-aligned on their box; no centered layout.
4. **8px grid.** All coordinates, padding, and spacing are multiples of 8.
5. **No decorative boxes.** Every element is a real system component. No
   gradient orbs, no "brain" icons, no purple/cyan/neon.
6. **Every SVG is hand-written** (coordinates explicit), so it renders anywhere
   GitHub shows it — no JS, no external fonts, no raster dependencies.

## 3. Content rules (charter Appendix B — binding)

- **Social brand:** the label reads **"Asbury Solutions"**. The string "Asbury
  AI Solutions" never appears in a diagram.
- **No "AI" in labels.** Say "agent operating system", "the fleet", "seats".
  Plain words. No hype.
- **System only.** No ports, endpoints, tailnet IPs, credentials, tokens,
  client names, CRM data, internal costs, or security posture. If a box would
  need one of those to be drawn, the box is redrawn without it.
- **Zero fabrication.** No invented components, metrics, or flows. Every box
  traces to a real sanitized system part.

## 4. Layout conventions

- Canvas frame: 2px `line` inset 6px from every edge.
- Header band: white plate with a 6px signal rule on the left, hard shadow
  behind, title in `headline` 34px, subtitle in `mono` 16px `muted`.
- Boxes: `surface` fill, 2px `line` stroke, hard shadow plate behind.
- Arrows: drawn *before* boxes (behind them), ink 2px, filled arrowhead.
- Flow accent: a dashed `signal` path marks the fail-loud contract.
- Grouping: a `line`-only outlined plate with a 6px signal top rule names a
  region (e.g. "Fifteen seats — the fleet").
- Footer: full-width `paper` rail, `mono` 12px, brand left, "Harbor Grit ·
  zero slop" right.

## 5. Naming & exports

- Source of truth is always the `.svg`. PNG is an export (`rsvg-convert`),
  never edited directly.
- File names: `banner.svg` (README hero), `architecture.svg` (canonical
  system), `<topic>.svg` for any further diagrams.
- Keep `viewBox` matching `width`/`height` (1:1 user units).

## 6. Review gate

Before a diagram ships in the public repo:
1. `rsvg-convert` renders without error.
2. Zero `#E6441F`-on-`#F2EFE8` contrast violations on text (signal is for
   accents/headlines at weight 900 or 7px+ rules, not body copy).
3. Anti-slop validator clean on any `.html` wrapper (run the project's
   validator in `--ci` mode).
4. Devops secret-sweep passes before publish.
5. **The gut check:** if a reviewer thinks the diagram came out of an AI
   template, it gets redrawn. No exceptions.
