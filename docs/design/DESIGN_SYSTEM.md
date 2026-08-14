# Design system

Tokens live in `apps/design_tokens.py`: a soft light-neutral background, white panels, light-gray raised surfaces, neutral borders, dark charcoal text, blue accent, and semantic success/warning/danger/info colors. Spacing is 2/4/6/8/12/16/24/32px. Desktop base text is 13px; mobile base text is 16px. Identifiers use a monospace face and selectable text.

R007B7D canonical theme override: `CANONICAL_THEME=LIGHT`. Light mode is the
default acceptance direction for PySide6, Mobile Web/PWA, and Penpot A–G. The
industrial character remains compact, high-density, Vietnamese-first, and
mechanical; light surfaces replace dark-mode-first presentation without
changing domain, workflow, or QR contracts.

R007B4 toolchain boundary: Penpot is the canonical visual design artifact
authority; UICanvas Local MCP is the rapid exploration/screenshot surface.
Neither tool, and neither Open Design, is a production runtime dependency.
Penpot/UICanvas artifacts must reuse these tokens and must not alter domain,
workflow, or QR authorities.

Accessibility baseline: visible keyboard focus, text labels alongside color, disabled contrast, inline validation, and 44px minimum mobile action targets. Test widths are 360/390/414/768 and desktop 1280x720/1366x768/1920x1080.
