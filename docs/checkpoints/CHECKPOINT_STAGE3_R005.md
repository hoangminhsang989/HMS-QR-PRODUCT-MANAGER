# CHECKPOINT

Date: 2026-08-13
Stage: Stage 3 — Order Tracking Item + QR + Mobile Process Reporting
WP: Tracking identity + QR issuance + mobile/web process reporting
Revision: R005

## Baseline and candidate

- Main baseline HEAD/tree: `2aed6e945543d2d190bf932a30330032608f95e2` /
  `f956fc07e4f5503b7624c808ff18b22e305255ae`
- Candidate branch: `stage3-tracking-qr-process-reporting`
- Candidate HEAD/tree: pending final candidate commit
- Main: unchanged; R005 does not authorize integration

## Delivered

- Separate Product, Order, Tracking Item, and opaque QR public identities.
- Delivery-date change preserving tracking code/QR with audit metadata.
- Transactional new-order occurrence with new order/tracking/QR identities.
- QR issue/reissue/render and live scan resolution.
- Operator profiles, server-side machining preferences, configurable machining
  types, per-item/per-process attempt expansion.
- Idempotent attempt/completion report events and append-only revisions.
- Tracking/scan/process APIs, mobile-first web page, and desktop tracking window.
- SQLAlchemy/Alembic Stage 3 schema and focused integration tests.

## Truthful external gaps

No Routing engine, QC, packing, delivery transactions, NAS production write,
PostgreSQL production integration, Machine A deployment, production auth, or
real iPhone/Android camera PASS is claimed.
