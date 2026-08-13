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
