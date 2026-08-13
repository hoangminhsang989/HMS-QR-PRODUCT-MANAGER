# CHECKPOINT

Date: 2026-08-13
Stage: Stage 2 — Customer + PO + Production Run
WP: Customer + PO + Production Run vertical slice
Revision: R004

## Baseline and candidate

- Main baseline: `bc9e8f0aecd2a2fd1644937365d6b088794ef77c`
- Baseline tree: `2b823a55b6f464161a265f3bff61bbbae73638d7`
- Candidate branch: `stage2-customer-po-production-run`
- Candidate HEAD/tree: pending final candidate commit
- Main: unchanged; no integration authorized by R004

## Delivered

- Customer, PurchaseOrder, PurchaseOrderLine, DeliveryScheduleEntry, and
  ProductionRun domain contracts with UUID/business identifiers, semantic
  statuses, audit metadata, and quantity invariants.
- SQLAlchemy 2.x normalized models/repository and Alembic baseline migration
  shape for SQLite DEV/test.
- Stage 2 FastAPI Customer/PO/Line/Delivery/Run endpoints.
- Compact Vietnamese dark desktop Stage 2 navigation tabs.
- Generic order/production Excel export; exact legacy template remains pending.
- Focused Stage 2 tests and migration smoke.

## Evidence to record

```text
SQLALCHEMY_SQLITE_INTEGRATION_PASS
ALEMBIC_SQLITE_MIGRATION_SMOKE_PASS
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
```

Full Stage 1 regression, Stage 2 regression, final isolation and candidate
identity evidence are required before the candidate verdict is recorded.

## Known gaps / next action

QR issuance, mobile scan, routing/operations, QC, packing, full delivery
transactions, production authentication, NAS write pipeline, and Machine A
deployment remain future scope. Next exact action after independent review is
`STAGE3_ROUTING_OPERATIONS_QR_ISSUANCE_R005`.
