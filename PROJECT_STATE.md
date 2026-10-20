# HMS QR Product Manager — Current State

Current Stage: STAGE_6_MACHINE_A_SERVER_DEPLOYMENT_FOUNDATION
Current WP: Engine cutover complete; mobile web app extracted for Vercel deployment
Current Revision: ADR-015 engine cutover (SQLAlchemy/Alembic/PostgreSQL removed)
Current Branch: main
Current Verdict: BROWSER_E2E_VERIFIED_16OF16_JOURNEY_ZERO_JS_ERRORS_757_PASSED_D2_FLAKE_ONLY_VERCEL_SETUP_PENDING_LO

R011 D2 remediation, two fresh independent committed-byte reviews, canonical
fast-forward integration, post-integration runtime-fixture reconciliation,
targeted verification, closure review, normal remote push, and remote readback
are complete. The immutable delivered implementation anchor is commit
`b492719343405ee7fdb224f2e1001ef96ded4ebb`, tree
`6036d8d51cd04c1e928f4a94ee37e39bdf5560b2`. The immutable D2 closure evidence
index SHA-256 is
`107e7fc886b3f143de59dbd34c4bb2d10b2962e6f629f3a22cf45a501a825bd8`.

```text
D2_IMPLEMENTATION_ANCHOR=b492719343405ee7fdb224f2e1001ef96ded4ebb
D2_IMPLEMENTATION_ANCHOR_TREE=6036d8d51cd04c1e928f4a94ee37e39bdf5560b2
D2_IMPLEMENTATION_STATUS=REMOTE_DELIVERED_AND_VERIFIED
CURRENT_CANONICAL_HEAD=READ_FROM_APPROVED_MAIN_AT_GATE_EXECUTION
CURRENT_CANONICAL_TREE=READ_FROM_APPROVED_MAIN_AT_GATE_EXECUTION
CURRENT_CANONICAL_REQUIREMENT=APPROVED_DESCENDANT_OF_D2_IMPLEMENTATION_ANCHOR
```

Canonical `main` is intentionally evolving. Gate C must read its exact commit
and tree at execution time, prove that the D2 anchor is its ancestor, prove that
the fresh Gate C authority explicitly approves that exact descendant, and read
the protected D2 Git blobs from that commit. Descendant status alone is not
approval and does not authorize implementation drift.

Gate C identity closure uses one mandatory four-blob contract:

```text
PROTECTED_D2_BLOB_COUNT=4
PROTECTED_D2_BLOB_READBACK_REQUIRED=4_OF_4
D2_BLOB_1_MATCH=MANDATORY
D2_BLOB_2_MATCH=MANDATORY
D2_BLOB_3_MATCH=MANDATORY
D2_TEST_BLOB_MATCH=MANDATORY
OMISSION_ALLOWED=NO
ANY_MISSING_BLOB=BLOCKED_D2_IMPLEMENTATION_IDENTITY_DRIFT
ANY_MISMATCH=BLOCKED_D2_IMPLEMENTATION_IDENTITY_DRIFT
```

The four protected committed paths and SHA-256 identities are:

```text
packages/deployment/os_trusted_one_shot.py=7e8ec5125723981fef84b520a3698ba91871d857b260b7e894d267555312a50f
scripts/r011_d2_protected_payload.ps1=9a499a48573f57b8cca0a63cb5b3043c7d940c42c160debfae87251db61a7e53
scripts/r011_d2_stage0.ps1=766cd212793056aab413d1f425a1adb696d39001e5ef0863685c37ee82b98c27
tests/stage6/test_r011_d2_os_trusted_one_shot.py=edb053532691a0bf5948f6aedba365397e00ef4b792f67cda501f1850803f406
```

Delivered D2 gates are `82/82` targeted, `32/32` trust-and-terminal, `1/1`
D2.31 exact, and `2/2` immutable provisioner compatibility. All previous D2
blockers are closed, no new independent trust boundary was discovered, no code
regression was confirmed, and no R011 D2 blocker remains open.

R011-WP1A source preparation and D2 trusted one-shot delivery close roadmap
mutation gates A (canonical Git identity) and B (exact artifact/tooling byte
identity). The single next Machine A gate is frozen as:

```text
R011_GATE_C_MACHINE_A_READ_ONLY_CURRENT_STATE_INVENTORY_AND_D2_PREFLIGHT
```

Gate C refreshes and reconciles current Machine A facts before any D2
production execution or further mutation. Its source-side preflight requires an
approved canonical descendant of the D2 anchor plus exact committed-byte
readback of all four protected D2 blobs, including the mandatory test blob. It
requires local
execution on Machine A under a standard token, no remoting, no network
dependency, no UAC, metadata-only production-root reads, and zero production
mutation. Gate C has not been executed and is not authorized by this
reconciliation; a fresh, gate-specific authority naming the execution-time
canonical commit and tree is mandatory.

Recovery-A evidence records four historical, safe foundation mutations on
Machine A: creation of the hardened empty `D:\HMS-QR-PROD` root, creation of
disabled account `HMS-PC\HMSQRService`, assignment of the root owner to
`BUILTIN\Administrators`, and application of the protected explicit root DACL.
The evidence-bound snapshot reports root child count `0`, service SID
`S-1-5-21-170807328-2858633000-3406472961-1009`, no local-group membership,
and no installed-service reference. Those are historical Recovery-A facts, not
fresh live verification. They must be preserved and reconciled by Gate C.

```text
MACHINE_A_EXECUTION_NOT_YET_AUTHORIZED
PRODUCTION_MUTATION_NOT_YET_AUTHORIZED
MACHINE_A_ACCESS_DURING_THIS_RECONCILIATION=0
PRODUCTION_ROOT_ACCESS_DURING_THIS_RECONCILIATION=0
REAL_UAC_INVOCATION_DURING_THIS_RECONCILIATION=0
```

Historical R011 and R011 D2 FAIL/BLOCKED checkpoints remain immutable
point-in-time evidence. They are not relabelled or overwritten by this current
state summary. See
`docs/checkpoints/CHECKPOINT_STAGE6_R011_D2_POST_REMOTE_DELIVERY_STATE_RECONCILIATION.md`.

Stage progress: Stage 0 PASS; Stage 1 PASS; Stage 2 PASS; Stage 3 PASS; Stage 4
PASS; Stage 5 PASS and remotely delivered; Stage 6 R008, R009, R010, the R011
roadmap, R011-WP1A, and R011 D2 are remotely delivered. Machine A production
qualification and deployment remain open external gates.

Design system: canonical light industrial tokens in `apps/design_tokens.py`. Penpot is the intended canonical visual design authority and UICanvas is the intended local rapid-prototype canvas. Open Design 0.19.0 remains optional historical tooling only; its paid AMR generation run is retired and is not retried.
Desktop redesign: shared PySide6 token theme applied to Product Master and Tracking.
Mobile redesign: existing operational flow retained with semantic CSS token layers,
focus states, and 44px touch-safe controls.
Visual evidence: Penpot exports plus external desktop captures at 1280x720 and
1920x1080; mobile runtime was checked at 360/390/414/768 with no horizontal
overflow and no browser console errors.

Known gaps:

```text
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

Production PostgreSQL integration is closed by R010 and then removed entirely by
ADR-015 (2026-10-18): the embedded SQL engine `packages/sqlengine` is now the
only persistence path, `requirements.txt` and `pyproject.toml` declare no
third-party runtime dependencies, the ORM model modules and the Alembic
machinery are deleted, and the Server Tool one-click setup creates a local
SQLite database file and applies the seven engine migrations in-process.
Machine A production deployment remains a separate open gap.

The engine cutover initially left the working tree at 696 passed / 7 failed /
19 errors, where every failure and error was the R011-WP1A D2 gate refusing two
legitimately changed pinned blobs (`packages/deployment/artifact.py` and
`plans.py`, whose `expected_alembic_head` fields became
`expected_engine_migration_head`). With LO's approval the frozen bundle was
re-blessed: four pinned values in
`packages/deployment/os_trusted_one_shot.py` changed and nothing else - the two
`TRUSTED_BUNDLE_FILES` entries, `TRUSTED_BUNDLE_SHA256`, and
`TRUST_MANIFEST_SHA256`. The working tree now stands at **720 passed / 2 failed**
in 946.11s, where both failures are the documented private-embeddable
`python.exe` subprocess load flake (`0xC0000135 STATUS_DLL_NOT_FOUND` under disk
load); each passes when run alone, and the failing test varies between runs. The
28 historical skips are gone because the isolated-PostgreSQL-runtime skip
conditions no longer apply.

`apps/server/portal.py`, the last raw-`sqlite3` consumer, was migrated onto the
engine in the same tranche. Its joins are resolved in Python rather than in one
joined statement, because the engine's join merges rows by column name and would
overwrite `quantity`/`notes`/`status` with the joined table's values; the
coalesce, case-when and `||` expressions the old SQL used are likewise rebuilt
in Python. `tests/stage6/test_portal_engine_reads.py` pins that behaviour.

The next exact action requires fresh authority for
`R011_GATE_C_MACHINE_A_READ_ONLY_CURRENT_STATE_INVENTORY_AND_D2_PREFLIGHT`.

Latest authority: R011 D2 post-remote-delivery project-state/roadmap reconciliation and next Machine A gate selection (external task attachment)
Latest checkpoint: docs/checkpoints/CHECKPOINT_STAGE6_R011_D2_POST_REMOTE_DELIVERY_STATE_RECONCILIATION.md
Test workspace: F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST

R007B4 toolchain migration evidence:

```text
PENPOT_MCP_SERVER=NOT_RUNNING
PENPOT_MCP_PLUGIN_CONNECTED=NOT_VERIFIED
PENPOT_MCP_READ_TEST=NOT_RUN
PENPOT_MCP_WRITE_TEST=NOT_RUN
UICANVAS_LOCAL_INSTALL=PASS
UICANVAS_LOCAL_SERVER=BLOCKED_UPSTREAM_WINDOWS_RUNTIME
UICANVAS_MCP_REAL_TOOL_TEST=NOT_RUN
```

See `docs/design/PENPOT_INTEGRATION.md` and
`docs/design/UICANVAS_INTEGRATION.md` for source identities, boundaries, and
the exact next recovery gates.

R007B5 recovery evidence:

```text
UICANVAS_NODE24_EXIT_CODE=0
UICANVAS_NODE24_PORT3200=FALSE
UICANVAS_NODE22_VERSION=v22.23.2
UICANVAS_NODE22_EXIT_CODE=0
UICANVAS_NODE22_PORT3200=FALSE
PENPOT_NPM_PACKAGE=@penpot/mcp@2.15.4
PENPOT_NPM_INSTALL=BLOCKED_PNPM_IGNORED_BUILDS_esbuild_sharp
PENPOT_MCP_PROCESS=NOT_STARTED
PENPOT_PLUGIN_SERVER=NOT_STARTED
```

The official UICanvas checkout behaves identically under Node 24 and the
portable official Node 22 control, so the Node-version hypothesis is rejected.
The official Penpot npm fast-path resolves correctly but its pnpm bootstrap
stops before server startup because native build scripts are refused by the
host policy. No config mutation or PASS claim was made.

R007B6 source-sparse recovery evidence:

```text
PENPOT_RELEASE=2.17.0
PENPOT_SOURCE_COMMIT=bdce5817ea86d028db29113d9ecdadcf07097b36
PENPOT_SOURCE_TREE=936b5cfa08005172d7caff9ff754897afcf6dbf1
PENPOT_SOURCE_PATH=F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\tools\penpot-2.17.0-r007b6\mcp
PENPOT_BUILD_POLICY=allowBuilds esbuild=true sharp=false
PENPOT_DEPENDENCY_INSTALL=PASS
PENPOT_BUILD=PASS
PENPOT_PLUGIN_SERVER=PASS
PENPOT_MCP_PROCESS=PASS
PENPOT_PLUGIN_MANIFEST_HTTP=200
PENPOT_MCP_ENDPOINT=http://localhost:4401/mcp
PENPOT_PLUGIN_CONNECTED=WAITING_STANDARD_PENPOT_FREE_LOGIN
PENPOT_MCP_READ_TEST=NOT_RUN
PENPOT_MCP_WRITE_TEST=NOT_RUN
PENPOT_MCP_READBACK=NOT_RUN
UICANVAS_EXTENSION_HOST=VS_CODE
UICANVAS_EXTENSION_ACTIVATION=PARTIAL_FIREWALL_PROMPT
UICANVAS_STATUS=OPTIONAL_TOOLING_BLOCKER_NON_PRODUCT
```

Penpot's free web UI is at the standard login screen; authentication was not
automated. UICanvas's existing VS Code host opened the extension view, but a
Windows Defender Firewall prompt blocked confirmation of its dynamic HTTP
listener. No security prompt was automated or changed.

R007B7C dual-identity recovery and HMS QR canonical design evidence:

```text
PENPOT_MODE=OFFICIAL_REMOTE_MCP
PENPOT_STAGE72_MCP_RECOGNIZED=PASS
PENPOT_HMS_QR_MCP_RECOGNIZED=PASS
PENPOT_STAGE72_TOOL_COUNT=4
PENPOT_HMS_QR_TOOL_COUNT=4
PENPOT_TWO_PROJECT_PARALLEL_ISOLATION=PASS
PENPOT_HMS_QR_READ_TEST=PASS
PENPOT_HMS_QR_WRITE_TEST=PASS
PENPOT_HMS_QR_READBACK=PASS
PENPOT_DUAL_PROJECT_PARALLEL_GATE=PASS
PENPOT_ARTIFACT_A=PASS
PENPOT_ARTIFACT_B=PASS
PENPOT_ARTIFACT_C=PASS
PENPOT_ARTIFACT_D=PASS
PENPOT_ARTIFACT_E=PASS
PENPOT_ARTIFACT_F=PASS
PENPOT_ARTIFACT_G=PASS
PENPOT_TOKEN_IN_REPOSITORY=NO
```

The protected Stage72 file was read before and after the HMS QR disposable
write and remained unchanged. The runtime UI received bounded token alignment:
Tracking now applies the shared PySide6 theme and Mobile layers semantic CSS
variables/touch-safe controls over the existing workflow markup. No domain,
API, or QR contract was changed. Fresh Alembic smoke passed and the full suite
returned `40 passed, 1 warning` in 85.70s; test isolation, secret scan, and
diff check pass. The candidate is ready for review and remains unmerged.

R007B7D canonical visual direction override:

```text
CANONICAL_THEME=LIGHT
DESKTOP_LIGHT_THEME_REVIEW=PASS
MOBILE_LIGHT_THEME_REVIEW=PASS
PENPOT_LIGHT_ARTIFACT_REFRESH=PASS
```

The user superseded dark-mode-first wording. Semantic tokens, PySide6 theme,
Web CSS variables, Penpot Design System, and A–G artifacts now use the light
industrial direction. Desktop and Mobile light-theme reviews have passed using
fresh runtime captures and responsive browser checks.

R007C independent review and local integration:

```text
R007C_CANDIDATE_COMMIT=70baf17
R007C_CANDIDATE_REVIEW=PASS_STAGE5_R007C_INDEPENDENT_UI_FUNCTIONAL_REVIEW
CURRENT_BRANCH=main
MAIN_PRE_INTEGRATION_HEAD=b75e994
STAGE5_FINAL_MAIN_HEAD=70baf17
STAGE5_FINAL_MAIN_TREE=753492c9b452e4cca771a964bccdf79e02b8261b
UNRELATED_CHANGE_COUNT=0
BUSINESS_LOGIC_UNINTENDED_CHANGE_COUNT=0
LIGHT_THEME_CANONICAL_CONSISTENCY=PASS
DESKTOP_FUNCTIONAL_SMOKE=PASS
MOBILE_FUNCTIONAL_SMOKE=PASS
DESKTOP_VISUAL_ACCEPTANCE=PASS
MOBILE_RESPONSIVE_ACCEPTANCE=PASS
PENPOT_PARALLEL_ISOLATION_REVIEW=PASS
PENPOT_A_G_CANONICAL_SET=PASS
PENPOT_LIGHT_ARTIFACT_REVIEW=PASS
QR_LABEL_PAYLOAD_SEPARATION=PASS
PENPOT_SECRET_MATCH_COUNT=0
POST_INTEGRATION_VERIFICATION=PASS
STAGE5_LOCAL_INTEGRATION_COMPLETE_PUSH_PENDING
```

R007C used read-only Penpot inspection for the HMS QR identity and the
sanitized dual-project ledger. The protected Stage72 identity was not live at
review time, so no Stage72 write, delete, or rename was attempted; its prior
sanitized mapping remains the protection evidence. The in-app browser exposed
the current runtime viewport only; responsive acceptance combines source/CSS
review, computed light-runtime checks, and the retained bounded target-width
evidence without inventing a screenshot.

Next-stage freeze: NAS STORAGE + PRODUCT IMAGES / ATTACHMENTS + BACKUP
FOUNDATION + EXACT EXCEL TEMPLATE PREPARATION. No next-stage implementation was
started under R007C.

R008 bounded storage/backup/Excel foundation candidate:

```text
STAGE6_BRANCH=stage6-storage-images-backup-excel
STAGE6_BASE_HEAD=ee9c1f13cb20dce64996536d807d177363362a9b
STAGE6_BASE_TREE=dae464eaad32c52b0c03d51f2c8c49ae9feb45b7
FOCUSED_TESTS=12 passed
FULL_REGRESSION=52 passed, 1 inherited warning
FAILED_TEST_COUNT=0
ALEMBIC_SMOKE=PASS
ALEMBIC_HEAD=0004_managed_files
TEST_ISOLATION=PASS
QR_CONTRACT_CHANGE=NO
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
```

R008 introduces server-owned logical storage keys, local/test atomic filesystem
publication, a NAS-ready adapter boundary, SHA-256 and bounded MIME/signature
validation, managed-file metadata with PENDING/READY/FAILED/ARCHIVED state,
multiple product-image and generic attachment relations, verified backup
manifests, non-destructive restore verification, and copy-based Excel template
population. All automated runtime artifacts remain under
`F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`; no production NAS operation was
attempted and no exact workbook fidelity was claimed.

Next exact action: independent R008 candidate review on the frozen candidate.
Do not merge to `main`, push, run a real NAS write, or claim exact Excel fidelity
without separate authority and the canonical reference workbook.

R008A rejected frozen candidate `de20e462522b55ff2287c4e9f545eb288c8a3f42`
because importing the `0004` ORM models while Alembic loaded its revision graph
registered Stage6 tables into the shared metadata used by historical migration
`0001`. A physical database targeted at `0003_qc_packing_delivery` therefore
incorrectly contained `managed_files` and `product_file_relations`.

R008A1 preserves that rejected commit and applies only a descendant migration
boundary remediation. Migration `0004_managed_files` now owns standalone
Alembic DDL and has zero shared storage-ORM imports. Black-box subprocess tests
prove Stage6 tables absent at `0003`, present at head, absent after downgrade to
`0003`, and present after re-upgrade. The Stage6 focused suite passes with the
new regression (`13 passed`), and the full suite passes (`53 passed, 1 inherited
warning`). No product/storage/backup/Excel/QR/UI behavior was changed.

Next exact action: `STAGE6_R008A2_INDEPENDENT_REVIEW_OF_REMEDIATED_CANDIDATE`.
R008A1 is not integration authority. Do not merge, push, write real NAS, or
claim exact Excel fidelity.

R008A2 independently reproduced the clean Alembic revision boundary, physical
schema roundtrip, schema equivalence, storage/path/state/integrity gates,
backup/restore verification, Excel source immutability, focused tests, QR
critical tests, full regression, isolation, secret scan, and frozen candidate
identity. Verdict:

```text
PASS_STAGE6_R008A2_INDEPENDENT_REVIEW_OF_REMEDIATED_CANDIDATE
R008_REMEDIATED_CANDIDATE_APPROVED_FOR_INTEGRATION=YES
```

R008B fast-forwarded local `main` from
`ee9c1f13cb20dce64996536d807d177363362a9b` to approved candidate
`fb147944b42be85e9a33053a106e04df034c631d`. Post-integration physical Alembic
boundary checks passed; Stage6 focused returned `13 passed`; QR critical
returned `6 passed, 1 inherited warning`; isolation, secret, and diff checks
passed. No implementation/test byte changed during local integration.

Current status: `STAGE6_R008_LOCAL_INTEGRATION_COMPLETE_PUSH_PENDING`.
Next exact action: `STAGE6_R008C_REMOTE_DELIVERY_AND_R008_CLOSURE`. Do not push,
write real NAS, perform production restore, claim exact Excel fidelity, or start
another Stage6 tranche without that authority.

R009 consumes the remotely delivered R008C baseline
`fadaeef44d6db082bc64f3e32456b24d6bd7e6b1` and implements local-first upload,
versioned storage configuration, a persistent leased transfer queue,
same-target remote temp publication, size/SHA-256 verification, bounded retry,
capacity admission control, grace retention, and revalidated local-delete-last.
Managed-file `READY` remains availability; archive progress is separate.

Product image and attachment APIs, compact Desktop Product/Admin panels, and
bounded Mobile metadata/download access are included without raw path exposure.
The QR payload remains exactly the existing four business fields. R009 is a
candidate only: no merge, push, real NAS write, production restore, or exact
Excel fidelity claim is authorized.

Latest checkpoint: `docs/checkpoints/CHECKPOINT_STAGE6_R009.md`
Next exact action after terminal candidate PASS:
`STAGE6_R009A_INDEPENDENT_SAFE_STORE_FORWARD_REVIEW`.

R009A independently rejected frozen candidate `a2be6d3` because the storage
admin guard reloaded zero-argument DEV configuration at request time. A files
API built around production-like services therefore accepted the spoofable
DEV header and executed storage configuration mutation.

R009A1 preserves that rejected commit and is limited to explicit immutable
`AppConfig` injection plus a real-admin-authorizer boundary. DEV convenience
header behavior is now reachable only under explicitly injected DEV authority.
STAGING/PROD require a supplied authorizer or return deterministic fail-closed
`503` before any handler. No store-forward, file, UI, QR, backup, Excel, or
migration behavior is changed.

Latest checkpoint: `docs/checkpoints/CHECKPOINT_STAGE6_R009A1.md`
Next action after remediation candidate PASS:
`STAGE6_R009A2_INDEPENDENT_REVIEW_OF_REMEDIATED_R009_CANDIDATE`.

R009A2 independently confirmed the R009A1 authorization fix, then rejected the
frozen remediated candidate `76b39d81` because ordinary manual retry demoted
`LOCAL_GRACE_RETENTION` back to `TRANSFER_QUEUED`. A worker could consequently
reprocess already verified remote content and restart the local grace period.

R009A2A preserves both rejected commits and centralizes ordinary transfer-retry
eligibility at the repository mutation boundary. Only
`TRANSFER_FAILED_RETRYABLE` may be requeued; queued jobs are exact no-ops, and
active, permanent-failure, remote-ready, grace, purge-pending, and archived-only
states remain unchanged. The conditional update includes the state predicate,
so retry cannot race a verifier or purge worker backwards. Desktop Product and
Admin actions consume the same policy. Purge retry remains the existing
remote/checksum/grace/lease-revalidated delete-local-last workflow.

Fresh evidence: retry lifecycle `13 passed`; auth `10 passed`; R009 focused
`22 passed`; runtime hardening `23 passed`; QR critical `6 passed`; full
single-process Qt-last regression `98 passed, 1 inherited warning`. Alembic
remains `0005_store_forward`; isolation, secret, scope, and diff gates pass.
No NAS write, production restore, exact Excel fidelity claim, merge, or push
occurred.

Latest checkpoint: `docs/checkpoints/CHECKPOINT_STAGE6_R009A2A.md`
Next exact action:
`STAGE6_R009A3_INDEPENDENT_REVIEW_OF_REMEDIATED_R009_CANDIDATE`.

R009A3 independently re-proved auth fail-closed, retry lifecycle monotonicity,
store-forward integrity, UI, migration, security and the `98`-test full suite,
but rejected candidate `098e4a4` after reproducing an uncovered API contract
defect. An archive-only file whose archive backend became unavailable returned
generic plain-text HTTP `500` because Files API did not map the existing
`StorageUnavailable` exception.

R009A3A preserves that rejected candidate and changes only the Files API error
boundary. Exact `StorageUnavailable` failures now return structured HTTP `503`
with code `STORAGE_UNAVAILABLE` and a bounded Vietnamese message. The handler
does not expose exception text, roots, storage keys, credentials, backend type
or tracebacks. Local-present downloads still bypass the offline archive and
succeed; archive-only offline reads do not mutate lifecycle state, requeue a
transfer, invoke a worker or change purge state. Other unexpected and integrity
exceptions remain real `500` errors rather than being over-caught.

Fresh evidence: download contract `7 passed`; auth `10 passed`; retry lifecycle
`13 passed`; R009 focused `22 passed`; runtime hardening `23 passed`; QR
critical `6 passed`; full one-process Qt-last regression `105 passed, 1
inherited warning`. Black-box actual Files API returned `503`,
`application/json`, `STORAGE_UNAVAILABLE`, with unchanged
`ARCHIVED_REMOTE_ONLY` state. Alembic remains `0005_store_forward`; isolation,
secret, diff, scope and six-gap gates pass. No UI/storage-engine/migration byte,
NAS write, production restore, exact Excel fidelity claim, merge or push was
introduced.

Latest checkpoint: `docs/checkpoints/CHECKPOINT_STAGE6_R009A3A.md`
Next exact action:
`STAGE6_R009A4_FINAL_INDEPENDENT_REVIEW_OF_REMEDIATED_R009_CANDIDATE`.

R009A4 independently approved the fully remediated candidate
`3e0c2437d6351e0e015cbe12ee6a4de0a95bba00`, tree
`69bba5356981834b3a68501e70765f0ba4e41c4a`, for local integration. R009B
fetched and re-proved local and remote `main` at `fadaeef4`, exact candidate
identity, the complete four-commit remediation chain, and fast-forward
ancestry. Local `main` then advanced with `git merge --ff-only`; no merge commit,
squash, rebase, amend, rewrite, or push occurred.

Post-integration evidence re-proved auth fail-closed (`10 passed`), remote-
verified retry immutability (`13 passed`), archive-offline download contract
(`7 passed`), R009 focused (`22 passed`), runtime hardening and physical
Alembic boundary (`23 passed`), storage security (`12 passed`), QR critical
(`6 passed`), and the one-process Qt-last full regression (`105 passed, 1
inherited warning`). Actual Files API black-box evidence returned JSON `503`
and `STORAGE_UNAVAILABLE` from `ARCHIVED_REMOTE_ONLY` with zero state mutation;
local-present/archive-offline download returned matching file bytes. Isolation,
whole-worktree high-confidence secret, diff, single-head Alembic, scope, and
six-gap gates passed. Runtime symlink control remains unavailable without
Windows privilege; static containment remains `PASS_STATIC_CONTAINMENT`.

Current status: `STAGE6_R009_LOCAL_INTEGRATION_COMPLETE_PUSH_PENDING` and
`R009_STATUS=LOCAL_INTEGRATED_PUSH_PENDING`.

Latest checkpoint: `docs/checkpoints/CHECKPOINT_STAGE6_R009B.md`
Next exact action: `STAGE6_R009C_REMOTE_DELIVERY_AND_R009_CLOSURE`. Do not push,
write real NAS, perform production restore, claim exact Excel fidelity, or
begin R010 without that separate authority.

# 2026-10-17 Feature tranche committed on feature/server-tool-popups (b73650a)
## State
- Branch `feature/server-tool-popups` (from main at `bbeaefe`) now carries the complete feature tranche as commit `b73650a`: 112 files, +17,778/-258. Working tree clean.
- Scope: Server Tool four-popup redesign + autostart reconciliation; Desktop/Server LAN discovery, DPAPI credential memory, role-aware UI, Stage 2/file API clients, Excel formula engine/factory adapter, QR CV scanner; domain partial-row relaxation + format_quantity; migrations 0006_outsourced_company and 0007_server_accounts; offline installer layout, Dockerfile, render.yaml.
- Verification at commit time: full regression 635 passed, 28 skipped (isolated PostgreSQL runtimes not configured), 0 failed across all 48 test files; Server Tool suite 82 passed; migration head == ORM (probe zero diff).
- Housekeeping in the same commit: `.gitignore` excludes `.opencode/` (local agent working directory with node_modules).
- NOT done (requires explicit LO direction): push to remote, merge/fast-forward into main, PR. The canonical R011 D2 verdict and Gate C freeze above are unchanged by this commit.

# 2026-10-17 Standalone tranche (uncommitted) - embedded SQLite, offline jsQR, self-signed TLS
## State
- LO requirement: software must run standalone with no separately installed external software, including the database ("cả cái sql cũng tự viết lại"); confirmed interpretation: drop the PostgreSQL hard requirement and use SQLite embedded in the Python runtime (sqlite3 stdlib - nothing to install).
- SQLite LAN concurrency: every SQLite engine now enables WAL journal mode, busy_timeout 30s, and synchronous=NORMAL (packages/persistence/database.py connect-event pragmas + driver timeout). Readers no longer block behind the single writer; concurrent writers wait instead of failing with "database is locked".
- Standalone production mode: config/environments.py accepts absolute SQLite file URLs in STAGING/PROD (relative paths, :memory:, and empty still rejected). apps/server/tool.py 1-click setup runs 7 standalone steps: offline package check, local folders + DPAPI secrets, embedded SQLite database at D:\HMS-QR-PROD\database\hms_qr.sqlite, Alembic migrations, self-signed TLS certificate, Private firewall, Server start. PostgreSQL install/provision runs only when the database_mode secret is explicitly "postgresql". production_setup_requirements no longer demands the PostgreSQL offline installer. Backup/restore route to the standalone database file when present.
- Offline jsQR: the mobile QR scanner previously loaded jsQR from cdn.jsdelivr.net (dead without Internet). The exact artifact (jsqr@1.4.0 dist, 130,594 bytes, SHA-256 32214c74ee92d37de6d88276987690d996ce757668e82ca1709dba5e0be9fcce) is bundled at apps/static/jsqr.min.js; apps/mobile/web.py and apps/static/sw.js (service-worker cache bumped to hms-qr-v2) reference the local file only. A regression test fails on any external CDN reference in shipped web assets.
- Self-signed TLS for phone cameras: getUserMedia requires a secure context, so http://LAN-IP was blocked. New apps/server/tls.py generates an RSA-2048 self-signed certificate (SAN: localhost + hostname + private LAN IPv4 addresses, 10-year validity) locally with the bundled cryptography wheel (cryptography-50.0.2, cffi-2.1.1, pycparser-3.11 added to installer/wheels; cryptography>=43.0.0 added to requirements.txt). The Server runs uvicorn with --ssl-certfile/--ssl-keyfile; packages/application/lan_transport.py lan_urlopen trusts the local certificate on https LAN URLs; discovery, admin, portal, and mobile URLs switch to https when TLS is enabled; the Server Tool has a new "BẬT HTTPS CAMERA" button and the 1-click flow creates the certificate automatically. Phones trust the certificate once through the browser warning.
- Verification: full regression on the current worktree 654 passed / 28 skipped / 0 failed (28 skips are the isolated PostgreSQL runtimes, not configured). New tests: tests/stage6/test_sqlite_lan_concurrency.py, tests/stage6/test_offline_assets.py, tests/stage6/test_lan_tls.py (includes a real HTTPS round-trip against the locally generated certificate).
- Committed 2026-10-17 as `4ef368b` on main (29 files, +1,110/-92), together with the hosting prep and the portal.py portability fix. Worktree clean; main is ahead of origin by 1 and the push awaits LO direction.

###### 2026-10-19 - The mobile page was driven in a real browser for the first time
## State
- **Every check up to now was static or server-side. The page had never been loaded in a browser.** It now has, through Chrome DevTools Protocol against a live server, and it works.
- **Page load**: `readyState=complete`, title `HMS QR — Quản lý Sản xuất & Truy vết` with the diacritics intact, and **zero JavaScript errors** after a reload with an error collector installed before anything ran.
- **The base variables resolve correctly at runtime**: `serverOrigin = "http://127.0.0.1:4321"`, `api = ".../tracking"`, `filesApi = ".../files"` - auto-detected from `location.origin`, no hardcoded host.
- **Login, both paths**: a wrong password shows `Tên đăng nhập hoặc mật khẩu không đúng.` and stores nothing; the right password hides the error, writes `hms-access-token` and `hms-account` to `localStorage`, and the account pill changes from `Đăng nhập` to `admin`.
- **The fetch wrapper attaches the token - proven at the network layer, not by reading the page's source.** An in-page spy placed *before* the wrapper sees no header and reports a false negative; the wrapper passes a `Headers` object, so `headers['Authorization']` is undefined on it. CDP `Network.requestWillBeSent` settles it: the page's own call sends `Authorization: Bearer eyJzdWIiOiJkNGNjNGM3Yi0...` and no cookie.
- **Auth actually gates**: with the token removed, `/tracking/api/v1/operators`, `/machining-types` and `/tracking-items` all return **401**, and the 401 handler opens the login form. Logging back in returns 200 with data.
- **The full operator journey, 16/16, through the API**: login, create operator, customer, product, purchase order, PO line, tracking item, **issue a QR**, **scan it back through `/tracking/api/v1/scan?payload=` and get the same item**, an unknown payload refused with 4xx rather than a 500, machining types seeded, operator preference written and read back, attempt display readable, **process report submitted and present in the history**.
- **The same scan through the UI**: typing the payload into `#qr` and clicking `#qr-resolve` sends `GET /tracking/api/v1/scan?payload=...` with the Bearer token and renders `CHI TIẾT SẢN PHẨM & ĐƠN HÀNG` plus the five-step `TIẾN TRÌNH SẢN XUẤT` (Phôi → Gia công → QC → Đóng gói → Đã giao). Zero JS errors.
- **Route layout confirmed while wiring the journey**: `/api/v1/products` lives on the **root app**, while `/api/v1/customers` and `/api/v1/purchase-orders` are mounted under **`/stage2`**. The page never calls either - it only calls `qr-catalog` and `scan-image` at the root - so this is harness knowledge, not a page defect.
- **`/api/v1/qr-catalog` is readable without a token in DEV.** It sits on the root app, which carries no auth dependency, while the tracking sub-app has `require_tracking_access`. In non-DEV `require_sqlite_legacy_endpoint` returns 501, so there is no production exposure. The page shows the catalog *before* login, so gating it would change that behaviour - flagged for LO rather than changed.
- **A QR payload is a JSON blob**, not a short code: `{"product_name":"Mặt bích A6061","custom...}`. Worth knowing before anyone prints a QR label.
- Test server and the debug Chrome were both shut down afterwards; port 4321 and CDP 9222 are free and the worktree is clean.

# 2026-10-19 - Four callers were still invoking Alembic after the cutover (ee0a2dd)
## State
- **The engine cutover left four callers still invoking Alembic.** `alembic.ini` was deleted and `migrations/versions/` was emptied, so every one of them fails with `No 'script_location' key found in configuration`:
  - **`apps/server/tool.py` Start Server button** - the worst one. It ran the upgrade command as a precondition before launching uvicorn, so on a factory machine the operator clicks Start Server, gets a preparation failure, and **the production server never comes up at all**.
  - **`Dockerfile` CMD** and **`render.yaml` startCommand** - a fresh container or a Render deploy never serves traffic.
  - **`TEST_HMS_QR_SERVER.bat`** - has been failing since the cutover.
- What each needs is the engine migrations, because that is what `require_database_schema_current` compares the applied versions against in production. `tool.py` now applies them through `_apply_engine_migrations()`, which runs the same script `Stage2Repository.create_schema()` uses; the launcher, Dockerfile and render.yaml run that script directly.
- **The tool migrates the production database, not the caller's shell database**: `production_server_environment()` pins `HMS_QR_ENV=prod` and `HMS_QR_DATABASE_URL=sqlite:///D:/HMS-QR-PROD/database/hms_qr.sqlite`. Verified by capturing the subprocess the method launches: program `py -3.14 -c`, cwd `E:\QR`, `create_schema()` present, no alembic.
- **PROD accepts a standalone absolute SQLite URL** (`config/environments.py:59`) - the engine cutover made SQLite the production backend too, so `sqlite:///D:/HMS-QR-PROD/...` is valid. The docstring at line 42 says as much.
- **The guard that should have caught this was itself blind.** It matched the literal command string, which misses the subprocess argument-list form `["py", "-3.14", "-m", "alembic", "upgrade", "head"]` the tool used. Re-introducing that call left both new tests green. It now squashes whitespace and quotes before matching (`_squash`), so every quoting style collapses to one shape.
- **The second guard was blind too**: it checked the file contained `create_schema()`, which a dead helper next to a replaced call site satisfies. It now also asserts `self._apply_engine_migrations()` appears in `tool.py`.
- Verified RED by re-introducing the list-form alembic call into `tool.py` - both tests failed - and GREEN after restoring. `TEST_HMS_QR_SERVER.bat`'s own REM comment had to be reworded, because it quoted the command string and tripped the guard.
- **The deployment doc** (`docs/POSTGRESQL_LAN_DEPLOYMENT.md`) told operators to run the upgrade command and to check `alembic heads`. Rewritten to the engine migrations, plus a note that the engine has **no downgrade support**, so a rollback means restoring a backup rather than reversing a migration.
- **Left alone deliberately**: ten tracked `_stage_*.ps1` staging scripts still reference alembic, sqlalchemy and psycopg. Nothing in the repo references them and they were last touched before the cutover; they are PostgreSQL-staging leftovers, not a runtime path. Flagged for LO rather than deleted unilaterally.
- Full suite: **757 passed / 2 failed** in 761.43s, both the documented D2 private-`python.exe` subprocess flake. D2 file alone passes 82/82 (51.39s). stage6 alone: 507 passed / 1 failed, same flake.
- Committed 2026-10-19 as `ee0a2dd` (6 files, +149/-12) and pushed: `2d3313b..ee0a2dd`. Local and remote main in sync.

# 2026-10-19 - Route guard now checks the whole fetch path; core flow verified (eead3da)
## State
- **The route guard only extracted the literal immediately after the base variable.** For `fetch(api + '/api/v1/operators/' + userId + '/preference')` it checked that `/tracking/api/v1/operators/` was a route prefix and stopped. Renaming the trailing segment - `/preference` to `/prefs`, `/history` to `/histories` - passed cleanly, which is the same silent-404 class as the base mistake the guard was written for.
- The guard now flattens the **entire** concatenation, replacing each interpolated identifier with a placeholder, and matches the result against the registered routes segment by segment. A segment drawn from a lookup table (`routes[workflowType]` -> `qc-events` / `packing-events` / `delivery-events` / `reports`) expands to one path per value the table can hold, so a typo **inside** the table is caught too rather than hidden behind a wildcard.
- Parsing the first `fetch` argument needs a small scanner, not a regex: `encodeURIComponent(q)` contains parentheses and the options object after the URL contains commas and braces. `_fetch_first_arguments` walks from the call's opening parenthesis to the first top-level comma or the matching close, tracking nesting and string state.
- Verified **RED** against three separate breaks applied together - a renamed trailing segment (`/preference` -> `/prefs`), a typo inside the lookup table (`packing-events` -> `packing-event`), and a renamed workflow suffix (`/history` -> `/histories`) - all three reported, and **GREEN** once restored.
- **The mobile app's core flow was driven end to end with real data for the first time** (16/18; the 2 misses were the harness's fault - `qr-catalog` is mounted on the root app and the harness only built the tracking sub-app, and it is covered separately). Verified: create operator -> listed; machining types seeded; issue a QR for a tracking item; **scan that QR through `/api/v1/scan?payload=...`** and get the item back with a formattable quantity; read `/api/v1/operators/{id}/preference` and `/api/v1/tracking-items/{id}/attempt-display`; **submit a process report** and find it in the history. The app's reason to exist works.
- **The service worker was audited and is correct**: `apps/static/sw.js` handles only `/static/` paths, cache-first. It does **not** cache the HTML page or any API response, so there is no stale page after a deploy and no cached API data - the two failure modes a tracking app cannot afford.
- Full suite: **754 passed / 2 failed** in 771.43s. Both failures are `test_d2_19` and `test_d2_21`, the documented private-`python.exe` subprocess flake; each passes alone (`test_d2_21` 1 passed in 57.56s) and the D2 file passes 82/82 in a second isolated run. Zero non-D2 failures.
- Committed 2026-10-19 as `eead3da` (1 file, +159/-18) and pushed: `970d14a..eead3da`. Local and remote main in sync, worktree clean.

# 2026-10-19 - LAN asset paths and mid-shift token expiry pinned by tests (f37dfe1)
## State
- **Nothing checked that the LAN server actually serves the assets the page references.** The page is served at `/tracking/mobile` but registers `/sw.js` and links `/manifest.json` at the **root**, so those absolute paths only resolve if the server mounts them there. A missing one fails silently - the QR scanner never loads, or offline support quietly never installs - with the page itself looking fine. Same class of miss as the Vercel `start_url` and the precache path, both of which shipped broken.
- Verified by hand against a live server first, then codified: **30/30 checks** - `/tracking/mobile`, `/manifest.json`, `/sw.js`, `/static/jsqr.min.js`, `/static/manifest.json`, `/static/icon-192.png`, `/static/icon-512.png`, `/static/favicon.png` all 200 with usable content types; the LAN manifest's `start_url` is `/tracking/mobile` and all three icons resolve; every path the LAN service worker precaches resolves.
- Noted, not a bug: `/static/manifest.json` is served as `application/json` rather than `application/manifest+json`, because `StaticFiles` guesses by extension. Harmless - only the service worker precaches it, and the page links the root copy, which `app.py:694` serves with the correct type explicitly.
- **Token expiry verified**: a token crafted with the server's real secret but an `exp` sixty seconds in the past is refused with **401** and `"Phiên đăng nhập đã hết hạn."` - the message the page's fetch wrapper surfaces when it clears the token and reopens the login form. A token signed with a different secret is also refused. The page's wrapper (`web/index.html`, the `window.fetch` override) handles any 401 by clearing `hms-access-token`, clearing the account, re-rendering and reopening the login modal, so the mid-shift re-login path works. The login POST itself goes through `nativeFetch`, deliberately bypassing the wrapper so a wrong password does not trigger the session-expiry toast on top of the inline error.
- **Four new tests** in `tests/stage6/test_mobile_web_deployment.py` (now 21): the server serves every absolute asset the page references; the service worker precaches only paths that resolve; the LAN manifest points at `/tracking/mobile` and its icons resolve; and a token driven past its eight-hour lifetime is refused with the expiry message. The expiry test builds a real PROD runtime over a migrated engine database and moves the module clock rather than reimplementing the token format.
- Verified **RED** by pointing the LAN manifest's `start_url` at the Vercel value `/` (2 failures, including the pre-existing file-level guard), and **GREEN** once restored.
- Full suite: **753 passed / 3 failed** in 629.13s. All three failures are `test_d2_19`, `test_d2_21`, `test_d2_22` - the documented private-`python.exe` subprocess flake. The whole D2 file passes **82/82** in isolation (46.73s). Zero non-D2 failures.
- Committed 2026-10-19 as `f37dfe1` (1 file, +100) and pushed: `84e4cc9..f37dfe1`. Local and remote main in sync, worktree clean.

# 2026-10-19 - The launcher never gave the mobile app a way to sign in (0830773)
## State
- **The mobile page requires a login, but `CHAY_WEB.bat` set neither a token-signing secret nor a bootstrap administrator.** Reproduced by running the server under the launcher's exact environment and walking the path the phone walks: `POST /admin-api/api/v1/auth/login` -> **401 "Server has no administrator account. Configure bootstrap admin credentials."**, and every `/tracking/api/v1/*` call -> **401 AUTHENTICATION_REQUIRED**. The app was unusable as shipped.
- Two independent causes, both in the launcher:
  1. `ServerAuthService.login` (`packages/application/server_auth.py:96-97`) raises `"Server authentication is not configured."` when `HMS_QR_AUTH_SECRET` is empty - **in every environment**. The production guard at `require_production_configuration` only adds a length check; it does not create the requirement. A DEV server with no secret cannot issue a token either.
  2. `bootstrap_admin` (`server_auth.py:69-79`) reads `HMS_QR_BOOTSTRAP_ADMIN_USERNAME` / `HMS_QR_BOOTSTRAP_ADMIN_PASSWORD` and raises when the username is empty. `app.py:435` only calls it at startup when the environment is **not** DEV, so a DEV server never bootstraps; the only other caller is the admin API's own login endpoint (`apps/server/admin.py:83`), which needs the credentials to succeed first. There was no way out of that loop - the API that creates accounts sits behind the login that cannot happen.
- Fixed in `CHAY_WEB.bat`: generate `HMS_QR_AUTH_SECRET` (64 chars, `secrets.token_urlsafe(48)`) into `%DATA_ROOT%uth-secret.txt` and the administrator password (22 chars) into `%DATA_ROOT%dmin-password.txt`, both once, and reuse them. Both must survive a restart: a regenerated secret invalidates every token already issued, and a regenerated password locks the operator out mid-shift. Username is `admin`. Credentials are printed once on first run; deleting either file regenerates it.
- **Why the launcher stays on DEV**: `require_sqlite_legacy_endpoint` (`apps/server/app.py:79-88`) returns **501** for `/api/v1/qr-catalog` in any non-DEV environment, and the mobile page's part picker (`openPartPicker`) depends on that route. Switching the launcher to production would trade a broken login for a broken part picker. The 501 gate predates the SQL-engine cutover and its message still says "chua ho tro PostgreSQL server"; whether that endpoint should now be ungated is an open decision for LO, not something to change silently.
- **Also noted, not changed**: `TEST_HMS_QR_SERVER.bat` still runs `py -3.14 -m alembic upgrade head`, which is dead since the engine cutover - there is no Alembic in the runtime path any more. Its DEV schema comes from `repo.create_schema()` (`app.py:317`). Left alone because that launcher is test-only and out of scope for this fix.
- **Four regression tests** in `tests/stage6/test_mobile_web_deployment.py`: the launcher supplies the secret, persists it rather than regenerating it, supplies the bootstrap credentials, and persists the password where the operator can replace it. All four verified **RED** against the previous launcher and **GREEN** after the change.
- Verified end to end under the fixed launcher's environment: page 200, login 200 with an ADMIN token, `/tracking/api/v1/operators`, `/tracking/api/v1/machining-types` and `/api/v1/qr-catalog?limit=150` all 200 with that token, `qr-catalog` returns a real `items` array, a second login still succeeds (secret is stable), and a wrong password is still refused. 10/10.
- Full suite: **749 passed / 3 failed** in 782.09s. All three failures are `test_d2_19`, `test_d2_20`, `test_d2_21` - the documented private-`python.exe` subprocess flake. The whole D2 file passes **82/82** in isolation (72.30s). Zero non-D2 failures. Mobile/tunnel/offline/assets slice: 31 passed.
- Committed 2026-10-19 as `0830773` (2 files, +98/-1) and pushed: `46329a2..0830773`. Local and remote main in sync, worktree clean.

# 2026-10-19 Regression found and fixed - mobile page called two app-root routes through /tracking (03010ae)
## State
- **Bug I introduced in the origin refactor, caught by an E2E check before LO deployed.** The refactor rewrote every fetch to go through a base variable, but `/api/v1/qr-catalog` and `/api/v1/scan-image` are mounted at the application root (`@app.get("/api/v1/qr-catalog")`, `@app.post("/api/v1/scan-image")`), NOT under `/tracking`. Prefixing them produced `/tracking/api/v1/qr-catalog` and `/tracking/api/v1/scan-image`, both **404**. The original page used absolute paths (`fetch('/api/v1/qr-catalog?limit=150')`) which happened to be correct.
- Impact: the **part picker** (`openPartPicker`) and the **scan-from-image** feature (`scanFromImage`) failed silently. The page still loaded, the fetch simply never resolved, and no existing test noticed - the failure is invisible at the HTTP level of the page itself.
- Fix: both now use `serverOrigin` (the app root) instead of `api` (`/tracking`). Verified on a live server: `GET /api/v1/qr-catalog?limit=150` -> 200 (was 404), `POST /api/v1/scan-image` -> 422 (route exists, needs a file; was 404), both carrying the correct `access-control-allow-origin`.
- Second fix in the same commit: `apps/mobile/web.py` read the page with `read_text()`, which applies universal-newline translation, so the LAN server returned 56,669 bytes of LF while Vercel serves the 58,078-byte CRLF file. Content was identical after normalisation but the two deployments were not byte-identical. It now returns the raw bytes.
- **New guard test** `test_every_api_path_the_page_calls_is_a_real_route`: walks every `fetch()` in the page, resolves it against the routes the server actually registered (recursing into the mounted sub-applications, whose paths are relative to the mount), and fails on any path that is not a route. Companion test `test_page_does_not_fetch_an_absolute_api_path` fails on an absolute `fetch('/api/...')`, which would ignore the configured origin and break the Vercel deployment. The guard was verified RED against the bug and GREEN after the fix.
- Also verified end-to-end with a static server standing in for Vercel (root = `web/`) plus the real server with CORS enabled: 22/22 checks - every asset resolves, manifest `start_url` is `/`, service worker precaches only paths that exist, CORS preflight 200 with the right allow-origin/allow-headers, 401 without a token, disallowed origin refused, `/tracking/mobile` reachable without auth and byte-identical to the file on disk.
- Committed 2026-10-19 as `03010ae` (3 files, +124/-4) and pushed: `d4db8ea..03010ae`. Local and remote main in sync, worktree clean.
- Verification: full suite **746 passed / 2 failed** in 758.94s. Both failures are `test_d2_20` and `test_d2_22`, the documented private-embeddable-`python.exe` subprocess flake - **both pass when run alone** (`test_d2_20` 1 passed in 27.34s, `test_d2_22` 1 passed in 0.48s), and the whole D2 file passes 82/82 in isolation. Zero non-D2 failures. Mobile/tunnel/offline/assets slice: 31 passed.

# 2026-10-19 Engine cutover committed and pushed (8b86526) + mobile web app on Vercel
## State
- Committed 2026-10-19 as `8b86526` on main: **107 files, +10,533/-5,767**. Working tree clean; local and remote main in sync (`32765a0..8b86526` pushed to `https://github.com/hoangminhsang989/HMS-QR-PRODUCT-MANAGER.git`).
- Scope: the engine cutover (new `packages/sqlengine/` 9 files, `migrations/engine/` 7 migrations, `config/dburl.py`, all persistence/excel/server layers rewritten, `requirements.txt` + `pyproject.toml` drop sqlalchemy/alembic/psycopg, 15 Alembic/ORM files deleted) together with the mobile web app work (new `web/` tree, `apps/mobile/web.py` rewrite, CORS + `/tracking/mobile` exemption in `apps/server/app.py`, new `apps/server/tunnel_url.py`, `CHAY_WEB.bat`, 3 new + 2 updated test files) and the D2 frozen-bundle re-bless.
- Pre-commit checks: secret scan of all 92 changed/untracked files (2 hits, both pre-existing test fixtures - `password="new-password-456"` in `test_server_admin.py:139` and `note="postgresql://user:pass@host/db"` in `test_r011_wp1a_deployment.py:185`; no real secrets). All modules import clean with `HMS_QR_TEST_ROOT` set. D2 gate **82/82**.
- **NEXT (needs LO): the one-time Vercel project setup.** `vercel` and `gh` CLIs are not installed on this machine, so the deploy step needs LO's Vercel login. Settings that matter: Root Directory = `web`, Framework Preset = `Other`, no build command, no output directory. Full instructions in `web/README.md`. Once the project exists, every push to `main` auto-deploys.
- After Vercel is live: run `CHAY_WEB.bat` on the factory machine, read `D:\HMS-QR-DATA\tunnel-url.txt`, paste it into the app's connection screen (MÁY CHỦ -> dán URL -> LƯU & KẾT NỐI), then write the Vercel hostname into `D:\HMS-QR-DATA\cors-origins.txt` and restart the server so the frontend may call the API.

# 2026-10-19 Engine cutover finished - mojibake repair, test rewrites, last consumers
## State
- Vietnamese mojibake in `apps/server/tool.py` fully repaired: 0 U+FFFD, 0 `/6` labels, 10 `/7` labels. Four repair scripts were tried; only line-number replacement with explicit indentation worked (skeleton matching matched 0 lines, and two earlier attempts silently dropped indentation). `python -c "import apps.server.tool"` verified clean. L1651 also repaired (PostgreSQL wording -> database wording).
- `tests/stage6/test_server_tool.py` rewritten for engine backups: new `_seed_engine_database()` helper using `connect(engine_dir_for(...))`; the 6 backup/restore/inventory/integrity tests now assert on `.engine` directories; imports updated (removed `sqlite3`, added `ENGINE_BACKUP_SUFFIX`, `engine_dir_for`, `from packages.sqlengine import connect`). 52 passed.
- `packages/persistence/sqlite_product_repository.py` migrated to engine: schema bootstrap via `schema.has_table()` / `has_column()` instead of `CREATE TABLE IF NOT EXISTS`; sequence row seeded read-then-insert; `next_sequence()` does read-modify-write inside `database.transaction()` because the engine's `UPDATE ... SET` only accepts literals; indexes dropped entirely (the engine has no `CREATE INDEX` and scans in Python anyway); rows are dicts, not `sqlite3.Row`. 113 passed across test_repository.py + test_api.py + test_desktop.py + test_excel.py.
- `apps/server/app.py` `/api/v1/qr-catalog` migrated: two flat SELECTs plus a Python product lookup dict. The join was not portable - `Executor._joined_rows` merges by column *name*, so `SELECT t.internal_id ... JOIN products p` returned `'p1'` (the product's id) instead of `'t1'`. Search filtering and `items = list(reversed(items))[:limit]` rebuilt in Python because the engine silently ignores `ORDER BY rowid`.
- `packages/excel/export_report.py` migrated: all stats via `database.scalar("SELECT COUNT(*) ...")`; status histogram counted in Python; activity log rebuilt from flat SELECTs plus lookup dicts for `machining_types` / `order_tracking_items` / `products`; coalesce/case-when rebuilt in Python.
- `packages/excel/factory_adapter.py` `import_factory_items_to_db()` migrated: maps `db_path` -> `engine_path()`, whole import wrapped in one `database.transaction()`, `conn.commit()` / `conn.close()` removed.
- Zero raw `sqlite3` remaining anywhere in the tree (verified by `git grep -nE 'import sqlite3|sqlite3\.'`).
- Full suite: **726 passed / 1 failed** in 558.90s. The single failure is the known flake `test_d2_19_private_runtime_ctypes_black_box`, which passes alone (1 passed in 71.14s). pytest-qt teardown crash `0x8001010d` is a harmless Windows artifact that fires after all tests pass. (Later runs in the same session showed 744/1 and 743/2 - always the same D2 subprocess flake family, always passing alone.)
- Adding `web/` and editing `apps/` does NOT affect the D2 gate: `build_deployment_bundle()` only bundles `TRUSTED_BUNDLE_FILES`, all under `packages/deployment/` + `config/paths.py`.

# 2026-10-19 Mobile web app extracted for Vercel + GitHub deployment
## State
- LO requirement: "Tận dụng .vercel.app và github để tạo web app mobile" - a phone must reach the app from anywhere on the Internet, not only inside the factory LAN.
- Architecture: static frontend on Vercel (GitHub push -> auto-deploy) + the HMS QR server stays on the factory machine (the engine is single-writer and file-based, so it cannot be sharded across serverless functions) exposed through a Cloudflare Tunnel. `CHAY_WEB.bat` already launched `cloudflared tunnel --url http://localhost:8000` as a quick tunnel.
- Gaps found before any code: the API root was hardcoded (`const api = '/tracking'`), there was zero CORS support, and the mobile UI had no login screen at all.
- Defaults chosen after LO said "tiếp tục" twice instead of answering: quick tunnel (free, no domain); API base URL is runtime-configurable so a new tunnel URL never needs a Vercel redeploy; frontend is plain static HTML/CSS/JS with no build step; lives in `web/` at the repo root.
- `web/index.html` extracted from the old `MOBILE_HTML` Python string (47,311 bytes -> 56,446 after patches, 1,210+ lines) and is now the **single source of truth**. `apps/mobile/web.py` was rewritten to just read and return it, with a 503 fallback page if the file is missing. LAN and Vercel now serve byte-identical HTML.
- API origin resolves at runtime in this order: `localStorage['hms-server-origin']` (set from the new connection screen) -> `location.origin` when the page is served by the HMS QR server itself -> empty, which forces the connection screen. All 5 hardcoded absolute fetches patched; zero `fetch('/api` / `fetch('/files` remain.
- Connection + login UI added: header pills, a connection modal (server origin input), and a login modal. An authenticated `fetch` wrapper is installed once and injects `Authorization: Bearer <token>` from `localStorage['hms-access-token']`, handling 401 by clearing the token and reopening the login form. Login endpoint is `POST {origin}/admin-api/api/v1/auth/login`; the response is **flat** (`{access_token, token_type, role, username}`), not nested under `account`. Tokens live 8 hours.
- CORS added to the server as **opt-in** via `HMS_QR_CORS_ORIGINS` (comma-separated). Empty by default, so a LAN-only deployment keeps its original same-origin behaviour. Never a wildcard. Verified: allowed origin -> 200 preflight with correct `access-control-allow-origin` / `-methods` / `-headers`; disallowed origin -> 400 with no allow-origin header.
- `/tracking/mobile` is now auth-exempt (it carries the login form; gating it would leave no way to log in). `/tracking/api/v1/*` still returns 401 without a token.
- `web/` deployment assets: `index.html`, `manifest.json`, `sw.js`, `vercel.json` (cleanUrls, immutable cache headers for `/static/(.*)`, `Service-Worker-Allowed: /`, nosniff), `static/{jsqr.min.js, favicon.png, icon-192.png, icon-512.png}`.
- Two Vercel-specific bugs found and fixed: (1) `web/manifest.json` needed `start_url: "/"` because Vercel serves `web/` at the root, while the LAN copy keeps `/tracking/mobile`; (2) `web/sw.js` precached `/static/manifest.json`, which 404s on Vercel, and `cache.addAll` aborts the entire install when one asset fails - so offline support was silently dead. The Vercel worker now precaches `/manifest.json` and caches each asset individually with `cache.add(asset).catch(...)`.
- `CHAY_WEB.bat` improved: reads optional `HMS_QR_CORS_ORIGINS` from `D:\HMS-QR-DATA\cors-origins.txt`, passes `--logfile` to cloudflared, and polls the new `apps/server/tunnel_url.py` helper to write the assigned `*.trycloudflare.com` hostname to `D:\HMS-QR-DATA\tunnel-url.txt` and print it, instead of letting it scroll past in a console window.
- New tests: `tests/stage6/test_mobile_web_deployment.py` (12 tests - page reachable unauthenticated, no hardcoded origin, API still 401, CORS off by default, CORS allows only the configured origin, login reachable cross-origin, Vercel assets exist, vercel.json cache rules, manifest start_url per root, service worker precaches only paths that exist), `tests/stage6/test_tunnel_url.py` (6 tests). `tests/stage6/test_offline_assets.py` updated to pin `web/` and the no-hardcoded-origin rule; `tests/stage6/test_files_api_ui.py` updated to read `MOBILE_PAGE_PATH` instead of the removed `MOBILE_HTML`.
- Verification: full suite **743 passed / 2 failed** in 824.78s. Both failures are `tests/stage6/test_r011_d2_os_trusted_one_shot.py` private-embeddable-`python.exe` subprocess tests (`test_d2_20`, `test_d2_21`), both exiting `3221225477` = `0xC0000005 STATUS_ACCESS_VIOLATION` under full-suite disk load. Both pass when run alone (`test_d2_20` 1 passed; `test_d2_21` 1 passed in 61.19s). This is the documented flake family `test_d2_19`-`test_d2_22`; the exact failing subset varies run to run (an earlier run in this same session showed 744 passed / 1 failed with only `test_d2_19`). Zero non-D2 failures. Mobile/tunnel/offline/assets slice: 28 passed.
- All text files normalized to CRLF to match `core.autocrlf=true`; zero U+FFFD anywhere. `web/static/jsqr.min.js` is byte-identical to the checksum-pinned `apps/static/jsqr.min.js` (130,594 bytes, SHA-256 32214c74...).
- NOT done (needs LO): commit, push to GitHub, and the one-time Vercel project setup (Root Directory must be `web`, Framework Preset `Other`, no build command). `vercel` CLI and `gh` CLI are not installed, so the deploy step needs LO's Vercel login.

# 2026-10-19 QR catalog read the wrong customer field and 500'd on a company-less product

## State
- Found while adding tracking data to test the part-picker button label: `/api/v1/qr-catalog` returned **HTTP 500** as soon as any tracking item's product had no `company`.
- Root cause 1 (the 500): the endpoint built `QrPayload(product["part_name"], product["company"], ...)` unguarded inside its loop. `company` is optional on `ProductPayload` (`company: str = Field(default="", max_length=255)`), and `QrPayloadService.encode()` raises `TrackingError("QR payload fields must be non-empty strings")` on an empty field. One bad product killed the whole endpoint - the part picker dies entirely, not just for that row.
- Root cause 2 (found while fixing it): the catalog read `products.company` while `TrackingService.qr_payload` - the endpoint that actually issues and validates QR codes - reads `customers.name` via `repo.qr_identity`. Two different values for the same field meant a payload rendered in the picker decoded to something `scan()` then reported as inconsistent (`qr_identity_consistent` false).
- Fix: the catalog now reads `customers.name` (same source as the issued QR) and wraps the payload build in `try/except TrackingError: continue`, matching the existing `if product is None: continue` pattern. An item whose identity cannot produce a scannable code is skipped rather than failing the request.
- Also fixed: the picker button carried a hardcoded "Danh Sách 76 Chi Tiết" that had nothing to do with the catalog. Added `id='part-picker-btn'`, removed the 76, and the label is now written from `data.total` after the catalog fetch (falling back to `items.length`, which the limit can cap below the total).
- Emoji escape bug fixed along the way: the label used `\U0001f50d` inside a JS string literal, which is not a JS escape - replaced with the literal `🔍` character.
- Verified against a live server: catalog returns 200 with a company-less product; the catalog's `qr_payload` matches the issued QR **exactly**; the payload carries the customer record's name; `total` equals `len(items)`; label reads "🔍 Danh Sách 1 Chi Tiết".
- Three guards added to `tests/stage6/test_mobile_web_deployment.py`, each verified RED by re-introducing its defect:
  - `test_the_catalog_reads_the_customer_name_from_the_customer_record`
  - `test_a_product_without_a_company_cannot_take_the_catalog_down` - checked **structurally with `ast`**, not by substring. A substring check for `except TrackingError` is satisfied by an orphaned except clause that no longer guards anything, which is exactly what a careless edit leaves behind (this was caught during verification: the first version of the guard passed against a syntactically broken file).
  - `test_the_catalog_button_does_not_advertise_a_made_up_count`
- Full suite: **759 passed / 3 failed** in 1251.52s. All three failures are the known D2 private-embeddable `python.exe` flake (`test_d2_19`, `test_d2_21`, `test_d2_22`); the D2 file alone passes 82/82.
- stage6 also produced a one-off failure of `test_semantic_identity_documents_timestamp_exclusion` that did not reproduce on re-run and passes alone and with its whole file - a load flake, not a regression.
- Committed and pushed as `ed4d9d1`.

## Next
- Wait for LO to complete the one-time Vercel setup (Root Directory `web`, Framework Preset `Other`, no build command), then verify CORS and the manifest against the live Vercel URL.
- On the factory machine: run `CHAY_WEB.bat`, read `D:\HMS-QR-DATA\tunnel-url.txt`, paste into the app's connection screen, write the Vercel hostname to `D:\HMS-QR-DATA\cors-origins.txt`, restart the server.

# 2026-10-19 Endpoint audit after the catalog fix - partial products and scan-image

## State
- Audited every endpoint the mobile page calls, looking for the same class of defect as the QR catalog 500 (an endpoint failing on a data shape the contract allows).
- The page calls 16 fetches across 9 distinct routes: `/api/v1/operators` (GET/POST), `/api/v1/operators/{id}`, `/api/v1/machining-types`, `/api/v1/scan?payload=`, `/api/v1/tracking-items` (POST/GET), `/api/v1/process-reports`, `/api/v1/qr-catalog`, `/api/v1/scan-image`, `/files/api/v1/products/{id}`. No absolute fetches remain.
- **`/api/v1/scan-image` verified end to end** (no code change needed): issued a QR, rendered it as a real PNG, POSTed it as multipart, and the endpoint decoded it back to the exact issued payload. That payload then resolved through `/tracking/api/v1/scan` with `qr_identity_consistent: true`. A blank white PNG returns **422 with a Vietnamese message**, not 500. OpenCV 4.13.0 is installed and the 5-stage enhancement pipeline runs.
- **Every `QrPayload` construction site audited** - only three exist in production: the catalog (now fixed), `TrackingService.qr_payload_data` (reads `customers.name`), and `QrPayloadService.decode`. The QR surface is now consistent.
- **Partial products are intentional, and the 422 is correct.** `ProductPayload.part_name` has `max_length=255` but no `min_length`, while `unit` and `product_code` are both required - and `test_domain.py:18-19` plus `test_api.py:53` both assert a blank name is accepted. That is a product arriving from an import before its name is known. A null `product_code` is auto-generated by the server, so a product is always identifiable.
- Downstream consequence, verified against a live server: issuing a QR for a tracking item of a blank-named product returns **422 `TRACKING_VALIDATION_ERROR`** - a clean validation failure, not a 500, and not a silently issued QR that decodes to a blank name. The recovery path is `PATCH /api/v1/products/{id}` to complete the name, after which the QR issues normally. That whole path is now covered by a test.
- New test `test_a_partial_product_cannot_issue_a_qr_but_never_breaks_the_catalog` builds a full app on an isolated engine database and walks: blank-named product accepted -> QR issue 422 -> PATCH completes the name -> QR issue 200 with the right payload. Verified RED by adding `min_length=1` to `part_name`, which would break the import flow's partial-product design.
- Gotcha found while writing it: `/api/v1/qr-catalog` and `/api/v1/scan-image` are registered on the **module-level `app`** (`@app.get`), not inside `build_api` (`@api.get`). An app built by `build_api` therefore 404s on them, and their handlers close over the module-level `SERVER_DATABASE_RUNTIME`, so they cannot be reused against an isolated database. That is why the catalog side of this behaviour is covered by the structural guards and the live-server check rather than by an isolated-app test.
- Full suite: **762 passed / 1 failed** in 874.52s - the known D2 flake (`test_d2_19`); the D2 file alone passes 82/82.
- Committed and pushed as `7466ab3`.

## Next
- Wait for LO to complete the one-time Vercel setup (Root Directory `web`, Framework Preset `Other`, no build command), then verify CORS and the manifest against the live Vercel URL.
- On the factory machine: run `CHAY_WEB.bat`, read `D:\HMS-QR-DATA\tunnel-url.txt`, paste into the app's connection screen, write the Vercel hostname to `D:\HMS-QR-DATA\cors-origins.txt`, restart the server.
# 2026-10-19 Vercel deploy verified live + CORS origin-list bug fixed
## State
- **The Vercel deployment is live and correct.** LO deployed `https://hms-qr-product-manager-ga5o69ff9-hms-98.vercel.app/`. It first answered with Vercel SSO (Deployment Protection / Vercel Authentication was on, redirecting to `vercel.com/login?next=/sso-api?url=...`); after LO turned protection off the same URL serves the app. **24/24 checks pass**: page is `text/html` with the login form and connection screen, no hardcoded API origin, runtime-origin read present, `manifest.json` is `application/json` with `start_url`/`scope` = `/` and `display: standalone`, all three manifest icons resolve, `sw.js` is JavaScript with `Service-Worker-Allowed: /` and is not cached long, `jsqr.min.js` is cached immutably, `nosniff` is set, all 5 root-relative references resolve, no LAN-only path is referenced, and `jsqr.min.js` is **byte-identical** to the LAN copy. Root Directory was therefore `web` as required.
- No production alias exists yet: `hms-qr-product-manager.vercel.app`, `hms-qr-product-manager-hms-98.vercel.app`, `hms-qr-product-manager-hms98.vercel.app`, `hms-qr-product-manager-hms-98s-projects.vercel.app` and `hms-qr-product-manager-git-main-hms-98.vercel.app` all return 404. The working URL is a deployment-specific one (it carries the hash `ga5o69ff9`), so it survives as long as that deployment does but changes on redeploy. LO should read the assigned production domain off Settings -> Domains.
- **Bug found and fixed: the launcher kept only the last CORS origin.** `CHAY_WEB.bat` read `cors-origins.txt` with a bare `set` inside the `for /f` loop, so every line overwrote the previous one and only the final line survived - while the comment directly above it promised "one per line or comma-separated", which is exactly how anyone would write that file. Reproduced with a two-line file: input two origins, output one. Adding a second frontend (the production domain, once assigned) would therefore have silently locked the first out with a CORS error naming no cause. The loop now appends under `setlocal EnableDelayedExpansion`, and blank lines are skipped.
- **Second half of the same bug:** `cors_origins_from_environment` split on commas only, so even a correctly accumulated multi-line value would arrive as a single entry containing an embedded newline - matching no origin at all. It now splits on commas and newlines alike (`re.split(r"[,\r\n]", raw)`), which also makes CRLF files and stray padding harmless. `re` was added to the `apps/server/app.py` imports.
- Batch fix verified across five shapes: two origins one per line, three origins, a single origin, blank lines mixed in (skipped), and one comma-separated line. Python fix verified across ten shapes including empty, whitespace-only, CRLF, mixed separators, trailing comma and padding.
- Two guards added to `tests/stage6/test_mobile_web_deployment.py`, **each verified RED by reverting its half**: `test_cors_origins_split_on_newlines_as_well_as_commas` and `test_the_launcher_keeps_every_origin_line`. The launcher guard looks for the delayed-expansion append (`!HMS_QR_CORS_ORIGINS!`) rather than the assignment, for the same reason the catalog guard uses `ast` - a substring check is satisfied by code that no longer does the job.
- Full suite: **762 passed / 3 failed** in 870.20s. The three are the known D2 private-embeddable `python.exe` flake (`test_d2_19`, `test_d2_21`, `test_d2_22`); `test_d2_21` passes alone in 0.65s and 13.13s. The D2 gate pins only `packages/deployment/` + `config/paths.py`, so this change cannot affect it.
- Committed and pushed as `535ca04`.
## Next
- LO: read the production domain off Vercel Settings -> Domains and send it, so it can be verified and written into `cors-origins.txt`. Note that pushing to GitHub makes Vercel build a **new** deployment with a new hash URL, so the URL LO has will keep working but will no longer be the newest build.
- On the factory machine: run `CHAY_WEB.bat`, read `D:\HMS-QR-DATA\tunnel-url.txt`, paste into the app's connection screen, write the Vercel hostname(s) to `D:\HMS-QR-DATA\cors-origins.txt` (one per line is now safe), restart the server.
# 2026-10-20 The catalog listed QRs that could not scan
## State
- **Bug found while driving the real part-picker flow in a browser.** The picker opened, listed the seeded part, the button label read the server's real total, and picking the part filled the QR field - but the scan never resolved the product card. Chasing that led to a genuine defect, not a test artifact.
- **The catalog listed every tracking item; `scan_by_tracking_code` accepts only `qr_status = ACTIVE`.** `qr_catalog` (`app.py:622`) queried `order_tracking_items` with no filter and rendered a `qr_data_uri` for each row, while `scan_by_tracking_code` (`tracking_repository.py:135`) requires `qr_status = ?` with `QRStatus.ACTIVE`. So an item whose QR was never issued - or was revoked - appeared in the picker looking scannable, and its own payload then answered **404 `TRACKING_NOT_FOUND` "QR not found or revoked"**. The payload decodes cleanly; the server simply refuses it. Dead end for the operator.
- **The mobile page never issues a QR.** Grepping the whole repo, `issue_qr` is called only from `POST /tracking/api/v1/tracking-items/{id}/qr`, from `atomic_new_order`, and from tests. The page's 18 fetches contain no call to it. So in the mobile flow nothing ever set `qr_status`, and the picker offered dead codes by default.
- **This is the same class as the catalog reading `products.company`**: the picker disagreed with what the QR surface would actually accept. The existing comment already states the principle - an item that cannot produce a scannable QR does not belong in a picker whose job is handing out scannable codes - and an un-issued QR is exactly that.
- Fix: the catalog query now carries `WHERE qr_status = ?` with `QRStatus.ACTIVE.value`. Nothing is hidden - the item still exists, still appears in `GET /tracking/api/v1/tracking-items`, and appears in the catalog the moment its QR is issued.
- Verified both directions against a live server: before, a freshly created item was listed and its own catalog payload scanned 404; after, only the issued item is listed, every listed item scans 200, issuing the hidden item makes it appear, and it was never deleted. 7/7.
- Guard `test_the_catalog_only_lists_qrs_that_actually_scan` checks the WHERE clause **structurally with `ast`** - it finds the `database.query` call whose SQL selects `product_id, customer_id` from `order_tracking_items` and asserts `WHERE QR_STATUS` is present. A substring test would pass on a comment that merely mentions ACTIVE. Verified RED by removing the clause.
- Full suite: **764 passed / 2 failed** in 467.79s. Both failures are the known D2 private-runtime `python.exe` flake (`test_d2_19`, `test_d2_20`); the D2 file alone is 81 passed with only `test_d2_20` failing, and `test_d2_20` passes alone in 53.85s and 4.86s.
- Committed and pushed as `762dd99`.
## Next
- **LO must decide the picker's behaviour now that it is honest.** With the filter in place the picker shows only items whose QR was issued. If nothing in the factory has been issued yet, the picker will be empty - which is truthful but may not be what the operators need. Two ways forward, LO's call:
  - **(a) leave it** - operators get QRs issued elsewhere (portal / import) and the picker browses those.
  - **(b) have the page issue the QR when a part is picked** - `selectPartFromList` calls `POST /tracking/api/v1/tracking-items/{id}/qr` (the catalog already returns `internal_id`) and uses the returned payload. The picker then becomes "activate a part for work", the GET stays side-effect free, and the issue is recorded as a `QR_ISSUED` history event.
- Still outstanding from before: the production domain off Vercel Settings -> Domains, then the factory-machine steps (`cors-origins.txt`, `CHAY_WEB.bat`, `tunnel-url.txt`).
# 2026-10-20 The picker now activates a part instead of only browsing labelled ones
## State
- **Follow-up to `762dd99`, which was the wrong fix.** That commit filtered the catalog to `qr_status = ACTIVE`, which made the picker honest but useless: **nothing in this repository ever issues a QR.** Grepping every client - the desktop tracking window only *displays* `qr_status` (`tracking_window.py:137`), and the mobile page's 18 fetches contain no call to `POST .../qr`. So in the mobile flow no item ever became ACTIVE, and the picker would have been permanently empty for any operator who had not been handed a code some other way.
- **The picker exists precisely so an operator can work on a part that has no physical label yet** - it is one of four ways to get a code into the QR field (camera scan, image upload, three samples, picker). Filtering it to already-labelled parts removes the only path that needs no printed label.
- **Fix (`bb26bf9`)**: the catalog lists every item again and reports `qr_status`; `selectPartFromList` is now `async` and calls `POST /tracking/api/v1/tracking-items/{id}/qr` when the item is not ACTIVE, using the payload the server returns (authoritative - the catalog's own `qr_data_uri` is only a preview). An already-ACTIVE item writes nothing: `issue_qr` reuses the existing public id but appends a duplicate `QR_ISSUED` history row, and a code already printed on a label must not be disturbed.
- Verified against a live server, **14/14**: catalog lists both items with status; picking the un-issued one issues a QR whose payload scans 200 and resolves to that part; picking the ACTIVE one adds no history row and its catalog payload scans as-is; re-issuing returns the same payload and the original code still scans.
- Verified in a real Chrome with the page on a different origin than the API, **10/10**: login, picker lists both parts, button label carries the real total, picking the un-issued part issues its QR and fills the field with a payload the server accepts, picking the ACTIVE part makes no issue call.
- **The browser run caught a defect this commit would otherwise have shipped**: `selectPartFromList` was not `async`, so the new `await` was a syntax error - and the browser discards an **entire `<script>` block** on one. The page rendered normally while `submitLogin`, `openPartPicker` and every other function were `undefined`. Nothing in the suite noticed, because the guards read the page as text and a broken script is still valid text.
- New guard `test_the_pages_inline_script_actually_parses` runs `node --check` on the inline block. Verified RED against exactly that defect. This is the guard class that was missing: every other page guard is a text or `ast` check, and none of them can see a script that does not parse.
- **Full suite: 767 passed, 0 failed** in 665.67s.
- **The D2 flake was self-inflicted, not a real flake.** Repeated full-suite runs had accumulated `pytest-temp-*` basetemp directories on `F:`; with them present the D2 file failed a *different* subset each run (`d2_19`-`d2_22`, then `terminal_05b[baseline_changed]` / `[extra_terminal_lf]`). Clearing them: D2 file passes **82/82 in 25s** (vs 119.98s on a dirty tree). `pytest-temp-engine` itself cannot be deleted - a `test_terminal_04_receipt_is_cr0` subdirectory is locked by something outside the test run - so use a fresh basetemp name rather than fighting it.
## Next
- Still outstanding: the production domain off Vercel Settings -> Domains, then the factory-machine steps (`cors-origins.txt`, `CHAY_WEB.bat`, `tunnel-url.txt`).
- **Worth asking LO**: the picker now writes a `QR_ISSUED` history event the first time an operator picks a part. If the factory's process is that a QR is issued by a supervisor before work starts, this changes who issues codes and should be confirmed rather than assumed.
# 2026-10-20 Production domain found: hms-qr-product-manager-web.vercel.app
## State
- **The production domain is `https://hms-qr-product-manager-web.vercel.app`** (also reachable as `hms-qr-product-manager-web-hms-98.vercel.app`). The project is **`hms-qr-product-manager-web`**, not `hms-qr-product-manager`.
- **How it was found.** Every alias of `hms-qr-product-manager` returned 404 with `X-Vercel-Error: DEPLOYMENT_NOT_FOUND` - the domain exists but has no production deployment. GitHub's commit-status API then named the real project: `Vercel: success (https://vercel.com/hms-98/hms-qr-product-manager-web/8Kuym4Z)`. The `-web` suffix was the whole mystery; `hms-qr-product-manager` is a stale project LO is no longer deploying to.
- **Git integration is healthy.** `refs/heads/main` on GitHub = `1e4559c` = local HEAD, pushed `2026-10-20T03:48:03Z`. The live page is 58127 bytes, which is exactly the committed size of `web/index.html` at `bb26bf9`, and it contains `qr_status !== 'ACTIVE'` and `async function selectPartFromList`. Nothing is stale.
- **Production verified 22/22**: both hostnames 200; `index.html`, `manifest.json`, `sw.js` and `static/jsqr.min.js` all match the repo (line endings aside - Vercel checks out LF, the working tree is CRLF); login form and part picker present; no hardcoded API origin; `hms-server-origin` runtime read present; `nosniff` on the page; `manifest.json` served as `application/json`; `Service-Worker-Allowed: /` on `sw.js`; `jsqr.min.js` cached `immutable`; `start_url`/`scope` = `/`; `display: standalone`; all three icons 200.
- **CORS verified 8/8 against the production origin**: preflight from `https://hms-qr-product-manager-web.vercel.app` is granted; preflights from a stranger origin and from localhost are refused; real login and catalog calls from the production origin carry `Access-Control-Allow-Origin: <production origin>`; a stranger origin gets no grant on a real call either.
- **Mixed content is a hard requirement, not a nicety.** The production page is HTTPS, and a browser refuses to let an HTTPS page fetch an HTTP origin. The first end-to-end attempt failed with `Failed to fetch` on every call - login, catalog, QR issue - purely because the test API was plain HTTP. **The factory server must therefore be HTTPS.** The Cloudflare quick tunnel already is (`*.trycloudflare.com` serves a valid certificate), so the planned setup satisfies this; a plain-HTTP LAN server would not.
- **Cả hai đường deploy đều được chạy end-to-end sau khi thêm traceability**: **production (Vercel + tunnel HTTPS thật) 22/22** và **LAN (same-origin) 11/11**. Cả hai cho cùng một dòng history: `'Cấp phát QR — 16:57:01 20/10/2026 — admin'` — nhãn tiếng Việt, mốc thời gian, tên người vận hành, và không còn chuỗi `QR_ISSUED` thô. Đường LAN quan trọng vì `apps/mobile/web.py` phục vụ chính file `web/index.html` đó tại `/tracking/mobile`, nên mọi thay đổi page đều ảnh hưởng cả hai.
- **The full browser journey from the real production page is now verified 16/16.** The certificate trust path - the one gap left after `8068741` - was closed by reproducing the factory setup exactly: a plain-HTTP uvicorn on `127.0.0.1` behind a Cloudflare quick tunnel, so the browser sees a valid `*.trycloudflare.com` certificate while the server itself stays HTTP. The page was loaded from `https://hms-qr-product-manager-web.vercel.app` (`isSecureContext: true`), pointed at the tunnel origin through `localStorage`, and driven through the whole operator journey. **This is the same shape as `CHAY_WEB.bat`** - the launcher runs the server on HTTP and terminates TLS at the tunnel, so what was proven here is what the factory machine will do. What was proven: login from the production page; the picker listing both parts; the pick of a part with no QR issuing one (`qr_status: None -> 'ACTIVE'`); that payload scanning 200 and resolving to the picked part; the pick of an already-ACTIVE part writing **no** history row; and the service worker registering on the production origin.
- **Two verification-script bugs worth remembering**: `dict(response.headers)` is case-sensitive while `HTTPMessage` is not, so header assertions must lowercase the keys first (this produced four false failures); and an OPTIONS request without `Access-Control-Request-Method` is routed to the app and answered 405, which is not a CORS result.
## Next
- **Factory machine steps** (verified shape, nothing left to prove):
  1. Write `https://hms-qr-product-manager-web.vercel.app` into `D:\HMS-QR-DATA\cors-origins.txt` (one origin per line is now safe after `535ca04`).
  2. Run `CHAY_WEB.bat`; read `D:\HMS-QR-DATA\tunnel-url.txt` for the HTTPS tunnel origin.
  3. On the phone, open `https://hms-qr-product-manager-web.vercel.app`, enter the tunnel origin in the connection screen, log in.
  4. The tunnel origin is random per run, so it must be re-entered whenever the tunnel restarts.
- **LO must delete the stale `hms-qr-product-manager` Vercel project himself** - no credentials are available here. Direct link: `https://vercel.com/hms-98/hms-qr-product-manager/settings` -> Delete Project -> type the project name. Confirmed safe: all aliases 404 `DEPLOYMENT_NOT_FOUND`, its only deployment is older than every commit in the repo, and GitHub commit-status points at `hms-qr-product-manager-web`.
- **Operator traceability for issued QRs — `1dce5f1`** (LO chon "Can ca hai": tho van tu lay duoc ma, nhung phai ghi nhan ai cap phat). Diều tra phat hien ha tang truy vet **da co san va chua ai dung**: endpoint doc header `X-Actor`, `save_item` ghi vao `tracking_audit_events.actor`, va CORS **da** cho phep header do. Thieu dung hai mat xich. (1) Page khong bao gio gui header, nen moi QR phat tu picker bi ghi la chuoi `"development-user"` - mot cai ten khong tra loi gi ca; wrapper fetch nay stamp `X-Actor` tu tai khoan dang nhap, chi khi co tai khoan, nen mot call chua xac thuc khong the bia nguoi van hanh va header tuong minh tu call site van thang. (2) `tracking_audit_events` chi ghi khong ai doc: history endpoint bao cao mot chi tiet di thang sang QC ma khong co ban ghi nao ve ai cap phat ma cua no. `TrackingRepository.audit_events` doc cac dong do va `TrackingHistoryService.history` gop chung vao, giu nguyen thu tu thoi gian va khong day di cac dong workflow/machining da co.
  - **Mot test cu dang assert su vang mat cua dong audit**: `test_stage4_api_surface_status_filter_and_qr_unchanged` kiem tra chinh xac danh sach `event_type` cua history cua mot item da cap phat QR, tuc la no dang chan rang dong audit khong hien ra. Da sua thanh assert dong do co mat va mang ten actor.
  - **Ba guard, moi cai chung minh RED bang cach tu hoan chinh no**: page dat ten nguoi van hanh; history cho thay ai cap phat QR; va CORS cap phep header ma page nay gui - cai cuoi quan trong vi `X-Actor` khong thuoc CORS-safelisted, thieu no moi call sua doi tu trang production se fail preflight.
  - **Xac nhan tren trang production that qua tunnel HTTPS that: 18/18**, trong do dong audit ghi `actor: 'admin'` - dung ten nguoi da dang nhap, khong con `development-user`.
  - Full suite: **770 passed** (767 + 3 guard moi).
- **Nhan tieng Viet cho audit event + giu lai old/new value — `ed6202f`** (tìm bằng cách hỏi bản ghi có thật sự *dùng được* không, không chỉ có mặt): (1) Dòng audit giờ hiện trong history, nhưng map `names` của `loadHistory` không có entry cho chúng, nên thợ đọc chuỗi tiếng Anh thô `QR_ISSUED` trên màn hình còn lại là tiếng Việt. Ba type là toàn bộ những gì `save_item` từng ghi vào `tracking_audit_events`, nên map nay phủ đúng tập đầy đủ. (2) Đọc dòng audit trả về cũng **làm mất** `old_value`/`new_value` — với `DELIVERY_DATE_CHANGED` đó là ngày cũ và ngày mới, và là bản ghi duy nhất về ngày trước đó là gì. Hai guard, mỗi cái chứng minh RED bằng cách tự hoàn chính nó. Full suite **772 passed**.
  - **Lỗi tự gây ra, bắt bởi guard đã có**: chạy script chèn nhãn hai lần (lần đầu lưu file rồi chết vì console cp949 không in được tiếng Việt, lần chạy lại chèn thêm) → block nhãn bị nhân đôi → `node --check` fail ngay. Guard `test_the_pages_inline_script_actually_parses` bắt được, đúng việc nó tồn tại để làm.
  - **Bài học ghi nhận**: viết script sửa file chứa tiếng Việt phải idempotent hoặc kiểm tra trước khi chèn; console PowerShell cp949 không in được tiếng Việt nên mọi print kiểm tra phải bỏ hoặc ghi ra file.
- Still open from before: whether the picker issuing a `QR_ISSUED` event on first pick matches the factory's process.

- **Canh bao tem cu khong khop — `1494b4d` + `8753f89`** (tim bang cach hoi co ai
  tieu thu `qr_identity_consistent` khong): server **luon luon** tinh xem payload QR
  co van khop voi item no tra ve khong. Tem in truoc khi thong tin chi tiet bi sua
  van resolve duoc, vi scan tra item bang `tracking_code` — nen tho thoay chi tiet
  ma khong co dau hieu tem cua no da cu. Lam viec tu tem cu la rui ro tinh dung,
  khong phai loi trang tri. **Khong ai doc flag do**: mot test assert no, khong
  caller nao dung. Page gio hien canh bao trong the san pham, va pick xoa no, vi
  payload cua pick do server tao va nhat dinh theo cau tao.
  - **Hai loi tu gay ra, ca hai deu bat duoc**:
    1. Title banner ghi `KH\u1edap` = "KHOP **p**" — chu p thuong giua chu hoa,
       trong khi dong ban ghi khac la chu hoa. Sua thanh `KH\u1edaP`.
    2. Check E2E cua toi `.upper()` title nhung khong upper needle, nen
       `"KH\u00d4NG KH\u1edap" in banner.upper()` **khong bao gio** khop — p
       thuong bi upper thanh P. So sanh phai cung chu hoa hai ben.
  - **Loi trong script E2E, khong phai loi page**: `#login-modal` ship
    `display:none` va chi `openLogin()` hien no. Script khong bao gio mo modal,
    nen vong lap `if modal == 'none': break` thoat ngay giay thu 1 — truoc khi
    login xong. Cac lan chay truoc may manh thanh cong vi fetch xong trong 1 giay;
    lan nay tunnel cham (DNS 5 lan) nen lo ra. Sua: mo modal, roi doi **token**,
    khong phai trang thai modal.
  - **PATCH product can `expected_updated_at`** (`app.py:230`) — optimistic
    concurrency. Phai GET product truoc roi gui kem `updated_at`.
  - Xac nhan tren trang production that qua tunnel HTTPS that: **26/26**, trong do
    tem bi sua giua in va quet, banner hien dung chu "MA QR KHONG KHOP DU LIEU",
    va pick chi tiet khac xoa canh bao.
  - Full suite: **771 passed** + 2 D2 flake da biet (chay rieng voi basetemp sach:
    82/82; khong file pin nao bi doi).

- **Cap phat QR ghi ten tho, khong phai ten dang nhap — `86991ed`** (tim bang
  cach doc quy uoc cua chinh codebase): `sendWorkflow` va `submitReport` deu
  chan neu `!userId` va ghi `#user`.textContent lam actor. Picker la ngoai le
  duy nhat — `selectPartFromList` va `openPartPicker` khong kiem tra `userId`,
  va `X-Actor` lay tu `readAccount().username`. Nen tren may dung chung, cung
  mot nguoi xuat hien hai ten trong mot history: bao cao gia cong ghi
  "Nguyen Van A", con cap phat QR ghi "admin".
  - **Quyet dinh cua toi, LO khong tra loi**: uu tien operator duoc chon, chi
    fallback ve dang nhap khi chua chon ai. Ly do: (1) nhat quan voi moi ghi
    nhan khac trong luồng tracking; (2) khong chan ai — neu bat buoc chon
    operator truoc khi pick co the be luồng "giam sat pick ho cho nhieu tho";
    (3) giu fallback, vi bo no se lam header bi thieu va server quay ve
    "development-user" — chinh la loi ca chuoi nay da sua.
  - **Khong phai bug, da kiem tra**: `product_api_client.py:92` dung `elif`
    (co token thi khong gui X-Actor), nhung `current_actor` lay actor tu
    `principal["username"]` khi da dang nhap — nen `elif` vo hai. Desktop
    cung khong co action issue/reissue/change_date nao.
  - **Cung khong phai bug**: `restore()` (L1450) co khoi phuc `#user` tu
    localStorage, nen sau reload khong con la "Chua chon".
  - Xac nhan tren trang production that qua tunnel HTTPS that: **28/28**, trong
    do chon nhan su truoc khi pick, dong audit ghi `actor: 'Nguyen Van A'`,
    va history hien thi dung ten do.
  - Full suite: **774 passed, 0 failed** (basetemp sach nen ca D2 cua pass).

- **Noi that bai thay vi do loi cho ma QR — `7a73320`** (tim bang cach quet
  moi `catch` trong page va hoi cai nao nuot loi that su):
  - **Cap phat QR nuot loi cua chinh no**. Payload cua catalog chi scan duoc
    khi QR cua item da ACTIVE, nen sau khi cap phat that bai, page van giu
    ban preview do va lan quet tiep theo tra ve "Không tìm thấy dữ
    liệu cho mã QR này" — **đổ lỗi cho mã QR** trong khi
    thất bại thỹc là \u1edf bước ghi. Thủ công đi tìm
    lỗi ở sai chỗ.
  - **Picker cùng mặc**: catalog không tải được thì picker mở
    ra rỗng và không nói gì — đọc thành "không có gì để
    chọn" chứ không phải "không tới được máy chủ". Endpoint
    này cũng trả 501 ngoài DEV, nên đó là trạng thái tới
    được, không phải giả định.
  - **Các catch im lặc khác giữ nguyên**, vì chúng là fallback
    progressive-enhancement (jsqr rồi BarcodeDetector) và WebSocket tự
    retry.
  - Xac nhung khong regression: production that qua tunnel HTTPS that **28/28**.
  - Full suite: **775 passed, 0 failed**.
- **Hai trong ba loai audit event khong the xuat hien tu bat ky man hinh nao**
  (ghi lai de khong ai mong doi thay chung): khong UI nao trong repo co the
  reissue QR, doi ngay giao, hoac tao don moi — page khong goi, desktop khong
  co action, portal cung khong. `QR_REISSUED` va `DELIVERY_DATE_CHANGED` chi
  dat duoc qua API. Nhan tieng Viet va old/new value toi them cho chung van
  đung, nhung khong the thay tu man hinh.
