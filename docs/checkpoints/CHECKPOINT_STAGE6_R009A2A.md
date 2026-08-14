# CHECKPOINT — Stage 6 R009A2A Manual Retry Lifecycle Remediation

Date: 2026-08-14
Branch: `stage6-r009a2a-manual-retry-lifecycle-fix`
External artifact root: `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`

## Frozen baseline and defect

```text
R009A2A_BASE_HEAD=76b39d81a31886625b17fbf7c87cc5ad723df7d3
R009A2A_BASE_TREE=89aa7abf348086bae82ca4eb115f07d2658c8291
R009A2A_BASE_PARENT=a2be6d3d9941aa79a2fa94677ce702ecf1c7fe7c
ORIGIN_MAIN_HEAD=fadaeef44d6db082bc64f3e32456b24d6bd7e6b1
START_WORKTREE_CLEAN=YES
R009A2_VERDICT=REJECT_STAGE6_R009A2_MANUAL_RETRY_REQUEUES_REMOTE_VERIFIED_STATE
ROOT_CAUSE_CONFIRMED=YES
```

The frozen implementation no-op'd only `ARCHIVED_REMOTE_ONLY`. Every other
state could be rewritten to `TRANSFER_QUEUED`, including verified grace and
purge states. API and service forwarded directly to that method; Product Files
always exposed retry, while Admin selected both retryable and permanent failure
states by string prefix.

## Bounded remediation

- One canonical repository policy makes only `TRANSFER_FAILED_RETRYABLE`
  eligible for ordinary transfer retry.
- The actual SQL update includes that exact state predicate. Losing a race to
  verification, purge, or an active worker therefore produces a no-op.
- `TRANSFER_QUEUED` is an exact idempotent no-op. Permanent failure requires a
  separate explicit force action, which is not introduced here.
- All ineligible states preserve attempts, scheduling, errors, lease fields,
  remote verification, grace expiry, and `updated_at`.
- Server API remains authoritative and deterministically returns the unchanged
  current job for an ineligible retry.
- Product Files and Admin UI ask the service for the same canonical policy;
  neither offers transfer retry for verified/purge/permanent states.
- `LOCAL_PURGE_PENDING` remains in the existing purge worker. That path
  revalidates managed identity, local and remote checksum/size, verified
  metadata, expired grace, and absence of an active lease before deleting the
  local copy last. A delete failure remains purge-pending without new grace.

No schema, transfer publication, checksum, destination-version, capacity,
authorization, backup, Excel, QR, or unrelated UI contract changed.

## Lifecycle evidence

```text
TRANSFER_RETRY_ELIGIBILITY_POLICY=PASS
REMOTE_VERIFIED_TRANSFER_LIFECYCLE_MONOTONIC=PASS
REMOTE_READY_TRANSFER_RETRY_REQUEUE_COUNT=0
LOCAL_GRACE_TRANSFER_RETRY_REQUEUE_COUNT=0
LOCAL_PURGE_PENDING_TRANSFER_RETRY_REQUEUE_COUNT=0
ARCHIVED_REMOTE_ONLY_TRANSFER_RETRY_REQUEUE_COUNT=0
REMOTE_VERIFIED_AT_MUTATION_AFTER_INELIGIBLE_RETRY_COUNT=0
GRACE_EXPIRY_MUTATION_AFTER_INELIGIBLE_RETRY_COUNT=0
GRACE_EXTENSION_SECONDS=0
REPEATED_REMOTE_VERIFIED_RETRY_IDEMPOTENCY=PASS
PURGE_RETRY_USES_TRANSFER_WORKER_COUNT=0
PURGE_RETRY_LIFECYCLE=PASS
PURGE_RETRY_REVALIDATION=PASS
PURGE_FAILURE_GRACE_RESTART_COUNT=0
QUEUED_MANUAL_RETRY_DUPLICATE_JOB_COUNT=0
FAILED_RETRYABLE_MANUAL_RETRY=PASS
PERMANENT_FAILURE_SILENT_STANDARD_REQUEUE_COUNT=0
ACTIVE_TRANSFER_MANUAL_RETRY_DUPLICATE_WORKER_COUNT=0
MANUAL_RETRY_STATE_CHECK_AND_MUTATION_RACE_SAFE=PASS
RETRY_VS_REMOTE_VERIFY_RACE_STATE_REGRESSION_COUNT=0
RETRY_VS_PURGE_RACE_SAFE=PASS
PENDING_METRIC_MUTATION_AFTER_INELIGIBLE_RETRY_COUNT=0
REMOTE_VERIFIED_MANUAL_RETRY_TRANSFER_WORKER_CALL_COUNT=0
REMOTE_VERIFIED_MANUAL_RETRY_REMOTE_COPY_COUNT=0
SERVER_SIDE_RETRY_ELIGIBILITY_ENFORCEMENT=PASS
UI_TRANSFER_RETRY_INELIGIBLE_STATE_ENABLE_COUNT=0
NORMAL_REMOTE_SUCCESS_GRACE_PERIOD=PASS
NORMAL_LOCAL_DELETE_FAILURE_STATE=PASS
NORMAL_PURGE_COMPLETION=PASS
```

## Test evidence

The first new focused run returned `8 passed / 5 failed`; all five failures
were test-harness timestamps fixed earlier than each fixture's real
`next_retry_at`, so no worker could claim the prepared queued job. Production
logic was unchanged. The test timestamps were bounded to current UTC plus one
minute and the complete rerun passed.

```text
R009A2A_RETRY_FOCUSED_TESTS=13 passed, 1 inherited warning in 47.19s
R009_AUTH_FOCUSED_TESTS=10 passed, 1 inherited warning in 1.09s
R009_FOCUSED_TESTS=22 passed, 1 inherited warning in 87.46s
R009_RUNTIME_HARDENING_TESTS=23 passed, 1 inherited warning in 103.42s
QR_CRITICAL_TESTS=6 passed, 1 inherited warning in 23.90s
QR_EXACT_FIELD_COUNT=4
QR_EXACT_FOUR_FIELD_CONTRACT=PASS
FULL_REGRESSION=98 passed, 1 inherited warning in 376.85s
FULL_PYTEST_TERMINAL_VERDICT_OBTAINED=YES
QT_ANYIO_NATIVE_ABORT_REPRODUCED=NO
FAILED_TEST_COUNT=0
NEW_R009_WARNING_COUNT=0
```

The full run used one pytest process with all 28 test files explicitly listed
and the six Qt-instantiating files last, matching the previously successful
Python 3.14/Windows control. The sole warning remains the inherited
Starlette/httpx deprecation.

## Static, scope, and safety evidence

```text
ALEMBIC_HEAD=0005_store_forward
ALEMBIC_SINGLE_HEAD=PASS
TEST_ISOLATION_PASS=PASS
PRODUCTION_ROOT_TEST_ARTIFACT_COUNT=0
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
GIT_DIFF_CHECK=PASS
UNRELATED_CHANGE_COUNT=0
UNRELATED_PRODUCTION_CHANGE_COUNT=0
NON_RETRY_STORE_FORWARD_PRODUCTION_CHANGE_COUNT=0
PRODUCTION_GAP_RELABEL_COUNT=0
REAL_NAS_WRITE_COUNT=0
PRODUCTION_RESTORE_COUNT=0
EXACT_EXCEL_FIDELITY_CLAIM_COUNT=0
```

The initial isolation check found three `__pycache__` directories created by a
manual compile check in exactly the three compiled module directories. Those
generated artifacts were removed with exact in-workspace paths; the canonical
isolation checker then returned `TEST_ISOLATION_PASS`.

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
`STAGE6_R009A3_INDEPENDENT_REVIEW_OF_REMEDIATED_R009_CANDIDATE`.
