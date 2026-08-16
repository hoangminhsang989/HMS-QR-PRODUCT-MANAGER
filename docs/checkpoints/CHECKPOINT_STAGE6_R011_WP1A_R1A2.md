# CHECKPOINT — Stage 6 R011-WP1A-R1A2 runtime path portability

Status: pre-commit gates pass; exact post-commit artifact proof is pending.

## Candidate boundary

```text
BASE_HEAD=5ab38301267cda82436cde217adf6369b9702e91
BASE_TREE=d00bcb994353442d3e1a30e18391a7414ce3769c
ORIGIN_MAIN_HEAD=94c33180a31597c9386554a36a9f203659789a29
BRANCH=stage6-r011-wp1a-r1a2-runtime-path-portability-remediation
PRE_REMEDIATION_DEV_PATH_LITERAL_COUNT=8
MACHINE_A_READ_EXECUTION_COUNT=0
MACHINE_A_MUTATION_COUNT=0
MERGE_COUNT=0
PUSH_COUNT=0
```

R1A2 changes only portable path/configuration authority, its direct consumers,
test-harness routing, artifact path scanning, focused tests, and state/checkpoint
metadata. Historical migrations and business-domain behavior are unchanged.

## Runtime path authority inventory

| Concept | DEV/TEST authority | STAGING/PROD authority | Persistence |
|---|---|---|---|
| `SOURCE_ROOT` | Derived from `config/paths.py` module location | Derived from installed release module location | Replaceable release |
| pytest temp/cache/test DB/storage | Explicit `HMS_QR_TEST_ROOT` | Forbidden | Test-only |
| QR/label/Excel generated output | Explicit test root | Explicit `HMS_QR_GENERATED_ASSET_ROOT` | Configured runtime output |
| `APP_DATA_ROOT` | Not production authority | Explicit production config | Persistent |
| `APP_LOG_ROOT` | Not production authority | Explicit production config | Persistent |
| `LOCAL_INGEST_ROOT` | DEV services use injected test storage | Explicit production config | Persistent |
| release artifact output/local deployment simulation | Explicit test root | Live execution disabled | Test/build evidence |
| Alembic database URL | Explicit per invocation | Explicit deployment/runtime injection | Database authority |

No product module embeds a drive, checkout, test, evidence, clone, Machine A,
CWD, or personal-profile fallback. Missing test authority and missing or unsafe
STAGING/PROD generated/persistent roots fail closed.

## Implementation

- `config/paths.py` now derives `SOURCE_ROOT` structurally and validates explicit
  absolute external authorities.
- `config/environments.py` resolves the DEV SQLite/storage root only inside the
  DEV branch; PROD/STAGING imports do not resolve a test root.
- QR, label, and Excel output use environment-separated generated-asset
  authority. PROD/STAGING reject missing, relative, source-contained,
  test-contained, and personal-profile roots.
- Artifact building and the local deployment backend retain test-only external
  containment without a host literal.
- `pyproject.toml` and `alembic.ini` contain no default host path. Root pytest
  configuration requires `HMS_QR_TEST_ROOT` and routes basetemp/cache beneath it.
- The certified-artifact scanner normalizes slash/backslash and escaped path
  variants and reports payload files containing caller-supplied forbidden roots.
- Required `config/paths.py`, `packages/generated_assets.py`, and the read-only
  collector remain in the default certified payload.

## Test evidence

Evidence root:
`F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\stage6-r011-wp1a-r1a2-20260816`

```text
R011_WP1A_R1A2_PATH_TESTS=PASS (13 passed, 0 failed, 3.18s)
R011_WP1A_R1A2_FOCUSED_TESTS=PASS (44 passed, 0 failed, 17.37s)
R011_WP1A_R1A2_CRITICAL_NONREGRESSION=PASS (47 passed, 1 inherited warning, 146.70s)
FULL_REGRESSION=PASS
R011_WP1A_R1A2_FULL_PASSED=187
R011_WP1A_R1A2_FULL_FAILED=0
R011_WP1A_R1A2_FULL_WARNINGS=1 inherited Starlette/httpx deprecation
R011_WP1A_R1A2_FULL_DURATION=548.64s pytest; 550.48s native process
FULL_PROCESS_EXIT_CODE=0
FULL_PROCESS_STDERR_BYTES=0
FULL_STDOUT_SHA256=ed3b5418b8a53c579da8b13c8b9355e22e8c5716e3af1405dc2399f298688ba6
FULL_PYTEST_TERMINAL_VERDICT_OBTAINED=YES
TEST_ISOLATION_PASS=PASS
GIT_DIFF_CHECK=PASS
POSTGRESQL_TEST_CONTAINER_REMAINING_COUNT=0
```

An earlier complete harness run used the wrong delivered-baseline checkout and
therefore produced four expected partial-history fixture failures while 182
other tests passed. The immutable failure evidence was retained. Checkpoint
history identified the required delivered fixture as exact commit `fdf7cc80`;
all six PostgreSQL/SQLite partial-history controls then passed before the final
current-byte full gate. No product or migration byte was changed to mask that
harness defect.

## Security and safety preservation

```text
KNOWN_DEV_REPOSITORY_LITERAL_COUNT=0
KNOWN_EXTERNAL_TEST_ROOT_LITERAL_COUNT=0
ACTIVE_RUNTIME_DEV_ABSOLUTE_PATH_COUNT=0
PRODUCT_RUNTIME_HARDCODED_TEST_ROOT_COUNT=0
TEST_ROOT_SOURCE_FALLBACK_COUNT=0
PROD_TEST_ROOT_REFERENCE_COUNT=0
STAGING_TEST_ROOT_REFERENCE_COUNT=0
PRODUCTION_PERSISTENT_PATH_CWD_AUTHORITY_COUNT=0
PRODUCTION_PERSONAL_PROFILE_PATH_AUTHORITY_COUNT=0
WIN32_SERVICE_PATHNAME_REFERENCE_COUNT=0
RAW_SERVICE_COMMAND_LINE_COLLECTION_COUNT=0
INVENTORY_SECRET_VALUE_COLLECTION_COUNT=0
INVENTORY_MUTATING_COMMAND_COUNT=0
INVENTORY_TARGET_SIDE_FILE_WRITE_COUNT=0
INVENTORY_REMOTE_EXECUTION_CAPABILITY_COUNT=0
PERSISTENT_DATA_DELETE_ON_RELEASE_UPDATE_COUNT=0
PERSISTENT_DATA_DELETE_ON_APP_REMOVE_COUNT=0
DEFAULT_UNINSTALL_PERSISTENT_DATA_DELETE_COUNT=0
DRY_RUN_MACHINE_MUTATION_COUNT=0
WP1A_LIVE_MACHINE_EXECUTION_MODE=DISABLED
LIVE_TARGET_MUTATION_BACKEND_COUNT=0
REAL_SECRET_LEAK_COUNT=0
PRIVATE_KEY_LITERAL_COUNT=0
```

Only dedicated test canaries contain credential-shaped fixture strings. No
real database, NAS, private-key, or production secret literal is present.

## Production boundary

The five production gaps remain open and unchanged:

```text
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

No Machine A read/write, production PostgreSQL provisioning, Windows service,
account, firewall, registry, DPAPI, TLS, NAS, Cloudflare, backup, reboot, merge,
or push occurred. WP1B and Machine A mutation remain unauthorized.

## Post-commit gate

Exactly one child commit of `5ab3830` is permitted. Exact final HEAD/tree,
dual-clone LF/CRLF variation, Git-blob equality, path/secret/forbidden-file
scans, and the new certified artifact identity are recorded only in the
terminal handoff after they exist. Failure of any post-commit gate rejects this
candidate; no second commit or amend is permitted.
