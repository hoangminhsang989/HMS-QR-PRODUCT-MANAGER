# CHECKPOINT

Date: 2026-08-13
Stage: Stage 3 — Order Tracking Item + QR + Mobile Process Reporting
WP: Tracking identity + QR issuance + mobile/web process reporting
Revision: R005

## Baseline and candidate

- Main baseline HEAD/tree: `2aed6e945543d2d190bf932a30330032608f95e2` /
  `f956fc07e4f5503b7624c808ff18b22e305255ae`
- Candidate branch: `stage3-tracking-qr-process-reporting`
- Candidate HEAD: `ff5ca53bc14478a3b4a1cd9afa9adf255be6deaf`
- Candidate tree: `18ed0196cf0b1d156d0812bcfad8a139258cd442`
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

## Evidence

```text
DIFF_REVIEW_FILE_COUNT=9 direct source changes plus 25 committed paths total
UNRELATED_CHANGE_COUNT=0
Full regression: 20 passed, 1 external warning
ALEMBIC_SQLITE_MIGRATION_SMOKE_PASS
TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION
git diff --check: PASS
Browser responsive check: 390x844, scrollWidth == clientWidth, no console errors
```
