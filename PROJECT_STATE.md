# HMS QR Product Manager — Current State

Current Stage: STAGE_6_MACHINE_A_SERVER_DEPLOYMENT_FOUNDATION
Current WP: Engine cutover complete; mobile web app extracted for Vercel deployment
Current Revision: ADR-015 engine cutover (SQLAlchemy/Alembic/PostgreSQL removed)
Current Branch: main
Current Verdict: ENGINE_CUTOVER_COMMITTED_AND_PUSHED_03010ae_746_PASSED_D2_SUBPROCESS_FLAKE_ONLY_VERCEL_SETUP_PENDING_LO

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