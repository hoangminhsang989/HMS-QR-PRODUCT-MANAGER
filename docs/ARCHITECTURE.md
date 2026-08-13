# Architecture

The system is split into three clients/services:

- Server on Machine A: API, identity, live database, audit, and synchronization.
- Desktop client: production management, CAM preparation, QR operations, QC, and history.
- Mobile web/PWA: identity, QR scan, server-backed reporting, and status updates.

PostgreSQL is the live database on Machine A. NAS is a LAN-only object/file/archive
store reached by the server; clients never mount or access NAS directly.
