# CHECKPOINT — Stage 6 R009 Safe Store-and-Forward Candidate

Date: 2026-08-14
Repository: `F:\PHAN-MEM-QUAN-LY-QR`
External artifact root: `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`
Branch: `stage6-r009-store-forward-api-ui`

## Authority and frozen baseline

```text
BASE_BRANCH=main
BASE_HEAD=fadaeef44d6db082bc64f3e32456b24d6bd7e6b1
BASE_TREE=464c4bf1d2f6176e22030abefa6ac5000c63e4ad
ORIGIN_MAIN_HEAD=fadaeef44d6db082bc64f3e32456b24d6bd7e6b1
LOCAL_AHEAD=0
LOCAL_BEHIND=0
BASE_WORKTREE_CLEAN=YES
R008_VERDICT=PASS_STAGE6_R008C_REMOTE_DELIVERY
```

## Canonical architecture

```text
CLIENT
-> MACHINE A SERVER
-> LOCAL_INGEST_ROOT (durable + verified)
-> MANAGED FILE READY + PERSISTENT QUEUE (one DB transaction)
-> REMOTE SAME-FILESYSTEM .transfer-<job>.tmp
-> COPY + SIZE VERIFY + SHA-256 VERIFY
-> REMOTE FINAL COMMIT
-> REMOTE METADATA COMMIT
-> LOCAL GRACE RETENTION
-> PURGE REVALIDATION
-> DELETE LOCAL LAST
```

Upload success is based on local durability. Archive offline state is reported
as queued/retryable and does not relabel the upload failed. Archive transfer is
not backup, and `READY` does not mean remote archive ready.

## Persistence and configuration safety

- Alembic head: `0005_store_forward`.
- `storage_configurations` preserves versioned local/archive roots, grace,
  backoff, and capacity thresholds.
- Each `archive_transfer_jobs` row snapshots its configuration identity.
- New configuration affects new uploads. Queued/in-flight jobs keep their old
  destination. Already archived data is not migrated in R009.
- Database lease ownership prevents two workers from transferring one job.
- Retry defaults are 1, 5, 15, 30, and 60 minutes, then bounded recurring 60
  minutes. Manual retry only requeues; it does not duplicate an active lease.

## Crash/restart recovery matrix

| Point | Reconciliation after restart | Data-safety result |
|---|---|---|
| A. Local write in progress | Keep ambiguous temp; publish only an exact temp whose size and SHA-256 match metadata | No unverified bytes become READY |
| B. Local complete before queue | Verify local final, atomically recover READY + persistent job | Local valid copy retained |
| C. Queue before remote copy | Due job remains in DB and is claimable | Local retained |
| D. Partial remote temp | Exact job temp is safely restarted | Local retained |
| E. Remote copy before verify | Next attempt verifies existing final | No duplicate publication |
| F. Verify before DB commit | Existing valid final is detected and remote state is committed | Local and remote valid |
| G. Remote state before grace | Remote commit and grace timestamp share one DB update | Local retained through grace |
| H. Grace expired before delete | Reconciler advances to purge pending | Local retained until purge worker |
| I. Local delete fails | Remain `LOCAL_PURGE_PENDING`; do not retransmit | Remote valid, local retained/retried |

Unknown or mismatched bytes are never deleted automatically.

## API and UI boundary

- Product image: upload, list, download/view, set primary, relation update,
  archive, and version replacement foundation.
- Attachment: upload, list, download/view, archive, and replacement foundation.
- Responses contain logical ID, metadata, availability and archive state; no
  storage key, local root, UNC path, or credential.
- Desktop provides compact image and attachment tables plus Storage Admin root
  pickers, health, retry, and validation actions.
- Mobile provides server-mediated image/attachment metadata and links; upload is
  intentionally not broadened in R009.

## Focused and visual evidence

```text
R009_FOCUSED_TESTS=22 passed, 1 inherited warning in 83.15s
R008_STAGE6_LEGACY_TESTS=13 passed in 50.85s
FAILED_TEST_COUNT=0
DESKTOP_NATIVE_VIEWPORT=1280x720
MOBILE_VIEWPORT=390x844
MOBILE_INNER_WIDTH=390
MOBILE_SCROLL_WIDTH=390
MOBILE_MIN_INTERACTIVE_HEIGHT_PX=44
DESKTOP_LIGHT_INDUSTRIAL=PASS
DESKTOP_IMAGE_ATTACHMENT_COMPACTNESS=PASS
ADMIN_STORAGE_SECTION_BOUNDED=PASS
MOBILE_NO_HORIZONTAL_OVERFLOW=PASS
```

External visual artifacts:

```text
F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\r009-visual\desktop-files-1280x720.png
F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\r009-visual\desktop-admin-1280x720.png
F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\r009-visual\mobile-390x844.png
```

```text
DESKTOP_FILES_PNG_SHA256=77b9c2c1ca8b5ae8533d6c799a3a400b921191f073084731fa9d3b5377ce0c24
DESKTOP_ADMIN_PNG_SHA256=e5156c11a035e8f69766ff6e21c4a59dfa67b51d35d7b1e2723c20900512c0a8
MOBILE_390_PNG_SHA256=0ddfc0491b53fb339ecb595395d325d9b8e9af31dfa551cbff226cf76489b358
```

## Terminal candidate gates

```text
VERDICT=PASS_STAGE6_R009_SAFE_STORE_FORWARD_IMAGE_ATTACHMENT_API_UI_CANDIDATE
LOCAL_FIRST_UPLOAD=PASS
PERSISTENT_TRANSFER_QUEUE=PASS
ARCHIVE_OFFLINE_ACCEPTANCE=PASS
REMOTE_TRANSFER_INTEGRITY=PASS
LOCAL_DELETE_LAST=PASS
GRACE_PERIOD=PASS
CAPACITY_PROTECTION=PASS
CRASH_RECOVERY_FOUNDATION=PASS
PRODUCT_IMAGE_API=PASS
ATTACHMENT_API=PASS
DESKTOP_IMAGE_ATTACHMENT_UI=PASS
ADMIN_STORAGE_UI=PASS
MOBILE_FILE_ACCESS_FOUNDATION=PASS
ALEMBIC_HEAD=0005_store_forward
ALEMBIC_REVISION_BOUNDARY=PASS
FOCUSED_TESTS=22 passed, 1 inherited warning in 83.15s
RUNTIME_HARDENING_TESTS=23 passed, 1 inherited warning in 104.92s
FULL_REGRESSION=75 passed, 1 inherited warning in 353.56s
FAILED_TEST_COUNT=0
QR_CRITICAL_TESTS=5 passed, 1 deselected, 1 inherited warning in 19.77s
QR_EXACT_FOUR_FIELD_CONTRACT=PASS
TEST_ISOLATION_PASS=PASS
PRODUCTION_ROOT_TEST_ARTIFACT_COUNT=0
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
GIT_DIFF_CHECK=PASS
PRODUCTION_GAP_RELABEL_COUNT=0
REAL_NAS_WRITE_COUNT=0
PRODUCTION_RESTORE_COUNT=0
EXACT_EXCEL_FIDELITY_CLAIM_COUNT=0
```

Candidate commit HEAD/TREE and final clean worktree identity are recorded in the
handoff report after the commit, because a commit cannot truthfully contain its
own identity.

## Production gaps preserved

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

```text
REAL_NAS_WRITE_COUNT=0
PRODUCTION_RESTORE_COUNT=0
EXACT_EXCEL_FIDELITY_CLAIM_COUNT=0
PRODUCTION_GAP_RELABEL_COUNT=0
```

Stop after candidate commit. Do not integrate or push. Next authority is
`STAGE6_R009A_INDEPENDENT_SAFE_STORE_FORWARD_REVIEW`.
