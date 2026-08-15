# Stage 6 R011 Machine A Server Deployment Foundation Roadmap Freeze

Date: 2026-08-15
Branch: `stage6-r011-machine-a-server-deployment-foundation-roadmap-freeze`
Parent baseline: `3c77a29341ecb36ae2aa90c84413206b0c7adbd1`
Parent tree: `c45e571cc78e3fd474da19c611e99c390757c78f`

## Verdict

```text
VERDICT=PASS_STAGE6_R011_MACHINE_A_SERVER_DEPLOYMENT_FOUNDATION_ROADMAP_FREEZE
R011_SCOPE_FROZEN=YES
MACHINE_A_MUTATION_AUTHORIZED=NO
NEXT_ACTION=STAGE6_R011_MACHINE_A_DEPLOYMENT_FOUNDATION_IMPLEMENTATION_PLAN_REVIEW
```

This is a planning/static audit and product-definition freeze. No Machine A,
PostgreSQL production, Windows service, user, registry, firewall, NAS,
Cloudflare, public-hosting, or real-device action was performed.

## Canonical identity and static inventory

```text
BASE_HEAD=3c77a29341ecb36ae2aa90c84413206b0c7adbd1
BASE_TREE=c45e571cc78e3fd474da19c611e99c390757c78f
ORIGIN_MAIN_HEAD=3c77a29341ecb36ae2aa90c84413206b0c7adbd1
LOCAL_AHEAD=0 (pre-commit)
LOCAL_BEHIND=0 (pre-commit)
WORKTREE_CLEAN=YES (pre-commit)
SERVER_ENTRYPOINTS=apps/server/app.py:app; build_api; build_stage2_api; build_tracking_api; apps/server/files.py:build_files_api
DATABASE_CONFIG_PATHS=config/environments.py; packages/persistence/database.py; apps/server/app.py
STORAGE_CONFIG_PATHS=config/environments.py; config/paths.py; apps/server/files.py; packages/storage/*; packages/persistence/store_forward_repository.py
HEALTH_ENDPOINTS=GET /health/readiness/database; GET /api/v1/admin/storage/health
DEPLOYMENT_SCRIPT_COUNT=0
WINDOWS_SERVICE_SUPPORT_COUNT=0
PACKAGE_BUILD_SUPPORT_COUNT=0
```

The repository contains FastAPI application builders, PostgreSQL/SQLite
environment validation, the psycopg dependency, Alembic head
`0005_store_forward`, and R009 local-first store-forward storage. There is no
tracked Windows service installer/wrapper, deployment package builder,
production launcher, firewall script, or production logging contract.

## Frozen product decisions

- Machine A is the sole server authority. Desktop, Mobile Web/PWA, and future
  web hosting use the server API; clients never receive PostgreSQL or archive
  credentials/paths.
- The production process must behave as an unattended Windows service. The
  recommended implementation is an auditable service wrapper around an exact,
  isolated Python runtime and versioned entrypoint. Scheduled Task is not the
  primary production service mechanism.
- Release files are immutable and replaceable. Application data, logs, local
  ingest, PostgreSQL data, staging, rollback release, and protected secrets
  are persistent logical roots outside the release package. Drive letters and
  LAN subnets remain unknown until a later read-only Machine A inventory.
- PostgreSQL 17 is the frozen production major, based on the R010 17.11
  baseline. It is server-side only, preferably loopback-bound, with a
  least-privilege HMS QR role and no superuser runtime authority.
- Secrets use a DPAPI-backed machine/service-private store injected at service
  start. No secret is permitted in Git, source, docs, QR payloads, desktop,
  frontend, or evidence.
- Alembic is the schema authority at `0005_store_forward`. Database outage,
  migration failure, unexpected head, or invalid graph keeps the service from
  becoming healthy and never falls back to SQLite.
- R009 local-first semantics remain authoritative: local ingest is durable,
  archive/NAS is configurable and optional/offline, and real NAS remains later.
- API binding is explicit and LAN-scoped after inventory; PostgreSQL remains
  private. A local reverse proxy is recommended for LAN HTTPS termination;
  certificate issuance is later and no public Internet exposure is allowed.

## Gap matrix and gates

The machine-readable product definition records the full capability matrix for
startup, config, PostgreSQL, migrations, storage, logging, secrets, identity,
service supervision, LAN/TLS/firewall, health, outage behavior, artifact
packaging/hashes, upgrade, rollback, backup/restore, and operator runbook.

```text
MACHINE_A_GAP_MATRIX=PASS
MACHINE_A_SERVER_AUTHORITATIVE=YES
CLIENT_DIRECT_POSTGRESQL_ALLOWED=NO
CLIENT_DIRECT_ARCHIVE_STORAGE_ALLOWED=NO
MACHINE_A_UNATTENDED_SERVER_REQUIRED=YES
WINDOWS_SERVICE_PRODUCT_REQUIREMENT_FROZEN=PASS
WINDOWS_SERVICE_MECHANISM_RECOMMENDATION=AUDITABLE_SERVICE_WRAPPER_AROUND_VERSIONED_PYTHON_ENTRYPOINT
SERVICE_ACCOUNT_MODEL=DEDICATED_NON_INTERACTIVE_LEAST_PRIVILEGE_MACHINE_ACCOUNT_OR_MANAGED_SERVICE_IDENTITY_AFTER_INVENTORY
LEAST_PRIVILEGE_SERVICE_IDENTITY_POLICY=PASS
APPLICATION_RUNTIME_DATA_SEPARATION=PASS
IMMUTABLE_RELEASE_PACKAGE_MODEL=PASS
PRODUCTION_RELEASE_ARTIFACT_CONTRACT=PASS
MACHINE_A_SOURCE_DELIVERY_MODEL=CERTIFIED_IMMUTABLE_DEPLOYMENT_ARTIFACT
ISOLATED_PRODUCTION_PYTHON_RUNTIME=YES
FROZEN_POSTGRESQL_PRODUCTION_MAJOR_VERSION=17
POSTGRESQL_BIND_POLICY=LOOPBACK_OR_LOCAL_MACHINE_ONLY
POSTGRESQL_LAN_CLIENT_ACCESS=DENIED
APPLICATION_DB_SUPERUSER_ALLOWED=NO
PRODUCTION_SECRET_STORAGE_MODEL=DPAPI_BACKED_SERVICE_PRIVATE_STORE
PRODUCTION_SECRET_ROTATION_MODEL=VERSIONED_OUT_OF_BAND_ROTATION
PRODUCTION_SCHEMA_AUTHORITY=ALEMBIC
MACHINE_A_MIGRATION_FAILURE_FAIL_CLOSED=YES
MACHINE_A_LOCAL_INGEST_PERSISTENT=YES
REAL_NAS_WRITE_COUNT=0
PRODUCTION_LOGGING_CONTRACT=PASS
MACHINE_A_HEALTH_MODEL=PASS
API_BIND_ADDRESS_POLICY=EXPLICIT_CONFIGURED_LAN_ADDRESS_AFTER_INVENTORY
API_PORT_POLICY=EXPLICIT_MANIFEST_PORT_AFTER_INVENTORY
WINDOWS_FIREWALL_POLICY_FROZEN=PASS
TLS_TERMINATION_MODEL=RECOMMEND_LOCAL_REVERSE_PROXY
CERTIFICATE_PROVISIONING_SCOPE=DEFERRED_LAN_IMPLEMENTATION_TRANCHE
MACHINE_A_STARTUP_SEQUENCE_FROZEN=PASS
MACHINE_A_GRACEFUL_SHUTDOWN_REQUIREMENT=PASS
SERVICE_RESTART_POLICY_FROZEN=PASS
ATOMIC_OR_REVERSIBLE_APP_DEPLOYMENT_MODEL=PASS
APP_ROLLBACK_DB_DOWNGRADE_CONFLATION_COUNT=0
PRODUCTION_DB_ROLLBACK_POLICY_FROZEN=PASS
MACHINE_A_DB_BACKUP_PREREQUISITE_FROZEN=PASS
MACHINE_A_FIRST_DB_BOOTSTRAP_SEQUENCE=PASS
DEFAULT_PRODUCTION_ADMIN_PASSWORD_ALLOWED=NO
MACHINE_A_PREFLIGHT_CHECKLIST_FROZEN=PASS
MACHINE_A_CLOCK_SYNC_REQUIREMENT=PASS
MACHINE_A_DEPLOYMENT_EVIDENCE_CONTRACT=PASS
MACHINE_A_DEPLOYMENT_ACCEPTANCE_CONTRACT=PASS
R011_WORK_PACKAGE_SEQUENCE_FROZEN=PASS
R011_BEFORE_REAL_NAS_ACCEPTANCE=YES
R011_RISK_REGISTER=PASS
MACHINE_A_MUTATION_PRECONDITION_GATES_FROZEN=PASS
```

The nine mutation preconditions are GATE_A through GATE_I: exact canonical
main, exact artifact/hash, accepted read-only inventory, persistent roots,
service identity, secret mechanism, PostgreSQL plan, network/firewall plan,
and rollback plan. Machine A write authority may be issued only after all
gates are separately accepted.

## Scope and safety accounting

```text
R011_PRODUCT_DEFINITION_JSON_VALID=PASS
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
DATABASE_SECRET_LITERAL_COUNT=0
NAS_SECRET_LITERAL_COUNT=0
GIT_DIFF_CHECK=PASS
PRODUCTION_SOURCE_CHANGE_COUNT=0
TEST_CHANGE_COUNT=0
MIGRATION_CHANGE_COUNT=0
DEPENDENCY_CHANGE_COUNT=0
UNRELATED_CHANGE_COUNT=0
MACHINE_A_MUTATION_COUNT=0
PRODUCTION_BACKUP_EXECUTION_COUNT=0
PRODUCTION_GAP_RELABEL_COUNT=0
PRODUCTION_GAPS_REMAINING=5
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED=OPEN
MERGE_COUNT=0
PUSH_COUNT=0
```

The five remaining production gaps are preserved exactly:

```text
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

The only intended tracked paths in the roadmap commit are this checkpoint,
`docs/R011_MACHINE_A_SERVER_DEPLOYMENT_FOUNDATION_PRODUCT_DEFINITION.json`,
and `PROJECT_STATE.md`. No production source, tests, migrations, dependency
manifest, runtime configuration, or deployment implementation is changed.

R011 is complete at the freeze boundary and stops here. The next authority is
`STAGE6_R011_MACHINE_A_DEPLOYMENT_FOUNDATION_IMPLEMENTATION_PLAN_REVIEW`.
