# CHECKPOINT

Date: 2026-08-13
Stage: Stage 4 — QC + NG Return + Packing + Delivery Status
Revision: R006
Verdict: PASS_STAGE4_QC_PACKING_DELIVERY_R006

## Baseline and candidate

- Accepted main HEAD/tree: `fd2148a4c89ecde4c399addc41858c63106c452d` /
  `ef85816744cfc56e002802c851d2266a489f3cd0`
- Candidate branch: `stage4-qc-packing-delivery`
- Implementation HEAD/tree: `1ccb5838ca21c2cf1d33507e440bf0b33e1e8086` /
  `2b061e5bf8e57d0cf2913ec49d2ee2fd44e876f5`
- Final candidate tip after checkpoint metadata: recorded by the final commit.
- Main remains unchanged; R006 is candidate-only and requires a separate
  independent review/integration authority.

## Delivered workflow

- Typed append-only events: `QC_CHECKED`, `SHORTAGE_REPORTED`,
  `QC_NG_RETURNED_TO_MACHINING`, `PACKED`, `DELIVERED`, and `GENERAL_REPORT`.
- Tracking Item remains the QR/workflow anchor. These events are not Routing
  steps. Existing four-field QR payload stays unchanged.
- Multiple QC/NG/rework cycles are retained. Existing machining attempts and
  `ĐÃ XONG` continue after NG; a later QC event starts another QC cycle.
- Server-side current status projection supports `IN_PROCESS`, `WAITING_QC`,
  `QC_CHECKED`, `QC_NG`, `REWORK`, `SHORTAGE`, `PACKING`, `PACKED`,
  `PARTIALLY_DELIVERED`, and `DELIVERED` without deleting history.
- General reports retain free text without changing workflow status.
- Desktop overview/actions/history and mobile `GIA CÔNG` / `QC / GIAO HÀNG`
  modes use the same services and API business rules.

## Quantity and transaction policy

- Tracking Item quantity is target/order-occurrence quantity only.
- Checked, shortage, NG, packed, and delivered quantities remain separate event
  semantics. Partial and repeated packing/delivery are supported.
- `quantity > 0` for quantity-bearing events.
- Effective `packed <= target - shortage`.
- Effective `delivered <= packed`; delivery before sufficient packing is
  rejected.
- Planned delivery date is not actual delivery time. `DELIVERED` uses server
  UTC timestamp authority; mobile renders `Asia/Ho_Chi_Minh`.
- Event create/revision, effective aggregate validation, and status projection
  commit atomically. Injected-failure tests prove rollback.

## Audit, revision, and idempotency

- Every event includes UUID, request UUID, Tracking Item, semantic type,
  quantity/content, operator UUID and display snapshot, server UTC time,
  optional client/device and machining/report references, sequence, revision,
  superseded-event link, and active/superseded state.
- Same request UUID retries return the existing event. Reuse with a different
  identity fails closed.
- Corrections create a new revision; the old revision remains in history.
  Invalid corrections roll back both revision state and projection.
- Combined history presents machining/process reports alongside QC, shortage,
  NG, packing, delivery, and general reports.

## API and persistence

- Versioned QC, packing, delivery, general report, summary, combined history,
  status filtering, and workflow revision endpoints are exposed under the
  existing tracking API.
- SQLAlchemy uses the typed `tracking_workflow_events` table rather than an
  unstructured business JSON blob.
- Alembic `0003_qc_packing_delivery` passes fresh database and Stage 3 upgrade
  path tests with existing data preserved.

## Fresh evidence

```text
Stage 4 focused final: 12 passed, 1 external warning
Full Stage 0-4 regression: 35 passed, 1 external warning
ALEMBIC_SQLITE_MIGRATION_SMOKE_PASS
TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION
git diff --check: PASS
DIFF_REVIEW_FILE_COUNT=21 implementation paths plus this checkpoint
UNRELATED_CHANGE_COUNT=0
Authority source/saved SHA256=852026671BDF386A4693EBBD05717E79C194FEB613674B77F255DC59B5F3F221
Mobile browser: real local QR scan and QC create/history refresh; user picker;
all six actions; status QC_CHECKED; Asia/Ho_Chi_Minh display; viewport 390x844;
scrollWidth == clientWidth; clean tab had no console warning/error.
```

The sole warning remains
`STARLETTE_HTTPX_DEPRECATION_EXTERNAL_NON_BLOCKING`. It is unchanged external
library behavior; no new own-code warning is accepted.

## Truthful known gaps

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

No production PostgreSQL, NAS write, Machine A deployment, production hosting,
real-device camera acceptance, final template fidelity, or Routing engine is
claimed.

## Next exact action

Obtain a fresh independent Stage 4 candidate review and separate integration
authority. Do not merge `main` under R006.
