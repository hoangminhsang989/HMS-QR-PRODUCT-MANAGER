# CHECKPOINT — Stage 6 R011-WP1A-R1A1 remediation candidate

Status: descendant remediation candidate pending fresh independent review.

## Authorized remediation

- Preserved the uncommitted R1A Git-object artifact work without reset, stash,
  discard, or reconstruction. The pre-extension artifact-test SHA-256 was
  `d9358cf51ed923f578d47ab9f0e859d7826c24dba5ebabd17c25abc90072f0ec`.
- Certified release payloads now come only from exact committed Git blobs read
  through `ls-tree` and `cat-file`; working-tree files remain cleanliness and
  execution context only. Regular and executable blobs are allowed; unsupported
  entry types fail closed.
- The read-only collector no longer acquires raw service command lines. Its
  three `Win32_Service` queries project only `Name`, `DisplayName`, `State`,
  `StartMode`, and `StartName`. PostgreSQL executable path/version remain
  explicitly `UNKNOWN` when a safe source is unavailable.
- The collector has no dynamic invocation, redirection, target file write,
  remote/session mechanism, process launch, raw command-line field, environment
  dump, credential query, or mutating command.

## Test evidence

```text
R011_WP1A_R1A_ARTIFACT_TESTS=PASS (7 passed, 0 failed, 5.59s)
R011_WP1A_R1A1_INVENTORY_SECURITY=PASS (4 passed, 0 failed, 0.24s)
R011_WP1A_R1A1_FOCUSED=PASS (31 passed, 0 failed, 9.69s)
R011_WP1A_R1A1_CRITICAL_NONREGRESSION=PASS (49 passed, 1 inherited warning, 234.13s)
R011_WP1A_R1A1_FULL_REGRESSION=PASS (174 passed, 1 inherited warning, 570.72s pytest)
FULL_PROCESS_DURATION=572.33s
FULL_PROCESS_EXIT_CODE=0
FULL_PROCESS_STDERR_BYTES=0
FULL_STDOUT_SHA256=d67ea5e70047799af0011733f6a98b7771572794d512b41cc368b6fb2078cc39
POSTGRESQL_TEST_CONTAINER_REMAINING_COUNT=0
```

## Safety boundary

```text
MACHINE_A_READ_EXECUTION_COUNT=0
MACHINE_A_MUTATION_COUNT=0
PRODUCTION_POSTGRESQL_INSTALL_COUNT=0
WINDOWS_SERVICE_MUTATION_COUNT=0
WINDOWS_FIREWALL_MUTATION_COUNT=0
REAL_MACHINE_DPAPI_OPERATION_COUNT=0
REAL_NAS_WRITE_COUNT=0
CLOUDFLARE_ACTION_COUNT=0
MACHINE_A_INVENTORY_EXECUTED=NO
WP1B_MACHINE_A_READ_AUTHORIZED=NO
MACHINE_A_MUTATION_AUTHORIZED=NO
```

Final committed Git identity, clean-clone certified artifact identity, and the
post-commit LF/CRLF cross-clone proof are recorded in the terminal handoff. No
merge or push is authorized by this checkpoint.
