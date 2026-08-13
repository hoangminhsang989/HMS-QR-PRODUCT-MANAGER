# Stage 3 R005A — QR and label contract

## Canonical QR payload

The QR encodes UTF-8 JSON with no prefix, envelope, version field, UUID, or
resolver token. Serialization uses compact separators, preserves Unicode, and
uses this exact field order:

```json
{"product_name":"...","customer_name":"...","product_code":"...","tracking_code":"..."}
```

Those are the only four encoded fields. `tracking_code` is the authoritative
server lookup key. The other three embedded values are immutable identity
context used for offline identification and a non-authoritative consistency
diagnostic. Mutable data such as delivery date, quantity, status, process
reports, material, size, surface treatment, and PO/order information is always
loaded live from the server.

Changing a delivery date therefore leaves the canonical payload bytes and QR
pattern unchanged. Creating a new order creates a new Tracking Item and
`tracking_code`, so its QR payload is different even when it references the
same Product master.

## Internal QR issuance identity

`qr_public_id` remains internal metadata for QR issue/reissue audit history and
active/revoked lifecycle state. It is never encoded and never used as the scan
lookup identity. Reissuing changes `qr_public_id` but preserves the canonical
payload because the Tracking Item identity is unchanged.

## Printed label separation

`QrPayloadService` owns only the four-field canonical payload.
`LabelDataService` loads current visible label values. `LabelTemplateRenderer`
selects and formats visible fields independently, and `LabelExportService`
writes the rendered label. The standard template may visibly show product,
customer, codes, material, quantity/unit, size, surface treatment, delivery
date, order/PO, and notes while embedding the unchanged canonical QR payload.

Generated QR and label assets are rejected unless their resolved path is under
`F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`.
