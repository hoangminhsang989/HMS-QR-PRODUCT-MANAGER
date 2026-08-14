# HMS QR UI Design Authority — Stage 5 R007

This document is the canonical presentation authority for HMS QR. It governs visual language, tokens, reusable components, responsive behavior, and label presentation. It never overrides domain, API, QR payload, workflow, quantity, or revision authorities.

Direction: light neutral industrial software; high information density on desktop, touch-friendly compact cards on mobile, Vietnamese-first labels, explicit status text plus semantic color/icon (never color alone). The light theme is the canonical/default Stage 5 acceptance direction; a future dark theme may remain optional.

Canonical token source: `apps/design_tokens.py`. Web CSS variables and PySide6 theme values are generated from the same semantic names. Penpot is the intended canonical visual design artifact authority; UICanvas Local MCP is the rapid exploration and screenshot surface. Open Design is optional historical tooling only. Production runtime has no dependency on Penpot, UICanvas, or Open Design.

Status mapping: IN_PROCESS/info, WAITING_QC/warning, QC_CHECKED/success, QC_NG/danger, REWORK/danger, SHORTAGE/warning, PACKING/info, PACKED/success, PARTIALLY_DELIVERED/info, DELIVERED/success, HOLD/warning.

QR payload remains exactly four fields: `product_name`, `customer_name`, `product_code`, `tracking_code`. Label metadata is presentation-only.

See `docs/design/` for component, desktop, mobile, label, and integration details.
