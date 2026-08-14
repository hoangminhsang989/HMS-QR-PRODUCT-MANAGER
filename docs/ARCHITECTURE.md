# Architecture

The system is split into three clients/services:

- Server on Machine A: API, identity, live database, audit, and synchronization.
- Desktop client: production management, CAM preparation, QR operations, QC, and history.
- Mobile web/PWA: identity, QR scan, server-backed reporting, and status updates.

PostgreSQL is the live database on Machine A. NAS is a LAN-only object/file/archive
store reached by the server; clients never mount or access NAS directly.

## Stage 1 Product Master slice

The first vertical slice is layered as Domain → Repository → Application
Service → versioned FastAPI → PySide6 desktop presentation. The SQLite adapter
is restricted to the DEV/test profile and uses the external test workspace;
PostgreSQL remains the production target. Product attachments use a
`StorageReference` behind a server-owned `StorageService`, so clients never
receive a NAS path. Excel import/export is isolated in `packages/excel` and is
usable by the desktop layer without placing workbook logic in UI widgets.

## Stage 2 Customer + PO + Production Run

R004 adds normalized SQLAlchemy 2.x persistence for Customer, PurchaseOrder,
PurchaseOrderLine, DeliveryScheduleEntry, and ProductionRun. Product remains
the master reference; PO Line owns ordered quantity and Production Run owns
planned/completed manufacturing quantities. SQLite is DEV/test only, Alembic
provides the baseline migration shape, and PostgreSQL on Machine A remains the
production target.

## Stage 3 tracking, QR, and process reporting

R005 deliberately does not introduce a routing engine. It adds an
OrderTrackingItem between PO Line and QR, an opaque/versioned QR resolver,
server-owned operator preferences, a configurable MachiningType catalog,
per-tracking-item/per-machining-type attempt display state, and immutable
process report events/revisions. The mobile-first web client resolves live data
from the server; camera scanning requires a secure browser context and manual
paste remains a DEV fallback.

## Stage 4 QC, packing, and delivery tracking

R006 extends Tracking Item with typed append-only workflow events and a derived
status projection; it does not add a Routing engine. `QcService`,
`PackingService`, `DeliveryService`, `GeneralReportService`, and
`TrackingHistoryService` share one transactional repository policy. Each write
uses a request UUID for idempotency, server UTC time, operator UUID plus display
snapshot, optional client/device metadata, and non-destructive revision links.
Event creation/revision, quantity validation, and Tracking Item projection are
committed atomically. Mobile displays timestamps in `Asia/Ho_Chi_Minh`.

## Stage 6 R009 safe store-and-forward managed files

Product images and attachments are saved to `LOCAL_INGEST_ROOT` on Machine A
before upload success is returned. The database transaction that makes the
managed file `READY` also creates a persistent archive-transfer job. Archive
availability is a separate lifecycle, so `READY` continues to mean that the
file is safely available and never ambiguously means “already archived”.

The canonical destructive order is:

```text
SAVE LOCAL FIRST -> QUEUE -> COPY TO REMOTE TEMP -> VERIFY SIZE + SHA-256
-> REMOTE FINAL COMMIT -> METADATA COMMIT -> LOCAL GRACE RETENTION
-> REVALIDATE -> DELETE LOCAL LAST
```

Each transfer job snapshots a versioned storage configuration identity. A new
archive destination affects new uploads only; queued/in-flight jobs retain
their original destination, and already archived objects are not migrated by
R009. Downloads resolve logical file identity through the service: a verified
local copy is preferred, otherwise a verified archive copy is served. Neither
desktop nor mobile receives a local path, UNC path, credential, or storage key.

Workers claim jobs through a database lease, use bounded backoff, restart an
exact job-owned partial remote temp safely, and publish the final object by a
same-filesystem replace. A mismatched final object is never overwritten. Purge
requires a committed remote verification, expired grace period, no active
lease, and immediate checksum revalidation. Ambiguous bytes are retained.

Archive storage remains distinct from backup. A successful archive transfer
does not imply `BACKED_UP=YES`.
