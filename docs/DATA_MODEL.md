# Data Model Foundation

Business identifiers are explicit (`product_code`, `production_run_code`,
`qr_public_id`) and are distinct from internal UUIDs.

Audit records use immutable events with server UTC timestamps and optional client
timestamps/device identifiers. Corrections create revisions/events instead of
destructive updates.
