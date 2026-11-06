---
name: HMS QR
colors:
  background: "#f1f5f9"
  background_gradient: "linear-gradient(180deg, #eef4fb 0%, #f1f5f9 220px)"
  surface: "#ffffff"
  surface_raised: "#f8fafc"
  border: "#dbe4ee"
  border_strong: "#c3d2e3"
  primary: "#0f766e"
  primary_strong: "#0b5f59"
  primary_soft: "#e6f4f1"
  primary_dim: "rgba(15, 118, 110, 0.12)"
  success: "#047857"
  success_soft: "#ecfdf5"
  warning: "#b45309"
  warning_soft: "#fffbeb"
  danger: "#b91c1c"
  danger_soft: "#fef2f2"
  info: "#1d4ed8"
  info_soft: "#eff6ff"
  text_primary: "#0f172a"
  text_secondary: "#55637a"
  toast: "#0f172a"
  violet: "#5b21b6"
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "15px"
  base:
    fontSize: "16px"
  secondary:
    fontSize: "13px"
  label:
    fontSize: "12px"
  caption:
    fontSize: "11px"
  closeGlyph:
    fontSize: "18px"
  heading:
    fontWeight: "800"
  button:
    fontWeight: "700"
rounded:
  sm: "8px"
  md: "12px"
  card: "16px"
  lg: "16px"
  xl: "24px"
  chip: "20px"
  line: "2px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
shadows:
  sm: "0 1px 2px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.08)"
  md: "0 4px 12px rgba(15, 23, 42, 0.07), 0 1px 3px rgba(15, 23, 42, 0.05)"
  lg: "0 18px 40px rgba(15, 23, 42, 0.16)"
desktop_colors:
  background: "#f3f1ec"
  surface: "#ffffff"
  surface_raised: "#e7e8e8"
  surface_alt: "#f0f1f2"
  border: "#b8bdc1"
  text_primary: "#333333"
  text_secondary: "#555555"
  text_disabled: "#777777"
  hint_text: "#505a66"
  accent: "#246b9c"
  success: "#2f8f63"
  warning: "#b7791f"
  danger: "#c44747"
  info: "#3b72a6"
  qr_toast_bg: "#147a69"
  qr_toast_border: "#0f5b4e"
desktop_status_colors:
  NEW: "#dceeff"
  WAITING: "#fff1bf"
  IN_PROGRESS: "#cfe9ff"
  WAITING_QC: "#eadcff"
  QC_PASS: "#c7f2d3"
  QC_NG: "#ffd0d0"
  REWORK: "#ffdca8"
  PACKED: "#d9e5f5"
  DELIVERED: "#b8e8c7"
  HOLD: "#ffe0a3"
  CANCELLED: "#e4e4e4"
desktop_typography:
  fontFamily: "Segoe UI"
  fontSize: "13px"
desktop_rounded:
  control: "4px"
desktop_spacing:
  "2": "2px"
  "4": "4px"
  "6": "6px"
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "24": "24px"
  "32": "32px"
---

# HMS QR UI Design Authority — Stage 5 R007

This document is the canonical presentation authority for HMS QR. It governs visual language, tokens, reusable components, responsive behavior, and label presentation. It never overrides domain, API, QR payload, workflow, quantity, or revision authorities.

## Overview

Light neutral industrial software for factory-floor product tracking. High information density on desktop; touch-friendly compact cards on mobile. Vietnamese-first labels. Every status is explicit text plus semantic color and icon — never color alone. The light theme is the canonical acceptance direction (`CANONICAL_THEME=LIGHT`, R007B7D); a dark theme may remain optional in future.

## Four surfaces, one light direction

LO's direction, 2026-11-01: **all UI light, no dark UI.** `CANONICAL_THEME=LIGHT` (R007B7D) is therefore not just the mobile acceptance direction — it is the whole product's. A surface that goes dark has drifted, whatever its history.

Four palettes remain, because the surfaces are deliberately different and reconciling them is a product decision nobody has taken. Agents must read the right one for the surface they are editing, and must not "fix" one toward another.

Two of the four are the same set: the mobile web and the portal declare identical values for all 22 tokens they share, and `test_the_two_surfaces_declare_the_same_value_for_every_shared_token` fails if they ever disagree. The desktop and the Server Tool each have their own.

### Mobile Web / PWA — tokens above

Source of truth: the `:root` block in `web/index.html:14`. `web/lan.html` and `web/vps.html` are derived mechanically by `scripts/build_mobile_web.py` — `index.html` is the program; the other two are the same program minus the connection screen. Never edit them by hand; run `python -m scripts.build_mobile_web`. `tests/stage6/test_mobile_web_builds.py` regenerates both files and fails unless the result is byte-identical to what is committed, so drift becomes a test failure.

> **A missing `<style>` shipped this page unstyled for three days.** Commit `eed607f` (2026-10-31) rewrote `web/index.html` and dropped the opening `<style>` while keeping the closing `</style>` at the end of line 476, so the HTML parser could not place the 463 lines of CSS in a style element and they rendered as character data. `https://hms-qr-product-manager-web.vercel.app/` served HTTP 200 with 0 stylesheets and the browser default Times New Roman. Every guard on that file read bytes — line endings, BOMs, marker counts, byte-identical derivation — and not one asked whether the CSS was *applied*. Fixed 2026-11-03 by inserting the tag and regenerating, plus `test_the_css_is_actually_inside_a_style_element`, which asserts the `<style`/`</style>` counts match and that `--accent` falls inside a style element. **A byte-identical derivation is not a rendered page — verify the styling, not the bytes.**


Look: cool slate background with a soft vertical gradient; white cards on soft shadows with 16px radius; translucent white header bar; teal (`#0f766e`) accent with a teal focus ring on inputs; pills and tabs as 999px-radius chips with 44px minimum touch height; semantic states carry a `-soft` background with dark text so they read on white; the toast is a dark slab on the `--text` ground with `--on-text` ink, because a confirmation has to be unmistakable across a workshop — the *portal*'s toast is the soft success chip, and the two surfaces must not be swapped. `web/manifest.json` and `apps/static/manifest.json` declare the same light background and teal theme-color.

### Portal — `apps/server/portal.py`

Source of truth: its own `:root` block, which carries the **same light tokens as the mobile web** — it is not a third palette. The portal was brought onto this set on 2026-11-01 after it had drifted to a dark one (`--bg: #0d1520`, `--accent: #00d2b4`) that no document covered, which is exactly how a surface escapes the authority. It is named here so that cannot happen silently again.
What the re-theme had to fix beyond the token swap, because each was a latent defect the dark surface had been hiding:

- `var(--card)` was referenced but never declared, so spreadsheet cells, submenus and the context menu resolved to **no background at all**. They use `--card-bg`.
- Hover states were `rgba(255,255,255,0.04–0.08)`, tuned for a dark surface and invisible on a light one. They are `rgba(15,23,42,…)` at equivalent strength.
- The toast was a solid dark-green block; it is now a soft success chip with dark text, matching how semantic states read elsewhere.

The portal's spreadsheet engine (`_SS_CSS`, `_SS_JS`) uses the same tokens; its selection colour is teal rather than the blue it carried while dark.

### Desktop — PySide6

Source of truth: `apps/design_tokens.py`. Warm neutral background (`#f3f1ec`), blue accent (`#246b9c`), 4px control radius, Segoe UI 13px, spacing scale 2/4/6/8/12/16/24/32px. `PY_SIDE_THEME` in that file renders the same names into Qt stylesheet.

### Server Tool — PySide6 (`apps/server/tool.py`)

Source of truth: the `TOOL_TOKENS` block in that file. Cool light ground (`#f4f7fb`), teal accent (`#0b7285`), 8pt Segoe UI at desktop density, and a dark activity-log console (`#102a43` ground, `#d9e2ec` ink — 11.18:1) that is the one inverted panel in the product. `tests/stage6/test_server_tool_palette.py` holds two invariants: no colour outside that block, and every text colour clearing 4.5:1 on the ground it is painted on.

This window was absent from DESIGN.md until 2026-11-05, which is why it is described here at all: it kept 34 colour literals inline in one Qt stylesheet, and nothing read them. They are declared now, with the values they already had — **the only colour that moved is a 0.3% contrast nudge** (`#617487` to `#5d6b7b`, 4.49:1 to 5.07:1, collapsing two secondary-text colours into one). Merging this palette into the desktop's would recolour a shipped surface on a decision nobody has taken, so **whether the Server Tool should share the desktop's blue accent is open** and recorded here rather than answered.

Both are for LO. Neither is guessed at here.

### Radius — recorded, not yet reconciled

The front-matter's `rounded.card` said `14px` while `web/index.html` declares `--radius: 16px` and `.card` reads `var(--radius)`; the body of this document had said 16px all along, so the machine-readable block was the wrong one. `tests/stage6/test_design_document_matches_code.py` now pins `rounded.card` to `--radius` in both directions. That is the **only** radius guard in the tree, and two gaps sit behind it:

- **`web/index.html` carries six hardcoded `border-radius: 14px` rules** (`.btn-cam`, `#toast`, and a second `.card` rule) that bypass `--radius` entirely. This is the same defect as the portal's `#fff`: a value duplicated where no token reaches it, so changing `--radius` later would silently leave six radii behind.
- **The portal declares nine distinct radii** — 10, 8, 4, 6, 2, 14, 9, 12 and 5px — and has **no radius token at all**. It is the shape the Server Tool's palette was in before it was declared.

Whether to introduce `--radius-*` tokens for the web and the portal is a product decision, recorded here rather than taken. The mobile web's byte-identical build (`scripts/build_mobile_web.py`) means any change to `web/index.html` has to be regenerated into `web/lan.html` and `web/vps.html`, not hand-edited.

### Typography, spacing and shadows — recorded, not yet reconciled

Of the four non-colour axes the front-matter declares, **typography is the one that is already true**: it declares six sizes — 11, 12, 13, 15, 16 and 18px — and `web/index.html` uses exactly those six and no others. `tests/stage6/test_design_document_matches_code.py` asserts it, so the one axis that matches stays matching. The other three do not, and each gap is a decision rather than something to guess at:

- **Spacing.** The declared scale is five values (4, 8, 12, 16, 24px). The web uses fourteen distinct values, nine of them off-scale (2, 6, 9, 10, 11, 14, 20, 30, 40); the portal uses twenty, fifteen off-scale (1, 2, 3, 5, 6, 7, 9, 10, 11, 14, 18, 20, 22, 30, 60). The scale describes neither surface.
- **Portal type.** The portal uses five sizes off the declared scale — 10, 14, 17, 19 and 28px. The web does not.
- **Shadows.** The web reads a `--shadow-*` token for 7 of its 13 box-shadows; the portal reads one for **0 of 7** and declares no shadow token at all. That is the shape the portal's colours were in before `:root`.

The radius guard above is the pattern to copy if any of these is taken on: pin the one value the document makes a specific claim about, in both directions, and record the rest.

### Known drift — recorded, not yet reconciled

`apps/design_tokens.py` predates the R007 light-web redesign and no longer describes the web UI: its accent is blue `#246b9c` where the web is teal `#0f766e`, its background is warm `#f3f1ec` where the web is cool `#f1f5f9`, its radius is 4px where the web card is 16px, and its face is Segoe UI where the web uses the system stack. Treat the file as the desktop token source only. Reconciling the two palettes into one token set is a product decision; this file records the difference so an agent never "fixes" one surface toward the other by accident.

The product now carries **four palettes**, not the two this section used to imply: the mobile web and the portal share one token set (22 tokens, identical values, enforced by `test_the_two_surfaces_declare_the_same_value_for_every_shared_token`), the desktop has its own, and the Server Tool has its own. A fifth colour — the QR copy confirmation chip's teal `#147a69` in `product_master_window.py` — matches none of the four and is likewise recorded, not decided.

The front-matter at the top of this file declares the two palettes this document claims as its system — `colors` for the web and portal, `desktop_colors` plus `desktop_status_colors` for the desktop — and `tests/stage6/test_design_document_matches_code.py` asserts the code matches it, in both directions. It had drifted twice before that guard existed: `desktop_colors` declared 12 colours while `apps/design_tokens.py` had grown to 27, and `--violet` lived in `:root` on both web surfaces without being declared anywhere. **A fix that grows a palette must grow this document too**, or the next agent reads a description that is missing half the truth. The Server Tool and the LAN admin page are deliberately outside the front-matter; they are described above with their own token blocks, and folding them in would be the product decision this section defers.

## Status mapping

Keyed by `packages.domain.product.ProductStatus` member name, which is what `order_tracking_items.status` stores. NEW/info, WAITING/warning, IN_PROGRESS/info, WAITING_QC/warning, QC_PASS/success, QC_NG/danger, REWORK/danger, PACKED/success, DELIVERED/success, HOLD/warning, CANCELLED/neutral. Always render status as text plus semantic color and icon.

This mapping was stale until 2026-11-05: it named `IN_PROCESS`, `QC_CHECKED`, `SHORTAGE`, `PACKING` and `PARTIALLY_DELIVERED`, none of which exist in `ProductStatus`, and omitted `NEW`, `WAITING`, `IN_PROGRESS`, `QC_PASS` and `CANCELLED`, which do. `apps/design_tokens.py` copied it verbatim, so the desktop tracking window's `value in STATUS_COLORS` check left five of the eleven statuses with no background colour at all while the design said every status carries one. `tests/stage1/test_design_tokens.py` now fails if this mapping and the enum disagree.

Open for LO, recorded rather than decided: `DELIVERED` is green here and on the desktop, but **violet** on the mobile web (`.qc-deliv`) and in the portal (`--violet`) — a sixth hue that exists in neither palette's declared status set. Which one is right is a product decision; the token guard only enforces that the two web surfaces agree with each other.

## Component and interaction rules

- Mobile action targets are at least 44px; test widths 360/390/414/768 and desktop 1280x720/1366x768/1920x1080.
- Visible keyboard focus everywhere; inputs take a teal focus ring (web) or a 2px accent border (desktop).
- Identifiers use a monospace face and selectable text.
- Inline validation, disabled contrast, and text labels alongside every color.
- Web tokens are declared once in `:root`; new colors join the token block rather than appearing as literals in rules.

## Authorities and boundaries

QR payload remains exactly four fields: `product_name`, `customer_name`, `product_code`, `tracking_code`. Label metadata is presentation-only. Penpot is the canonical visual design artifact authority; UICanvas Local MCP is the rapid exploration and screenshot surface; Open Design is optional historical tooling. Production runtime has no dependency on Penpot, UICanvas, or Open Design. See `docs/design/` for component, desktop, mobile, label, and integration details.
