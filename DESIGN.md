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
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "13px"
  base:
    fontSize: "16px"
  label:
    fontSize: "12px"
  caption:
    fontSize: "11px"
  heading:
    fontWeight: "800"
  button:
    fontWeight: "700"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
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
  border: "#b8bdc1"
  text_primary: "#333333"
  text_secondary: "#555555"
  text_disabled: "#777777"
  accent: "#246b9c"
  success: "#2f8f63"
  warning: "#b7791f"
  danger: "#c44747"
  info: "#3b72a6"
desktop_typography:
  fontFamily: "Segoe UI"
  fontSize: "13px"
desktop_rounded:
  control: "4px"
---

# HMS QR UI Design Authority — Stage 5 R007

This document is the canonical presentation authority for HMS QR. It governs visual language, tokens, reusable components, responsive behavior, and label presentation. It never overrides domain, API, QR payload, workflow, quantity, or revision authorities.

## Overview

Light neutral industrial software for factory-floor product tracking. High information density on desktop; touch-friendly compact cards on mobile. Vietnamese-first labels. Every status is explicit text plus semantic color and icon — never color alone. The light theme is the canonical acceptance direction (`CANONICAL_THEME=LIGHT`, R007B7D); a dark theme may remain optional in future.

## Three surfaces, one light direction

LO's direction, 2026-11-01: **all UI light, no dark UI.** `CANONICAL_THEME=LIGHT` (R007B7D) is therefore not just the mobile acceptance direction — it is the whole product's. A surface that goes dark has drifted, whatever its history.

Two token sets remain, because the desktop and the web are deliberately different palettes. Agents must read the right one for the surface they are editing.

### Mobile Web / PWA — tokens above

Source of truth: the `:root` block in `web/index.html:14`. `web/lan.html` and `web/vps.html` are derived mechanically by `scripts/build_mobile_web.py` — `index.html` is the program; the other two are the same program minus the connection screen. Never edit them by hand; run `python -m scripts.build_mobile_web`. `tests/stage6/test_mobile_web_builds.py` regenerates both files and fails unless the result is byte-identical to what is committed, so drift becomes a test failure.

Look: cool slate background with a soft vertical gradient; white cards on soft shadows with 16px radius; translucent white header bar; teal (`#0f766e`) accent with a teal focus ring on inputs; pills and tabs as 999px-radius chips with 44px minimum touch height; semantic states carry a `-soft` background with dark text so they read on white; the toast is a soft success chip with dark text, never a solid dark block. `web/manifest.json` and `apps/static/manifest.json` declare the same light background and teal theme-color.

### Portal — `apps/server/portal.py`

Source of truth: its own `:root` block, which carries the **same light tokens as the mobile web** — it is not a third palette. The portal was brought onto this set on 2026-11-01 after it had drifted to a dark one (`--bg: #0d1520`, `--accent: #00d2b4`) that no document covered, which is exactly how a surface escapes the authority. It is named here so that cannot happen silently again.

What the re-theme had to fix beyond the token swap, because each was a latent defect the dark surface had been hiding:

- `var(--card)` was referenced but never declared, so spreadsheet cells, submenus and the context menu resolved to **no background at all**. They use `--card-bg`.
- Hover states were `rgba(255,255,255,0.04–0.08)`, tuned for a dark surface and invisible on a light one. They are `rgba(15,23,42,…)` at equivalent strength.
- The toast was a solid dark-green block; it is now a soft success chip with dark text, matching how semantic states read elsewhere.

The portal's spreadsheet engine (`_SS_CSS`, `_SS_JS`) uses the same tokens; its selection colour is teal rather than the blue it carried while dark.

### Desktop — PySide6

Source of truth: `apps/design_tokens.py`. Warm neutral background (`#f3f1ec`), blue accent (`#246b9c`), 4px control radius, Segoe UI 13px, spacing scale 2/4/6/8/12/16/24/32px. `PY_SIDE_THEME` in that file renders the same names into Qt stylesheet.

### Known drift — recorded, not yet reconciled

`apps/design_tokens.py` predates the R007 light-web redesign and no longer describes the web UI: its accent is blue `#246b9c` where the web is teal `#0f766e`, its background is warm `#f3f1ec` where the web is cool `#f1f5f9`, its radius is 4px where the web card is 16px, and its face is Segoe UI where the web uses the system stack. Treat the file as the desktop token source only. Reconciling the two palettes into one token set is a product decision; this file records the difference so an agent never "fixes" one surface toward the other by accident.

## Status mapping

IN_PROCESS/info, WAITING_QC/warning, QC_CHECKED/success, QC_NG/danger, REWORK/danger, SHORTAGE/warning, PACKING/info, PACKED/success, PARTIALLY_DELIVERED/info, DELIVERED/success, HOLD/warning. Always render status as text plus semantic color and icon.

## Component and interaction rules

- Mobile action targets are at least 44px; test widths 360/390/414/768 and desktop 1280x720/1366x768/1920x1080.
- Visible keyboard focus everywhere; inputs take a teal focus ring (web) or a 2px accent border (desktop).
- Identifiers use a monospace face and selectable text.
- Inline validation, disabled contrast, and text labels alongside every color.
- Web tokens are declared once in `:root`; new colors join the token block rather than appearing as literals in rules.

## Authorities and boundaries

QR payload remains exactly four fields: `product_name`, `customer_name`, `product_code`, `tracking_code`. Label metadata is presentation-only. Penpot is the canonical visual design artifact authority; UICanvas Local MCP is the rapid exploration and screenshot surface; Open Design is optional historical tooling. Production runtime has no dependency on Penpot, UICanvas, or Open Design. See `docs/design/` for component, desktop, mobile, label, and integration details.
