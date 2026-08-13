# Data Model Foundation

Business identifiers are explicit (`product_code`, `production_run_code`,
`qr_public_id`) and are distinct from internal UUIDs.

Audit records use immutable events with server UTC timestamps and optional client
timestamps/device identifiers. Corrections create revisions/events instead of
destructive updates.

## Product Master R002

Product identity is a UUID (`internal_id`) plus a unique business
`product_code`; code generation is centralized in `ProductCodeService` and can
later change prefix/sequence/year policy without changing the Product model.
The Product Master stores company, part name, ordered/product quantity, unit,
material, requester, surface treatment, outsourced flag, size, notes, delivery
schedule, semantic `ProductStatus`, and server-UTC created/updated timestamps
with actor metadata. `quantity` means ordered/product quantity only; processed,
QC, packed, and delivered quantities belong to future entities. Product images
and attachments are metadata references, not binary columns.

## Stage 2 order and manufacturing entities

Customer has a UUID identity and unique `customer_code`. PurchaseOrder
references Customer and owns PO-level dates/status. PurchaseOrderLine references
Product and owns `ordered_quantity`; it does not reuse Product.quantity.
DeliveryScheduleEntry is a repeated dated child of PO Line. ProductionRun
references PO Line/Product and owns planned/completed quantities with
`0 <= completed_quantity <= planned_quantity`; aggregate planned quantities are
blocked from exceeding ordered quantity. Future QC/delivery quantities remain
separate concepts.

## Stage 3 tracking identities

Product code identifies Product Master; customer PO number identifies the
customer order document; optional `internal_order_code` identifies an internal
order occurrence; `tracking_code` identifies one ordered/tracked item; and
`qr_public_id` is internal issuance/audit metadata; the canonical four-field QR
uses `tracking_code` as its live lookup identity. Delivery-date changes preserve
tracking/QR identity. Creating a new order occurrence creates a new order,
tracking code, and QR payload while reusing the Product master reference.
Attempt display state is keyed by `(tracking_item_id, machining_type_id)`, not
by user or Product. Process reports are append-only events with idempotency UUID,
actor snapshot, optional attempt number, completion kind, and revision chain.

## Stage 4 workflow events and quantity semantics

`TrackingWorkflowEvent` stores a typed event UUID, idempotency request UUID,
Tracking Item reference, event type, typed quantity, notes, optional related
machining type/process report, operator UUID/display snapshot, server UTC time,
optional client/device metadata, stable sequence, revision, superseded-event
link, and active/superseded state. No workflow event is stored as an untyped
JSON business blob.

Tracking Item quantity remains the target order occurrence. Checked, shortage,
NG, packed, and delivered quantities are independent event semantics. Effective
revision aggregates enforce `packed <= target - shortage` and
`delivered <= packed`. Multiple QC, partial packing, and partial delivery events
are retained. Tracking Item status is a derived projection, not a replacement
for history. Planned delivery date remains distinct from actual `DELIVERED`
event server time.

Independent shortage events are additive. Each event contributes only its
current active revision; superseded revisions never contribute to checked,
shortage, NG, packed, or delivered aggregates.
