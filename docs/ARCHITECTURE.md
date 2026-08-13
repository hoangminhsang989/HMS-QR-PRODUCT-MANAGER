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
