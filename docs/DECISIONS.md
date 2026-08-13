# Architectural Decisions

## ADR-001 — Live database on Machine A

Status: Accepted
Date: 2026-08-13

Decision: Keep the live PostgreSQL database on Machine A. Use NAS only for files,
exports, archives, and backups through the server.

Reason: Preserve one database authority and prevent direct client/NAS coupling.

Consequences: The server owns persistence and access policy; external exposure
requires a later security review.

## ADR-002 — Opaque QR references

Status: Accepted
Date: 2026-08-13

Decision: QR payloads contain an opaque, versioned reference such as `HMSQR:v1:<id>`.

Reason: Product data can change without invalidating printed QR labels.

## ADR-003 — External test artifacts

Status: Accepted
Date: 2026-08-13

Decision: Test, runtime, build, and generated artifacts are written only under the
dedicated test workspace.

## ADR-007 — R004 normalized persistence

Status: Accepted for R004

Decision: Normalize Customer, PO, PO Line, Delivery Schedule, and Production
Run using SQLAlchemy 2.x models with explicit foreign keys. Product remains the
master/reference entity and order/manufacturing quantities remain separate.

## ADR-008 — Production Run as QR extension anchor

Status: Accepted for R004

Decision: Production Run is the future QR/routing anchor. R004 does not
implement routing, operations, QR issuance, mobile scanning, QC, or packing.

## ADR-009 — Delivery schedule child entries

Status: Accepted for R004

Decision: Represent vendor delivery schedule as repeated DeliveryScheduleEntry
rows with date, quantity, status, and notes rather than one flattened text field.

## ADR-010 — Separate Product, Order, Tracking, and QR identities

Status: Accepted for R005

Decision: Product master code, customer PO/internal order code, Tracking Item
code, and opaque QR public ID are separate identities. Changing delivery date
preserves Tracking/QR identity; creating a new order creates new Tracking/QR
identities.

## ADR-011 — No routing engine required for mobile reporting

Status: Accepted for R005

Decision: Mobile reporting selects a configurable machining type, shows dynamic
attempt buttons, and writes process report events. Attempt expansion is keyed
by Tracking Item + machining type. Reports use idempotent append/revision
semantics; completion is a separate event, not a final routing step.
