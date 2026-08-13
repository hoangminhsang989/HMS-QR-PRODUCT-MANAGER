# Architectural Decisions

## ADR-001 — Live database on Machine A

Status: Accepted
Date: 2026-08-13

Decision: Keep the live PostgreSQL database on Machine A. Use NAS only for files,
exports, archives, and backups through the server.

Reason: Preserve one database authority and prevent direct client/NAS coupling.

Consequences: The server owns persistence and access policy; external exposure
requires a later security review.

## ADR-002 — QR references (superseded)

Status: Superseded by ADR-012 in Stage 3 R005A
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

## ADR-012 — Four-field business QR payload and live tracking lookup

Status: Accepted for R005A

Decision: Encode exactly Product name, Customer name, Product code, and
Tracking code as deterministic compact JSON. Resolve scans by Tracking code;
load mutable values from the server. Keep `qr_public_id` internal for issuance
and audit only. Printed-label fields and formatting are a separate service.

Reason: This is the current user requirement and preserves QR payload/pattern
when mutable delivery or label data changes.

## ADR-013 — QC, packing, and delivery are tracking events

Status: Accepted for R006

Decision: Model QC checked, shortage, NG return, packing, actual delivery, and
general reports as append-only, revision-aware events anchored to Tracking
Item. They are not Routing steps. Tracking Item `status` is a transactionally
updated projection for search/display; effective event history remains the
source of truth.

Quantity semantics remain separate: Tracking Item quantity is the target order
occurrence; event quantities represent checked, shortage, NG, packed, or
delivered amounts. R006 permits partial/multiple packing and delivery events,
limits aggregate packing to target minus effective shortage, and requires
aggregate delivered quantity not to exceed aggregate packed quantity.
