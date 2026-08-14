# Checkpoint - Stage 6 R008A1

## Verdict

`PASS_STAGE6_R008A1_ALEMBIC_REVISION_BOUNDARY_REMEDIATION_CANDIDATE`

This is a bounded descendant remediation candidate. It does not supersede the
historical R008A rejection with an independent approval, and it does not grant
merge or push authority.

## Frozen evidence and remediation identity

```text
REJECTED_R008_HEAD=de20e462522b55ff2287c4e9f545eb288c8a3f42
REJECTED_R008_TREE=4fed56c2d109a16f190c903d657b00377b61b4d2
R008A_VERDICT=REJECT_STAGE6_R008A_ALEMBIC_REVISION_BOUNDARY_VIOLATION
REMEDIATION_BASE_HEAD=de20e462522b55ff2287c4e9f545eb288c8a3f42
REMEDIATION_BASE_TREE=4fed56c2d109a16f190c903d657b00377b61b4d2
REMEDIATION_BRANCH=stage6-r008a1-alembic-boundary-fix
```

The rejected candidate remains unchanged. R008A1 was developed in an isolated
descendant worktree and does not amend or rewrite `de20e462`.

## Root cause and bounded fix

The unpublished `0004_managed_files` revision imported
`packages.persistence.storage_models` at module scope. Alembic imports revision
modules while building its graph, so this registered the two Stage6 tables in
the shared application `Base.metadata`. Historical migration `0001` later
executed `Base.metadata.create_all()`, causing those tables to be created even
when a fresh database targeted revision `0003`.

R008A1 removes the model-registration side effect. Revision `0004` now declares
its tables, foreign keys, unique constraints, and indexes directly through
standalone Alembic/SQLAlchemy DDL. Historical migration `0001` is unchanged.
The physical schema at head was compared against the existing ORM contract for
columns, types, nullability, primary keys, defaults, foreign keys, indexes, and
unique constraints.

The downgrade drops only the Stage6 relation index/tables and managed-file
indexes/table, in dependency-safe order.

## Black-box migration evidence

Every migration transition below ran in a clean Python subprocess with a fresh
SQLite database under `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST` and was inspected
through SQLAlchemy against the physical database:

```text
FRESH_TO_0003_REVISION=0003_qc_packing_delivery
FRESH_TO_0003_MANAGED_FILES=ABSENT
FRESH_TO_0003_PRODUCT_FILE_RELATIONS=ABSENT
UPGRADE_TO_HEAD_REVISION=0004_managed_files
UPGRADE_TO_HEAD_MANAGED_FILES=PRESENT
UPGRADE_TO_HEAD_PRODUCT_FILE_RELATIONS=PRESENT
DOWNGRADE_TO_0003_REVISION=0003_qc_packing_delivery
DOWNGRADE_TO_0003_MANAGED_FILES=ABSENT
DOWNGRADE_TO_0003_PRODUCT_FILE_RELATIONS=ABSENT
REUPGRADE_TO_HEAD_REVISION=0004_managed_files
REUPGRADE_TO_HEAD_MANAGED_FILES=PRESENT
REUPGRADE_TO_HEAD_PRODUCT_FILE_RELATIONS=PRESENT
ALEMBIC_HEADS=0004_managed_files
ALEMBIC_SINGLE_HEAD=PASS
MIGRATION_0004_SHARED_ORM_IMPORT_COUNT=0
MIGRATION_0004_SCHEMA_SEMANTIC_EQUIVALENCE=PASS
ALEMBIC_REVISION_GRAPH_STAGE6_METADATA_SIDE_EFFECT=NONE
```

Existing in-process Alembic tests were narrowly changed to clean subprocess
execution because whole-suite pytest collection imports later ORM modules before
earlier-stage tests run. This keeps migration verification representative of a
clean Alembic process and prevents the test harness from mutating shared ORM
metadata before a historical target is executed.

## Test evidence

All runtime artifacts, SQLite files, pytest temp/cache, and logs were directed
beneath the external test root.

```text
MIGRATION_BOUNDARY_TEST=1 passed in 8.81s
STAGE6_FOCUSED_TESTS=13 passed in 45.17s
TARGETED_MIGRATION_RECOVERY=6 passed, 1 inherited warning in 49.02s
FULL_REGRESSION=53 passed, 1 inherited warning in 135.87s
FAILED_TEST_COUNT=0
```

The sole warning remains the inherited Starlette/httpx deprecation. No QR,
storage, attachment, product-image, backup, Excel, UI, or application behavior
was changed by R008A1.

## Preserved production gaps

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

## Exact stop

Stop after the single descendant remediation commit. Do not merge or push.
The next exact action is
`STAGE6_R008A2_INDEPENDENT_REVIEW_OF_REMEDIATED_CANDIDATE`, which must first
reproduce the migration boundary and then restart the R008A gates that stopped
after the defect.
