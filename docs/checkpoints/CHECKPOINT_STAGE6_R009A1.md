# CHECKPOINT — Stage 6 R009A1 Admin Authorization Fail-Closed Remediation

Date: 2026-08-14
Branch: `stage6-r009a1-admin-auth-fail-closed`
External artifact root: `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`

## Frozen rejected base

```text
R009A1_BASE_HEAD=a2be6d3d9941aa79a2fa94677ce702ecf1c7fe7c
R009A1_BASE_TREE=1b6319076979420f7c37a8e44745fc240c88ea36
R009A_REVIEW_VERDICT=REJECT_STAGE6_R009A_ADMIN_AUTHORIZATION_BYPASS
ORIGIN_MAIN_HEAD=fadaeef44d6db082bc64f3e32456b24d6bd7e6b1
```

## Confirmed root cause

The rejected candidate's request guard called `load_config()` without an
argument. That call defaults to DEV and was independent of the services/app
context supplied to `build_files_api()`. A production-like API therefore
accepted `X-Storage-Admin: true` and executed `configure()`.

## Bounded remediation

- `build_files_api()` requires explicit immutable `AppConfig`.
- Global server construction resolves `SERVER_APP_CONFIG` once and injects the
  same instance into Product and Files APIs.
- Files admin authorization performs zero request-time configuration loads.
- Explicit DEV retains the development header workflow.
- STAGING/PROD require an injected `AdminAuthorizer` callable.
- Missing real authorizer returns `503` with
  `PRODUCTION_ADMIN_AUTH_NOT_CONFIGURED` before handler execution.
- Authorizer denial returns `403`; authorizer failure returns bounded `503`
  without exception, path, credential, or secret leakage.

All four R009 mutating admin routes share this boundary:

```text
POST /api/v1/admin/transfers/{file_id}/retry
POST /api/v1/admin/transfers/run-once
POST /api/v1/admin/purge
PUT  /api/v1/admin/storage/configuration
```

## Focused evidence

```text
ROOT_CAUSE_CONFIRMED=YES
REQUEST_TIME_ZERO_ARG_LOAD_CONFIG_COUNT=0
FILES_API_APP_CONFIG_EXPLICIT=PASS
FILES_API_ENVIRONMENT_AUTHORITY_STABLE=PASS
DEV_ADMIN_HEADER_ALLOWED_ONLY_IN_EXPLICIT_DEV_TEST=PASS
DEV_HEADER_STAGING_AUTH_ACCEPT_COUNT=0
DEV_HEADER_PRODUCTION_AUTH_ACCEPT_COUNT=0
PROD_MISSING_AUTH_BACKEND_FAIL_CLOSED=PASS
STAGING_MISSING_AUTH_BACKEND_FAIL_CLOSED=PASS
DENIED_ADMIN_HANDLER_EXECUTION_COUNT=0
R009_ADMIN_MUTATING_ROUTE_COUNT=4
R009_ADMIN_MUTATING_ROUTE_FAIL_OPEN_COUNT=0
R009_ADMIN_ROUTE_AUTH_BOUNDARY_AUDIT=PASS
PROD_FACTORY_DEV_HEADER_DENIED=PASS
PROD_FACTORY_CONFIGURE_CALL_COUNT=0
STAGING_FACTORY_DEV_HEADER_DENIED=PASS
STAGING_FACTORY_CONFIGURE_CALL_COUNT=0
POST_BUILD_ENV_VAR_MUTATION_AUTHORITY_OVERRIDE_COUNT=0
ZERO_ARG_DEFAULT_DEV_CANNOT_OVERRIDE_INJECTED_PROD=PASS
PROD_REAL_AUTHORIZER_SUCCESS=PASS
PROD_REAL_AUTHORIZER_DENY=PASS
CLIENT_ENVIRONMENT_SPOOF_OVERRIDE_COUNT=0
ADMIN_AUTH_ERROR_SECRET_LEAK_COUNT=0
R009A1_AUTH_FOCUSED_TESTS=10 passed, 1 inherited warning in 0.85s
R009_FOCUSED_TESTS=22 passed, 1 inherited warning in 150.71s
R009_RUNTIME_HARDENING_TESTS=23 passed, 1 inherited warning in 167.68s
FAILED_TEST_COUNT=0
NEW_R009_WARNING_COUNT=0
ALEMBIC_HEAD=0005_store_forward
NON_AUTH_STORE_FORWARD_PRODUCTION_CHANGE_COUNT=0
```

## Full and terminal evidence

Two initial default-order full attempts ended in a native Python 3.14/Windows
Qt/AnyIO access violation before pytest could return a verdict. The exact
interrupted Stage2 test passed alone, the Stage0-2 control passed `16`, and a
collect-all/exact-test control passed. A single-process full run containing all
27 test files then executed Qt-instantiating tests last and returned terminal
PASS. No product/test source was changed for this harness ordering.

```text
FULL_ATTEMPT_1=NATIVE_ABORT_NONTERMINAL
FULL_ATTEMPT_2=NATIVE_ABORT_NONTERMINAL
INTERRUPTED_TEST_CONTROL=1 passed, 1 inherited warning in 7.37s
STAGE0_2_CONTROL=16 passed, 1 inherited warning in 20.08s
FULL_COLLECTION_CONTROL=1 passed, 84 deselected, 1 inherited warning in 5.90s
FULL_REGRESSION=85 passed, 1 inherited warning in 301.26s
FAILED_TEST_COUNT=0
NEW_R009_WARNING_COUNT=0
VERDICT=PASS_STAGE6_R009A1_ADMIN_AUTHORIZATION_FAIL_CLOSED_REMEDIATION_CANDIDATE
```

Final static/isolation identities are recorded after their terminal runs and
the single descendant commit. No merge, push, NAS write, production restore,
or Excel fidelity claim is authorized.

```text
QR_CRITICAL_TESTS=5 passed, 1 deselected, 1 inherited warning in 24.98s
QR_EXACT_FIELD_COUNT=4
QR_EXACT_FOUR_FIELD_CONTRACT=PASS
ALEMBIC_HEAD=0005_store_forward
TEST_ISOLATION_PASS=PASS
PRODUCTION_ROOT_TEST_ARTIFACT_COUNT=0
SECRET_SCAN=PASS
SECRET_LITERAL_MATCH_COUNT=0
GIT_DIFF_CHECK=PASS
CHANGED_PATH_COUNT=7
UNRELATED_CHANGE_COUNT=0
NON_AUTH_STORE_FORWARD_PRODUCTION_CHANGE_COUNT=0
PRODUCTION_GAP_RELABEL_COUNT=0
REAL_NAS_WRITE_COUNT=0
PRODUCTION_RESTORE_COUNT=0
EXACT_EXCEL_FIDELITY_CLAIM_COUNT=0
```

## Production gaps preserved

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```
