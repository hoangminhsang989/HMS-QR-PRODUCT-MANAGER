# CHECKPOINT — Stage 6 R011-WP1A source-side deployment foundation

Status: implementation candidate; independent review required.

## Delivered

- `packages/deployment/` boundary with deterministic immutable release builder,
  manifest/hash verifier, symbolic root layout, production config validation,
  DPAPI-shaped secret-store interface, service/restart model, PostgreSQL and
  network/TLS/firewall plan models, mutation manifest, pure preflight/dry-run,
  local fake lifecycle backend, rollback and preserve-data uninstall model, and
  secret-free evidence sanitizer.
- Deployment plan binds the canonical inventory SHA-256 and release identity;
  preflight covers OS/architecture, filesystem/capacity, listener/service
  collision, PostgreSQL/runtime/TLS/firewall/secret/rollback resolution. Dry-run
  consumes the same artifact/config/inventory/plan and exposes no executor.
- The external-root-only fake backend models PRESTATE/VERIFY/STAGE/ACTIVATE/
  health/accept or revert, versioned release retention, compatibility-gated
  rollback, idempotent staging, and preserve-data uninstall.
- Strictly read-only inventory collector with explicit allowlist, unknown-state
  semantics, schema validation, and fixture-driven tests. The collector has not
  been run against Machine A.
- Vietnamese-first operator runbook draft.

## Evidence

```text
BASE_HEAD=94c33180a31597c9386554a36a9f203659789a29
BASE_TREE=082faf26ec8ab1374adae80d8ac62b8824b01b39
WP1A_BRANCH=stage6-r011-wp1a-source-side-deployment-foundation
R011_WP1A_FOCUSED_TESTS=20 passed, 0 failed in 3.02s
R011_WP1A_FULL_REGRESSION=163 passed, 0 failed, 1 inherited warning
R011_WP1A_FULL_DURATION=556.38s pytest / 557.99s process
R011_WP1A_FULL_STDOUT_SHA256=9f4012ad7fe6be2aef4b3828dd13c7f2f64abed174078e1d5632dd3bf033996f
FULL_PROCESS_EXIT_CODE=0
FULL_PROCESS_STDERR_BYTES=0
FULL_PYTEST_TERMINAL_VERDICT_OBTAINED=YES
POSTGRESQL_TEST_RUNTIME_STOPPED=YES
POSTGRESQL_TEST_CONTAINER_REMAINING_COUNT=0
MACHINE_A_READ_EXECUTION_COUNT=0
MACHINE_A_MUTATION_COUNT=0
PRODUCTION_POSTGRESQL_INSTALL_COUNT=0
WINDOWS_SERVICE_MUTATION_COUNT=0
WINDOWS_FIREWALL_MUTATION_COUNT=0
REAL_MACHINE_DPAPI_OPERATION_COUNT=0
REAL_NAS_WRITE_COUNT=0
MACHINE_A_INVENTORY_EXECUTED=NO
WP1B_MACHINE_A_READ_AUTHORIZED=NO
MACHINE_A_MUTATION_AUTHORIZED=NO
```

Independent review remains required after the single candidate commit. No
merge, push, Machine A access, or production action is authorized by this
checkpoint.
