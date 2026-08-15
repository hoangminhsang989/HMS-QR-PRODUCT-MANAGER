# Checkpoint — Stage 6 R010M1 historical migration boundary remediation

## Candidate boundary

R010M1 is a prerequisite migration-history remediation candidate. It is not
PostgreSQL production integration and does not close any production gap.

```text
BASE_HEAD=fdf7cc80c5fd262b0b69b29ed2489b8d7558ce90
BASE_TREE=32a0b3b0e75030300c28de84fe8a781cd58ae910
R010M1_BRANCH=stage6-r010m1-historical-migration-boundary-remediation
ALEMBIC_HEAD=0005_store_forward
R010M1_NEW_ALEMBIC_REVISION=NO
```

No PostgreSQL application wiring, Product repository, production database
configuration, readiness, pool policy, business workflow, UI, QR, storage,
backup, or Excel behavior changed.

## Reproduced defect and ownership

On a fresh PostgreSQL 17 database, the pre-remediation `0001` produced 15
physical tables instead of the frozen 7-table contract. Eight tables owned by
`0002`/`0003` leaked into `0001`, and
`purchase_orders.internal_order_code` appeared prematurely.

The revision-introduction commits and contemporaneous model/checkpoint evidence
freeze ownership as follows:

- `0001_stage2_baseline`: six Stage 2 application tables;
- `0002_tracking_qr_reporting`: `internal_order_code`, its unique constraint,
  and seven tracking/report tables;
- `0003_qc_packing_delivery`: `tracking_workflow_events`;
- `0004_managed_files`: two managed-file tables, unchanged;
- `0005_store_forward`: two store-forward tables, unchanged.

The pre-edit ownership matrix and existing-head control are retained under
`F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\stage6-r010m1-postgresql\evidence`.

## Bounded historical byte remediation

`0001` no longer uses mutable `Base.metadata.create_all/drop_all`. `0002` and
`0003` no longer import current ORM table objects. All three revisions now own
explicit Alembic DDL and reverse only their own delta. `0002` downgrade also
removes its named `internal_order_code` unique constraint and column.

Canonical baseline Git-blob SHA-256 and candidate SHA-256:

| Path | Old SHA-256 | New SHA-256 | Reason |
|---|---|---|---|
| `migrations/versions/0001_stage2_baseline.py` | `9c833bd4315bd7deab4ef458d5613d6fd86ce1890eab04ffb3fd653440ec92ff` | `ceb3686f859d2727cfff6b8f6e7bc41138e4d5199834d0ce144d64d191b76e97` | Remove mutable global metadata ownership |
| `migrations/versions/0002_tracking_qr_reporting.py` | `59f1d10fccd25fb0e185eadee9e7d11c9b717c0353891313827944634386dd85` | `2a69c160ea1cad1e794f285a1afd3f1b8dab861af1966c3a3112317f63de8920` | Freeze the exact 0002 delta and repair downgrade ownership |
| `migrations/versions/0003_qc_packing_delivery_events.py` | `c7caf628dc159b39c093b3929d452a49d1f08a97de08039ad8911b6d01b8d69d` | `afdf1a30f959d7335aff937c550926ded3e23383dc5f29cd4b3f5a1e46d8ce2b` | Freeze the exact 0003 delta |

`migrations/env.py`, `0004_managed_files.py`, and `0005_store_forward.py`
remain unchanged. Revision IDs and the down-revision graph remain unchanged.

## Physical boundary evidence

PostgreSQL 17.11 and SQLite both produced the exact cumulative table counts:

```text
0001=7
0002=14
0003=15
0004=17
0005/head=19
```

`internal_order_code` is absent at `0001`, present at `0002`, removed by the
`0002 -> 0001` downgrade, and restored by re-upgrade. Complete downgrade to
base removes every application table; complete re-upgrade reproduces the same
head schema. Pre-importing all current ORM modules before `0001` does not alter
the physical `0001` boundary.

Fresh-head migration schemas match current ORM schemas on SQLite and
PostgreSQL for columns, types, nullability, PKs, FKs, uniques, indexes, and
defaults. The SQLite database frozen at delivered `0005` before remediation
remained raw-byte and schema-signature identical after `alembic upgrade head`:

```text
EXISTING_HEAD_DB_SCHEMA_SHA256=64aaf5ce53795ed49a2708ad84620c14566068d299274fcd6d4c2ce0df248493
EXISTING_HEAD_DB_RAW_SHA256=6708040aeecd0a539401da0a2e59595ea87219092db619bc1176cccc9076a589
EXISTING_HEAD_DB_UPGRADE_NOOP=PASS
```

## Test evidence

The first new-test invocation exposed two test-oracle defects and printed its
disposable PostgreSQL URL in pytest traceback context. That runtime was stopped
and removed immediately, invalidating the credential. A fresh container and
credential were created; all subsequent tests used a password-free redacted
URL plus process-local `PGPASSWORD`. No credential entered repository or
retained evidence bytes.

```text
R010M1_NEW_MIGRATION_TESTS=5 passed in 25.80s
R008_R009_MIGRATION_REGRESSION=17 passed, 1 inherited warning in 101.27s
R010M1_CRITICAL_BUSINESS_NONREGRESSION=77 passed, 1 inherited warning in 258.92s
FULL_REGRESSION=PASS
R010M1_FULL_PASSED=110
R010M1_FULL_FAILED=0
R010M1_FULL_WARNINGS=1 inherited Starlette/httpx deprecation
R010M1_FULL_DURATION=406.22s
FULL_PYTEST_TERMINAL_VERDICT_OBTAINED=YES
QT_ANYIO_NATIVE_ABORT_REPRODUCED=NO
```

## Final safety gates

```text
TEST_ISOLATION_PASS=PASS
PRODUCTION_ROOT_TEST_ARTIFACT_COUNT=0
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
DATABASE_SECRET_LITERAL_COUNT=0
GIT_DIFF_CHECK=PASS
POSTGRESQL_APPLICATION_WIRING_CHANGE_COUNT=0
PRODUCT_MASTER_REPOSITORY_CHANGE_COUNT=0
PRODUCTION_DATABASE_CONFIG_CHANGE_COUNT=0
DATABASE_READINESS_CHANGE_COUNT=0
POSTGRESQL_POOL_POLICY_CHANGE_COUNT=0
UNRELATED_CHANGE_COUNT=0
PRODUCTION_GAP_RELABEL_COUNT=0
REAL_NAS_WRITE_COUNT=0
PRODUCTION_RESTORE_COUNT=0
EXACT_EXCEL_FIDELITY_CLAIM_COUNT=0
POSTGRESQL_TEST_RUNTIME_STOPPED=YES
POSTGRESQL_TEST_CONTAINER_REMAINING_COUNT=0
```

## Verdict and stop boundary

```text
PASS_STAGE6_R010M1_HISTORICAL_MIGRATION_BOUNDARY_REMEDIATION_CANDIDATE
R010M1_CANDIDATE_READY_FOR_INDEPENDENT_REVIEW=YES
```

R010M1 is not merged or pushed. Do not resume R010 product implementation
until this exact candidate receives an independent review and later authority.
