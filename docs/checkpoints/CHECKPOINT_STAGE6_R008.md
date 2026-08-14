# Checkpoint - Stage 6 R008

## Verdict

`PASS_STAGE6_R008_STORAGE_BACKUP_EXCEL_FOUNDATION_CANDIDATE`

This is a bounded candidate foundation. It is not a production NAS pass, a
PostgreSQL production integration, an exact workbook-fidelity certification,
or a Machine A deployment.

## Baseline and branch

```text
CURRENT_BRANCH_PRECHECK=main
CURRENT_HEAD_PRECHECK=ee9c1f13cb20dce64996536d807d177363362a9b
CURRENT_TREE_PRECHECK=dae464eaad32c52b0c03d51f2c8c49ae9feb45b7
ORIGIN_MAIN_HEAD_PRECHECK=ee9c1f13cb20dce64996536d807d177363362a9b
LOCAL_AHEAD=0
LOCAL_BEHIND=0
WORKTREE_PRECHECK=CLEAN
STAGE6_BRANCH=stage6-storage-images-backup-excel
STAGE6_BASE_HEAD=ee9c1f13cb20dce64996536d807d177363362a9b
STAGE6_BASE_TREE=dae464eaad32c52b0c03d51f2c8c49ae9feb45b7
```

No source mutation occurred before the exact Stage5 preflight passed. The R008
candidate was developed only on the Stage6 branch. `main` was not modified or
checked out for implementation, and no push was performed.

## Storage architecture and NAS boundary

Clients continue to reach server APIs only. They never receive a physical NAS
root, credential, server path, or arbitrary path-based download operation. The
future topology remains Desktop/PWA/cloud frontend -> Machine A server -> NAS;
PostgreSQL remains the future authoritative transactional database on Machine A
and is not placed on NAS.

`StorageService` now defines publication, read, existence, archive, delete,
integrity verification, and health operations. `LocalDevStorage` implements the
development/test filesystem backend. `NasFilesystemStorage` is a server-only,
externally configured UNC adapter boundary that does not create its root and
does not silently fall back to local storage. No real UNC root or credential is
committed.

Every storage key is logical and server-generated from product UUID, file UUID,
category, version, and generated filename. User filenames remain metadata only.
The boundary rejects traversal, dot segments, absolute paths, drive letters,
UNC injection, reserved Windows names, illegal filename characters, and unsafe
key segments.

Publication is staged in the final directory, flushed and fsynced where the OS
supports it, checked for exact size and SHA-256, then atomically replaced into
the immutable final key. A conflicting existing key is rejected unless its
bytes are exactly identical. NAS availability is reported as a controlled
storage error; R008 performs no random production-local fallback.

## Managed-file model and compensation state

Migration `0004_managed_files` adds `managed_files` and
`product_file_relations`. Managed metadata includes immutable internal ID,
original and generated filenames, logical storage key, category, MIME,
extension, size, SHA-256, status, source, version, creator/timestamps,
replacement link, archive metadata, and bounded failure reason.

Publication uses `PENDING -> READY` only after durable storage verification.
Storage failure latches `FAILED`; a failed DB finalize leaves traceable metadata
for reconciliation instead of claiming success. Replacement finalization and
archival of the previous version occur in one metadata transaction. Archive is
non-destructive by default, so prior bytes and audit history remain available.

Multiple product images support primary selection, order, caption, archive,
replacement, and version history. Generic attachments use safe extensible
category codes for drawing, PDF, customer, inspection, purchase/order, and
other technical documents. Equal SHA-256 values remain distinct logical
relations and are not silently deduplicated.

Central upload policy enforces per-kind size limits and an extension/MIME
allowlist. Strong signatures are checked for JPEG, PNG, GIF, WebP, PDF, and DWG;
ZIP-family signatures are handled as a bounded shared container case. Uploaded
content is stored as inert bytes and is never executed.

## Backup and restore foundation

`BackupService` copies only `READY` managed files into a staging bundle,
revalidates their size and SHA-256, optionally includes a metadata snapshot
reference, writes a versioned JSON manifest plus a manifest SHA-256 sidecar,
verifies the complete staged bundle, and only then atomically publishes the
final directory.

The manifest records backup ID, UTC timestamp, application version, schema
revision, metadata-export reference/checksum, logical storage keys, bundle
relative paths, sizes, file checksums, and status. It contains no secret or NAS
credential. `RestoreVerifier` is non-destructive and detects missing manifest,
invalid/tampered manifest, unsafe relative paths, duplicate keys, missing
files, modified files, and modified metadata exports. Retention configuration
can identify candidates after `latest_n`; R008 does not hard-delete bundles.
The sidecar provides bounded accidental/corruption evidence; it is not a signed
or authenticated production-backup format, which remains later hardening.

This foundation verifies the current development/test state only. It does not
claim a production PostgreSQL backup or destructive restore pass.

## Excel template preparation

Generic import remains separate from template-preserving export. The new
adapter copies an XLSX/XLSM reference into the configured external artifact
root, applies bounded sheet/cell updates and optional product-image placement,
then saves the output. It never opens the canonical source for writing, rejects
in-place output, hashes the source before and after, preserves formulas and
existing workbook structures handled by openpyxl, and exposes anchor, image
dimensions, and row-height mapping.

The canonical business workbook was not supplied in this revision. Therefore:

```text
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
```

No claim is made yet for exact preservation of its embedded images, hidden
price/amount columns, formulas, styles, print settings, or other workbook
features. A future reference-locked test must copy the canonical workbook into
the external test workspace and compare the required fidelity evidence.

## Verification evidence

All commands used `PYTHONDONTWRITEBYTECODE=1`; `TEMP`, `TMP`, pytest base temp,
cache, SQLite databases, uploads, backups, restore evidence, and Excel files
were kept below `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`.

```text
FOCUSED_TESTS=12 passed in 17.31s
FOCUSED_WARNINGS=0
ALEMBIC_SMOKE=PASS
ALEMBIC_HEAD=0004_managed_files
FULL_REGRESSION=52 passed, 1 warning in 122.65s
FAILED_TEST_COUNT=0
FULL_WARNING=unchanged Starlette/httpx deprecation
TEST_ISOLATION=PASS
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
DIFF_CHECK=PASS
QR_AND_UI_DIFF=NONE
QR_FOUR_FIELD_CONTRACT=PASS
```

Focused coverage includes path traversal and injection rejection, safe generated
identity, MIME/extension/signature mismatch, centralized size limit, atomic
publication, checksum correctness, immutable-key conflict, missing/tampered
storage, controlled unavailable storage, multiple images, primary/order,
logical duplicate preservation, generic attachments, replacement history,
failed-publication latch, managed-ID verification, backup manifest integrity,
missing/tampered restore evidence, Excel source non-mutation and bounded feature
preservation, test-root confinement, and fresh/upgrade-path Alembic migration.

The QR payload implementation was untouched. Its exact four fields remain:

```text
product_name
customer_name
product_code
tracking_code
```

No image URL, attachment URL, NAS path, delivery date, or fifth field was added.
Stage5 light-industrial UI code was also untouched.

## Preserved production gaps

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

## Exact stop and next revision

Stop after the R008 candidate commit. Do not merge to `main`, push, access the
production NAS, run a destructive restore, or relabel any preserved gap.

Next exact revision: independently review the frozen R008 candidate as R008A,
including candidate-vs-baseline scope, migration behavior, managed-file state
transitions, storage confinement, backup tamper evidence, Excel source
protection, full regression, isolation, and secret scan. Exact workbook
fidelity remains blocked until the canonical reference file is supplied under
separate authority.
