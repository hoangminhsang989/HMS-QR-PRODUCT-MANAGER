# CHECKPOINT

Date: 2026-08-13
Stage: Stage 3 — Order Tracking Item + QR + Mobile Process Reporting
Revision: R005A
Verdict: PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005A_INTEGRATED

## Rejected R005 candidate and remediation

- Rejected candidate HEAD/tree: `21b36128431cd202e202d0644363719547e14efc` /
  `63f4944da2a1549e5a51f425ba446b7294d71e8e`
- Review verdict: `REJECT_STAGE3_R005_REQUIREMENT_DRIFT_QR_PAYLOAD_AND_PROCESS_CATALOG`
- Cause: opaque-only QR payload/lookup and missing `TẠO PHÔI` baseline catalog entry.
- Remediated candidate HEAD/tree: `9f64425f82f199e64323e9d73dba3b0c3f53b8d3` /
  `6ab1eb630d91647a91bdb42f3b8a454670669f04`
- R005A changed path count: `17`
- R005A unrelated change count: `0`
- Fresh review verdict: `APPROVE_STAGE3_R005A_INTEGRATION`

## Delivered contract

- Canonical compact UTF-8 JSON QR with exactly `product_name`,
  `customer_name`, `product_code`, and `tracking_code`, in fixed order.
- Scan decode and authoritative lookup by `tracking_code`; current mutable data
  comes live from the server. Embedded identity context is diagnostic only.
- Delivery-date changes preserve tracking code, exact payload bytes, and QR PNG
  pattern; the same scan resolves the current server delivery date.
- New-order transaction creates a new order, Tracking Item/code, and QR payload
  while allowing the same Product master reference.
- `qr_public_id` remains internal issuance/reissue/audit metadata and is neither
  encoded nor used for scan lookup.
- Configurable machining catalog now includes `TẠO PHÔI`, `TIỆN`, `PHAY`, and
  `CẮT DÂY`. Preference remains server-side per user; attempt expansion remains
  keyed by Tracking Item plus machining type.
- Separate `QrPayloadService`, `LabelDataService`, `LabelTemplateRenderer`, and
  `LabelPrintExportService` foundation. Reprinted visible label data can change
  while its embedded QR remains unchanged.
- Generated QR/label output is path-guarded to
  `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`.

## Fresh candidate and post-integration evidence

```text
Candidate focused Stage 3: 7 passed, 1 external warning
Candidate full Stage 0-3 regression: 23 passed, 1 external warning
Post-integration critical Stage 3: 7 passed, 1 external warning
Post-integration full Stage 0-3 regression: 23 passed, 1 external warning
ALEMBIC_SQLITE_MIGRATION_SMOKE_PASS
TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION
git diff --check: PASS
Authority source/saved SHA256: A31193C29D60524B657A324975713FAA5E98C878339A3C4F003983214625E1B0
Mobile browser: live scan at mobile viewport, no horizontal overflow, no console errors;
required user/process, product/customer/code/tracking/date/quantity/status,
LẦN 1-3, + THÊM LẦN, and ĐÃ XONG controls verified.
```

The unchanged warning is
`STARLETTE_HTTPX_DEPRECATION_EXTERNAL_NON_BLOCKING`; no new own-code warning was accepted.
The mobile gate does not claim a real iPhone/Android camera PASS.

## Integration

- Accepted main baseline HEAD/tree: `2aed6e945543d2d190bf932a30330032608f95e2` /
  `f956fc07e4f5503b7624c808ff18b22e305255ae`
- Method: clean `git merge --ff-only stage3-tracking-qr-process-reporting`
- Integrated implementation HEAD/tree before this checkpoint metadata commit:
  `9f64425f82f199e64323e9d73dba3b0c3f53b8d3` /
  `6ab1eb630d91647a91bdb42f3b8a454670669f04`
- No squash, rebase, force operation, or remote push.
- Final main HEAD/tree are the commit containing this checkpoint and its tree.

## Truthful known gaps

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
QC_WORKFLOW_NOT_YET_IMPLEMENTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

## Next action

Start a separately authorized business stage for QC + NG return + packing +
delivery status. No Routing engine or those workflows were added in R005A.
