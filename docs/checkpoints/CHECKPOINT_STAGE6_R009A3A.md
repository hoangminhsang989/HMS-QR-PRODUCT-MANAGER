# CHECKPOINT — Stage 6 R009A3A Archive Download Unavailable Contract

Date: 2026-08-15
Branch: `stage6-r009a3a-archive-download-unavailable-contract`
External artifact root: `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`

## Frozen baseline and reproduced defect

```text
R009A3A_BASE_HEAD=098e4a4a76462a3d148cc5a9653261e3f06a7f99
R009A3A_BASE_TREE=a8c5b0021cac7e98fde50d46e8e9275633e2c248
R009A3A_BASE_PARENT=76b39d81a31886625b17fbf7c87cc5ad723df7d3
ORIGIN_MAIN_HEAD=fadaeef44d6db082bc64f3e32456b24d6bd7e6b1
START_WORKTREE_CLEAN=YES
R009A3_VERDICT=REJECT_STAGE6_R009A3_ARCHIVE_ONLY_OFFLINE_DOWNLOAD_UNCONTROLLED_500
ROOT_CAUSE_CONFIRMED=YES
```

`StoreForwardService.read_available()` correctly reads the local tier first and
raises the distinct `StorageUnavailable` type when an archive-only file's
backend is unavailable. Files API had no handler for this exact operational
exception, so the framework returned a generic plain-text HTTP `500`.

## Bounded remediation

- Files API imports the existing `StorageUnavailable` type and registers one
  exact exception handler.
- The handler reuses the existing `_json_error` envelope and returns HTTP `503`
  with code `STORAGE_UNAVAILABLE`.
- The response message is fixed and client-safe; it does not use `str(exc)`.
- The sole managed-byte route, `GET /api/v1/files/{file_id}`, covers product
  images and attachments through the same service path.
- Lookup remains `404`; unexpected and integrity exceptions remain `500` and
  are not silently relabelled unavailable.
- No storage engine, worker, retry, grace, purge, capacity, destination, UI,
  authorization, QR, backup, Excel or migration production byte changed.

```text
STORAGE_UNAVAILABLE_HTTP_STATUS=503
STORAGE_UNAVAILABLE_ERROR_ENVELOPE=PASS
ARCHIVE_OFFLINE_FALSE_NOT_FOUND_COUNT=0
ARCHIVE_ONLY_OFFLINE_GENERIC_500_COUNT=0
FILES_READ_ROUTE_COUNT=1
STORAGE_UNAVAILABLE_MAPPED_READ_ROUTE_COUNT=1
GENERIC_EXCEPTION_RELABELED_STORAGE_UNAVAILABLE_COUNT=0
STORE_FORWARD_ENGINE_CHANGE_COUNT=0
UI_PRODUCTION_CHANGE_COUNT=0
```

## Black-box hard gate

The exact R009A3 scenario was repeated with actual Files API,
`raise_server_exceptions=False`, and fake local/archive tiers entirely beneath
the external test root.

```text
PRE_OFFLINE_STATE=LOCAL_GRACE_RETENTION
POST_PURGE_STATE=ARCHIVED_REMOTE_ONLY
ARCHIVE_ONLY_OFFLINE_STATUS=503
ARCHIVE_ONLY_OFFLINE_CONTENT_TYPE=application/json
ARCHIVE_ONLY_OFFLINE_ERROR_CODE=STORAGE_UNAVAILABLE
DOWNLOAD_UNAVAILABLE_STATE_MUTATED=FALSE
ARCHIVE_ONLY_OFFLINE_BOUNDED_RESPONSE=PASS
```

The structured response was exactly:

```json
{"error":{"code":"STORAGE_UNAVAILABLE","message":"Tệp hiện chưa thể truy cập do vị trí lưu trữ tạm thời không khả dụng."}}
```

## Contract and lifecycle evidence

```text
LOCAL_PRESENT_ARCHIVE_OFFLINE_DOWNLOAD=PASS
DOWNLOAD_UNAVAILABLE_STATE_MUTATION_COUNT=0
DOWNLOAD_UNAVAILABLE_TRANSFER_REQUEUE_COUNT=0
DOWNLOAD_UNAVAILABLE_TRANSFER_WORKER_CALL_COUNT=0
DOWNLOAD_UNAVAILABLE_PURGE_STATE_MUTATION_COUNT=0
PRODUCT_IMAGE_ARCHIVE_OFFLINE_ERROR_CONTRACT=PASS
ATTACHMENT_ARCHIVE_OFFLINE_ERROR_CONTRACT=PASS
ARCHIVE_OFFLINE_RESPONSE_RAW_PATH_LEAK_COUNT=0
ARCHIVE_OFFLINE_RESPONSE_CREDENTIAL_LEAK_COUNT=0
ARCHIVE_OFFLINE_RESPONSE_TRACEBACK_LEAK_COUNT=0
RAW_LOCAL_PATH_IN_API_RESPONSE_COUNT=0
RAW_ARCHIVE_PATH_IN_API_RESPONSE_COUNT=0
PROD_ADMIN_AUTH_FAIL_CLOSED=PASS
DEV_HEADER_PRODUCTION_AUTH_ACCEPT_COUNT=0
DEV_HEADER_STAGING_AUTH_ACCEPT_COUNT=0
DENIED_ADMIN_HANDLER_EXECUTION_COUNT=0
REMOTE_VERIFIED_TRANSFER_LIFECYCLE_MONOTONIC=PASS
LOCAL_GRACE_TRANSFER_RETRY_REQUEUE_COUNT=0
LOCAL_PURGE_PENDING_TRANSFER_RETRY_REQUEUE_COUNT=0
GRACE_EXPIRY_MUTATION_AFTER_INELIGIBLE_RETRY_COUNT=0
```

## Test evidence

```text
R009A3A_DOWNLOAD_UNAVAILABLE_FOCUSED_TESTS=7 passed, 1 inherited warning in 21.29s
R009_AUTH_FOCUSED_TESTS=10 passed, 1 inherited warning in 0.82s
R009_RETRY_FOCUSED_TESTS=13 passed, 1 inherited warning in 41.27s
R009_FOCUSED_TESTS=22 passed, 1 inherited warning in 78.06s
R009_RUNTIME_HARDENING_TESTS=23 passed, 1 inherited warning in 94.24s
QR_CRITICAL_TESTS=6 passed, 1 inherited warning in 26.81s
FULL_REGRESSION=105 passed, 1 inherited warning in 385.32s
FULL_PYTEST_TERMINAL_VERDICT_OBTAINED=YES
FAILED_TEST_COUNT=0
NEW_R009_WARNING_COUNT=0
```

The full run used one pytest process with all 29 files explicitly listed and
the six Qt-instantiating files last. The sole warning remains the inherited
Starlette/httpx deprecation.

## Static, scope and safety evidence

```text
QR_EXACT_FIELD_COUNT=4
QR_EXACT_FOUR_FIELD_CONTRACT=PASS
ALEMBIC_HEAD=0005_store_forward
TEST_ISOLATION_PASS=PASS
PRODUCTION_ROOT_TEST_ARTIFACT_COUNT=0
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
GIT_DIFF_CHECK=PASS
UNRELATED_CHANGE_COUNT=0
UNRELATED_PRODUCTION_CHANGE_COUNT=0
STORE_FORWARD_ENGINE_CHANGE_COUNT=0
UI_PRODUCTION_CHANGE_COUNT=0
PRODUCTION_GAP_RELABEL_COUNT=0
REAL_NAS_WRITE_COUNT=0
PRODUCTION_RESTORE_COUNT=0
EXACT_EXCEL_FIDELITY_CLAIM_COUNT=0
```

## Production gaps preserved

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

Candidate commit HEAD/tree/parent and final clean-worktree identity are recorded
after commit in the handoff report because a commit cannot contain its own hash.
No merge or push is authorized. The next authority is
`STAGE6_R009A4_FINAL_INDEPENDENT_REVIEW_OF_REMEDIATED_R009_CANDIDATE`.
