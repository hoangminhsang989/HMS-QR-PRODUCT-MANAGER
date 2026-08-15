# Checkpoint — Stage 6 R010M1A1 partial-history forward compatibility

## Candidate boundary

R010M1A1 is a one-commit descendant remediation of the frozen R010M1
candidate. It does not implement PostgreSQL production integration or close a
production gap.

```text
R010M1A1_BASE_HEAD=64dad613996f184fd7943ee5f8413f8ad4985d51
R010M1A1_BASE_TREE=1c8147fc77dd759ac89c70ba6e766add6f537f01
R010M1A1_BRANCH=stage6-r010m1a1-partial-history-forward-compatibility
R010M1A_REVIEW_VERDICT=REJECT_STAGE6_R010M1A_PARTIALLY_APPLIED_HISTORY_COMPATIBILITY_DEFECT
ALEMBIC_HEAD=0005_store_forward
R010M1A1_NEW_ALEMBIC_REVISION=NO
```

The rejected R010M1 commit remains unchanged. This descendant changes only
historical revisions `0002`/`0003`, focused partial-history tests, this
checkpoint, and `PROJECT_STATE.md`. Migration `0001`, `migrations/env.py`,
`0004`, and `0005` remain byte-identical to R010M1.

## Reproduced defect and compatibility policy

Independent review proved that delivered old `0001` was legitimately stamped
`0001_stage2_baseline` while already containing 15 tables and
`purchase_orders.internal_order_code`. R010M1 `0002` then failed with
PostgreSQL `DuplicateColumn` and left the stamp at `0001`.

R010M1A1 applies this migration-local policy to every possibly pre-created
revision-owned object:

```text
ABSENT -> CREATE EXACT REVISION-OWNED OBJECT
EXISTING + SEMANTIC CONTRACT MATCH -> ADOPT WITHOUT MUTATION
EXISTING + CONTRACT MISMATCH -> FAIL CLOSED BEFORE REVISION MUTATION
```

Validation covers columns, types, lengths, nullability, server defaults, PKs,
FKs, unique constraints, and required indexes. Compatibility code imports no
current ORM model or mutable metadata and does not use generic `checkfirst`.
Matching legacy objects are not dropped, recreated, truncated, deleted, or
rewritten. A missing `internal_order_code` unique constraint is created only
after checking existing non-null values for duplicates.

## Frozen delivered partial states

Before editing migration bytes, exact source from delivered baseline
`fdf7cc80c5fd262b0b69b29ed2489b8d7558ce90` was extracted beneath the external
test root. Independent PostgreSQL 17 and SQLite databases were constructed at
old `0001`, old `0002`, and old `0003`. Full physical fingerprints record
tables, columns, types, nullability, defaults, PKs, FKs, uniques, and indexes.

All six states physically contained 15 tables and the premature
`internal_order_code`, while preserving their distinct legitimate Alembic
stamps. Each database received one valid FK-complete sentinel row in every one
of the 14 application tables before forward migration.

```text
DELIVERED_OLD_0001_CONTRACT_FROZEN=PASS
DELIVERED_OLD_0002_CONTRACT_FROZEN=PASS
DELIVERED_OLD_0003_CONTRACT_FROZEN=PASS
LEGACY_PARTIAL_DATA_FIXTURE=PASS
LEGACY_SENTINEL_APPLICATION_TABLE_COUNT=14
LEGACY_SENTINEL_ROW_COUNT_PER_DATABASE=14
```

## Forward compatibility and data preservation

```text
OLD_PG_0001_TO_NEW_HEAD=PASS
OLD_PG_0002_TO_NEW_HEAD=PASS
OLD_PG_0003_TO_NEW_HEAD=PASS
OLD_SQLITE_0001_TO_NEW_HEAD=PASS
OLD_SQLITE_0002_TO_NEW_HEAD=PASS
OLD_SQLITE_0003_TO_NEW_HEAD=PASS
OLD_PG_0001_INTERNAL_ORDER_CODE_VALUE_PRESERVATION=PASS
OLD_PG_0001_PRECREATED_TABLE_DATA_PRESERVATION=PASS
LEGACY_PARTIAL_ROW_PRESERVATION=PASS
FORWARD_COMPATIBILITY_PREEXISTING_OBJECT_DELETE_COUNT=0
LEGACY_COMPATIBILITY_DESTRUCTIVE_OPERATION_COUNT=0
PARTIAL_HISTORY_MIGRATION_CONTRACT=PASS
ALL_MIGRATION_PATHS_CONVERGE_TO_HEAD_SCHEMA=PASS
LEGACY_PARTIAL_DOWNGRADE_SUPPORT=NOT_IN_SCOPE_FORWARD_COMPATIBILITY_ONLY
```

All three old PostgreSQL paths converged to one semantic head schema hash, and
all three old SQLite paths converged to one semantic head schema hash. Legacy
row snapshots remained exactly equal before and after forward migration.

## Fail-closed negative controls

PostgreSQL and SQLite controls independently prove:

- wrong `internal_order_code` type/nullability/default is rejected;
- a malformed pre-existing `0002` table is rejected before any revision
  mutation;
- a malformed pre-existing `tracking_workflow_events` table is rejected;
- duplicate non-null `internal_order_code` values prevent unique-constraint
  creation without altering or deleting either value;
- every rejection leaves the Alembic stamp at the previous revision.

```text
MALFORMED_EXISTING_COLUMN_FAIL_CLOSED=PASS
MALFORMED_EXISTING_TABLE_FAIL_CLOSED=PASS
MALFORMED_EXISTING_0003_TABLE_FAIL_CLOSED=PASS
LEGACY_UNIQUE_CONFLICT_FAIL_CLOSED=PASS
DATA_MUTATION_TO_FORCE_UNIQUENESS_COUNT=0
MISMATCH_FAILURE_STAMP_ADVANCE_COUNT=0
```

## Fresh-history and existing-head contracts

```text
FRESH_PG_0001_TABLE_COUNT=7
FRESH_PG_0002_TABLE_COUNT=14
FRESH_PG_0003_TABLE_COUNT=15
FRESH_PG_0004_TABLE_COUNT=17
FRESH_PG_0005_TABLE_COUNT=19
FRESH_SQLITE_0001_TABLE_COUNT=7
FRESH_SQLITE_0002_TABLE_COUNT=14
FRESH_SQLITE_0003_TABLE_COUNT=15
FRESH_SQLITE_0004_TABLE_COUNT=17
FRESH_SQLITE_0005_TABLE_COUNT=19
PG_ALL_CURRENT_MODELS_PREIMPORTED_0001=PASS
SQLITE_ALL_CURRENT_MODELS_PREIMPORTED_0001=PASS
PG_FRESH_DOWNGRADE_HEAD_TO_BASE=PASS
PG_FRESH_REUPGRADE_BASE_TO_HEAD=PASS
SQLITE_FRESH_DOWNGRADE_HEAD_TO_BASE=PASS
SQLITE_FRESH_REUPGRADE_BASE_TO_HEAD=PASS
EXISTING_HEAD_DB_UPGRADE_NOOP=PASS
```

## Historical hash accounting

Canonical filtered-byte SHA-256 values:

| Path | R010M1 | R010M1A1 |
|---|---|---|
| `0001_stage2_baseline.py` | `ceb3686f859d2727cfff6b8f6e7bc41138e4d5199834d0ce144d64d191b76e97` | `ceb3686f859d2727cfff6b8f6e7bc41138e4d5199834d0ce144d64d191b76e97` |
| `0002_tracking_qr_reporting.py` | `2a69c160ea1cad1e794f285a1afd3f1b8dab861af1966c3a3112317f63de8920` | `157cb8a430bc6b4fa920010dd2ea4088e1f30b4ff887d34a9be819c54f0cea1b` |
| `0003_qc_packing_delivery_events.py` | `afdf1a30f959d7335aff937c550926ded3e23383dc5f29cd4b3f5a1e46d8ce2b` | `3b167d9c62100e79ed9da2ae894be6fb52daa42a05bdf3351df5ffe251848f63` |

```text
R010M1A1_0001_BYTE_CHANGE_COUNT=0
ALEMBIC_ENV_BYTE_CHANGE_COUNT=0
REVISION_0004_BYTE_CHANGE_COUNT=0
REVISION_0005_BYTE_CHANGE_COUNT=0
ALEMBIC_REVISION_ID_CHANGE_COUNT=0
ALEMBIC_DOWN_REVISION_GRAPH_CHANGE_COUNT=0
R010M1A1_HISTORICAL_BYTE_CHANGE_ACCOUNTED=PASS
```

## Test evidence

PostgreSQL runtime: `17.11 (Debian 17.11-1.pgdg13+2)`.

```text
R010M1A1_PARTIAL_HISTORY_FOCUSED_TESTS=15 passed in 69.52s
R010M1_FRESH_HISTORY_TESTS=5 passed in 24.38s
R008_R009_MIGRATION_REGRESSION=12 passed, 1 inherited warning in 81.42s
R010M1A1_CRITICAL_BUSINESS_NONREGRESSION=97 passed, 1 inherited warning in 326.19s
QR_EXACT_FOUR_FIELD_CONTRACT=PASS
R009_STORE_FORWARD_REGRESSION=PASS
FULL_REGRESSION=PASS
R010M1A1_FULL_PASSED=125
R010M1A1_FULL_FAILED=0
R010M1A1_FULL_WARNINGS=1 inherited Starlette/httpx deprecation
R010M1A1_FULL_DURATION=547.43s
FULL_PYTEST_TERMINAL_VERDICT_OBTAINED=YES
```

## Safety and production boundary

```text
APPLIED_PRODUCTION_HISTORY_EVIDENCE=NONE_FOUND
PARTIAL_HISTORY_ABANDONMENT_ASSUMPTION_COUNT=0
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
DATABASE_SECRET_LITERAL_COUNT=0
RETAINED_EXPOSED_CREDENTIAL_MATCH_COUNT=0
TEST_ISOLATION_PASS=PASS
PRODUCTION_ROOT_TEST_ARTIFACT_COUNT=0
POSTGRESQL_APPLICATION_WIRING_CHANGE_COUNT=0
PRODUCT_MASTER_REPOSITORY_CHANGE_COUNT=0
PRODUCTION_DATABASE_CONFIG_CHANGE_COUNT=0
DATABASE_READINESS_CHANGE_COUNT=0
POSTGRESQL_POOL_POLICY_CHANGE_COUNT=0
TRACKED_POSTGRESQL_DRIVER_CHANGE_COUNT=0
UNRELATED_PRODUCTION_CHANGE_COUNT=0
PRODUCTION_GAP_RELABEL_COUNT=0
REAL_NAS_WRITE_COUNT=0
PRODUCTION_RESTORE_COUNT=0
EXACT_EXCEL_FIDELITY_CLAIM_COUNT=0
POSTGRESQL_TEST_RUNTIME_STOPPED=YES
POSTGRESQL_TEST_CONTAINER_REMAINING_COUNT=0
```

All six production gaps remain unresolved, especially
`POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED`.

## Verdict and stop boundary

```text
PASS_STAGE6_R010M1A1_PARTIAL_HISTORY_FORWARD_COMPATIBILITY_REMEDIATION_CANDIDATE
R010M1A1_CANDIDATE_READY_FOR_INDEPENDENT_REVIEW=YES
```

No merge or push occurred. R010 PostgreSQL product implementation remains
pending and must not resume without separate authority.
