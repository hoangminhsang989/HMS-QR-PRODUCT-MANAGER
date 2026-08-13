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
