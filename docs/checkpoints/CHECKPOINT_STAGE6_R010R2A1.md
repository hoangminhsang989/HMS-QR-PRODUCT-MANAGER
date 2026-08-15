# Checkpoint - Stage 6 R010R2A1 true PostgreSQL concurrency evidence remediation

Date: 2026-08-15
Branch: `stage6-r010r2a1-true-postgresql-concurrency-evidence`
Frozen rejected candidate: `5e3752f7dbe9c0e9ad197f9a979879f23302a75a`
Frozen tree: `d76b90c20ee97b8cb86f4ccb64f2f1df4af0663d`
Canonical main/origin baseline: `f80b7dbf6c3744f182648b47454be0afc1105992`
Status: test/evidence remediation candidate only; not independently approved,
not integrated, and not pushed

## Rejection reproduced and scope preserved

R010R2A rejected the frozen implementation candidate because the original
`ThreadPoolExecutor` tests did not prove deterministic transaction overlap.
They had no Barrier/Event gate, no held-lock window, no PostgreSQL wait
observation, and could pass under sequential execution.

```text
THREAD_POOL_EXECUTOR_BLOCK_COUNT=6
SYNCHRONIZATION_BARRIER_COUNT_BEFORE=0
SYNCHRONIZATION_EVENT_COUNT_BEFORE=0
EXPLICIT_LOCK_HOLDER_OR_BLOCKING_ASSERTION_COUNT_BEFORE=0
CONCURRENCY_TEST_WEAKNESS_REPRODUCED=YES
```

The frozen production implementation was not edited. The remediation changes
only the R010R2 PostgreSQL concurrency test module and a new test-only helper.

```text
PRODUCTION_SOURCE_CHANGE_COUNT=0
MIGRATION_CHANGE_COUNT=0
DEPENDENCY_CHANGE_COUNT=0
DATABASE_RUNTIME_CHANGE_COUNT=0
PRODUCT_REPOSITORY_CHANGE_COUNT=0
STORE_FORWARD_PRODUCTION_CHANGE_COUNT=0
```

Historical migration Git-blob bytes remain exact:

```text
0001_SHA256=ceb3686f859d2727cfff6b8f6e7bc41138e4d5199834d0ce144d64d191b76e97
0002_SHA256=157cb8a430bc6b4fa920010dd2ea4088e1f30b4ff887d34a9be819c54f0cea1b
0003_SHA256=3b167d9c62100e79ed9da2ae894be6fb52daa42a05bdf3351df5ffe251848f63
ALEMBIC_HEAD=0005_store_forward
NEW_0006_COUNT=0
```

## Strengthened true-concurrency contract

The test-only `DecisiveSqlWindow` attaches scoped SQLAlchemy events to the real
product engine. Two worker sessions are stopped at the matched decisive SQL,
record their actual `pg_backend_pid()`, and cross a two-party Barrier before
SQL execution can continue. Every Barrier, Event, Future result, PostgreSQL
lock wait, and lock timeout is bounded. The helper neither mocks repository
returns nor commits or changes isolation semantics on behalf of production.

The row-lock control holds the first successful `SELECT ... FOR UPDATE` result
open, proves that both Python futures remain incomplete, and independently
observes the other backend in `pg_stat_activity` with
`wait_event_type='Lock'` before releasing the holder. Atomic/nonblocking cases
use the same decisive-SQL barrier and prove distinct live backends plus the
final physical invariant.

```text
TRUE_CONCURRENCY_TEST_CONTRACT_FROZEN=PASS
DISTINCT_POSTGRESQL_BACKENDS=PASS
DECISIVE_OPERATION_OVERLAP_SYNCHRONIZATION=PASS
TRUE_OVERLAP_PROOF=PASS
ATOMIC_CONCURRENCY_EVIDENCE=PASS
CONCURRENCY_TEST_BOUNDED_TIMEOUT_POLICY=PASS
SLEEP_ONLY_CONCURRENCY_SYNCHRONIZATION_COUNT=0
CONCURRENCY_REPEAT_ITERATIONS=10
CONCURRENCY_REPEATABILITY=PASS
CONCURRENCY_SCHEDULING_ORDER_DEPENDENCE=NONE_DETECTED
```

```text
ROW_LOCKING_TEST_DESIGN_INDEPENDENT_SESSIONS=PASS
ROW_LOCK_HOLDER_BACKEND_DISTINCT=PASS
ROW_LOCK_WAITER_OBSERVED=PASS
ROW_LOCK_SECOND_TRANSACTION_COMPLETED_BEFORE_RELEASE_COUNT=0
POSTGRESQL_ROW_LOCKING=PASS

IDEMPOTENCY_TEST_TRUE_CONCURRENCY=PASS
IDEMPOTENCY_BOTH_WORKERS_IN_FLIGHT_BEFORE_FIRST_COMPLETION=PASS
POSTGRESQL_CONCURRENT_IDEMPOTENCY=PASS
COMMITTED_EFFECTIVE_EVENT_COUNT=1 per repetition
DUPLICATE_EFFECTIVE_EVENT_COUNT=0
INCOMPATIBLE_IDEMPOTENCY_REUSE_FAIL_CLOSED=PASS

ENSURE_JOB_TEST_TRUE_CONCURRENCY=PASS
POSTGRESQL_CONCURRENT_ENSURE_JOB=PASS
DUPLICATE_TRANSFER_JOB_COUNT=0

STORE_FORWARD_LEASE_TEST_TRUE_CONCURRENCY=PASS
STORE_FORWARD_BOTH_WORKERS_IN_CLAIM_WINDOW=PASS
POSTGRESQL_STORE_FORWARD_LEASE_CLAIM=PASS
POSTGRESQL_DUPLICATE_ACTIVE_WORKER_COUNT=0
EXACT_ACTIVE_LEASE_OWNER_COUNT=1 per repetition
POSTGRESQL_STALE_LEASE_RECOVERY=PASS
PRE_EXPIRY_SECOND_OWNER_COUNT=0
POST_EXPIRY_RECOVERY_OWNER_COUNT=10

ACTIVE_STORAGE_CONFIG_TEST_TRUE_CONCURRENCY=PASS
POSTGRESQL_ACTIVE_STORAGE_CONFIG_CONCURRENCY=PASS
FINAL_ACTIVE_STORAGE_CONFIG_COUNT=1 per repetition

PRODUCT_PRIMARY_TEST_TRUE_CONCURRENCY=PASS
POSTGRESQL_PRODUCT_PRIMARY_CONFLICT_CONTROL=PASS
FINAL_EFFECTIVE_PRIMARY_IMAGE_COUNT=1 per repetition

MANAGED_FILE_RELATION_TEST_TRUE_CONCURRENCY=PASS
POSTGRESQL_MANAGED_FILE_RELATION_CONCURRENCY=PASS
FINAL_LOGICAL_RELATION_COUNT=1 per repetition
```

Evidence matrix:

| Domain | Protection | Decisive overlap | Observed DB effect | Final invariant | Defect caught |
| --- | --- | --- | --- | --- | --- |
| Row lock | `SELECT FOR UPDATE` | SQL barrier plus held result | backend lock wait | one effective event | missing row lock |
| Idempotency | row lock plus unique UUID | SQL barrier | semantic replay or fail-closed conflict | one committed event | duplicate or incompatible reuse |
| Ensure job | unique managed-file job | INSERT barrier | insert arbitration | one transfer job | duplicate job |
| Lease | conditional UPDATE | UPDATE barrier | one rowcount winner | one active lease | double ownership |
| Active config | transaction advisory lock | advisory-lock barrier | serialized activation | one active config | multiple active configs |
| Primary image | product advisory lock | advisory-lock barrier | serialized selection | one primary image | multiple primaries |
| File relation | PK/unique constraints | INSERT barrier | one commit and one conflict | one logical relation | duplicate relation |

The first strengthened module run reported two claimed jobs in the lease test.
Physical inspection showed that earlier `ensure_job` repetitions had left
other eligible queue rows, while `claim_next` is intentionally queue-wide.
This was a test-fixture isolation defect, not double ownership of one job. The
test now quarantines previously eligible rows before lease repetitions begin;
the lease-only rerun passed all ten repetitions and the complete focused
module then passed twice. No production source was changed.

## Real PostgreSQL and regression evidence

```text
POSTGRESQL_IMAGE=postgres:17
POSTGRESQL_SERVER_VERSION=17.11 (Debian 17.11-1.pgdg13+2)
POSTGRESQL_HOST_BIND=127.0.0.1:55433
POSTGRESQL_READINESS=PASS
POSTGRESQL_REAL_CONNECTION=PASS

R010R2A1_TRUE_CONCURRENCY_FOCUSED_TESTS=PASS
TRUE_CONCURRENCY_FOCUSED_PASSED=10
TRUE_CONCURRENCY_FOCUSED_FAILED=0
TRUE_CONCURRENCY_FOCUSED_DURATION=11.53s

R010R2_POSTGRESQL_FOCUSED_REGRESSION=PASS
R010R2_POSTGRESQL_FOCUSED_PASSED=18
R010R2_POSTGRESQL_FOCUSED_FAILED=0
R010R2_POSTGRESQL_FOCUSED_WARNINGS=1 inherited Starlette/httpx deprecation

R010_MIGRATION_HISTORY_REGRESSION=PASS
R010_MIGRATION_HISTORY_PASSED=26
SQLITE_DEV_TEST_COMPATIBILITY=PASS
SQLITE_DEV_TEST_PASSED=38
R010R2A1_CRITICAL_NONREGRESSION=PASS
R010R2A1_CRITICAL_PASSED=88
QR_EXACT_FOUR_FIELD_CONTRACT=PASS
R009_STORE_FORWARD_REGRESSION=PASS

FULL_GATE_LAUNCHER_NATIVE_EXIT_PROPAGATION=PASS
FULL_GATE_LAUNCHER_CRASH_MASK_COUNT=0
QT_ANYIO_NATIVE_ABORT_REPRODUCED=NO_IN_APPROVED_QT_LAST_GATE
FULL_REGRESSION=PASS
R010R2A1_FULL_PASSED=143
R010R2A1_FULL_FAILED=0
R010R2A1_FULL_WARNINGS=1 inherited Starlette/httpx deprecation
R010R2A1_FULL_DURATION=547.50s
FULL_PROCESS_DURATION=549.13s
FULL_PROCESS_EXIT_CODE=0
FULL_PROCESS_STDERR_BYTES=0
FULL_PROCESS_STDOUT_SHA256=7bc252e5a2a6fc9b5e5d22662137ce0422635749cbc14044c6e6c16cfc160b2d
FULL_PYTEST_TERMINAL_VERDICT_OBTAINED=YES
```

The full gate used one native-process-safe, Qt-last pytest invocation. It did
not retry after a crash, split the suite, or infer success from heartbeat.

## Safety, cleanup, and delivery boundary

```text
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
DATABASE_SECRET_LITERAL_COUNT=0
TEST_ISOLATION_PASS=PASS
PRODUCTION_ROOT_TEST_ARTIFACT_COUNT=0
GIT_DIFF_CHECK=PASS
UNRELATED_CHANGE_COUNT=0
PRODUCTION_GAP_RELABEL_COUNT=0
REAL_NAS_WRITE_COUNT=0
PRODUCTION_RESTORE_COUNT=0
MACHINE_A_ACTION_COUNT=0
CLOUDFLARE_ACTION_COUNT=0
EXACT_EXCEL_FIDELITY_CLAIM_COUNT=0
POSTGRESQL_TEST_RUNTIME_STOPPED=YES
POSTGRESQL_TEST_CONTAINER_REMAINING_COUNT=0
MERGE_COUNT=0
PUSH_COUNT=0
```

All six production gaps remain unresolved, especially
`POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED`. R010R2A1 establishes a
candidate for improved test evidence only. It does not approve R010R2 for
integration or production use.

## Verdict and next boundary

```text
PASS_STAGE6_R010R2A1_TRUE_POSTGRESQL_CONCURRENCY_EVIDENCE_REMEDIATION_CANDIDATE
R010R2A1_CANDIDATE_READY_FOR_INDEPENDENT_REVIEW=YES
```

The next action is a fresh independent review of the frozen R010R2A1 candidate.
Do not merge, push, deploy, write a real NAS, perform a production restore, act
on Machine A, or close any production gap under this checkpoint.
