# HMS QR Product Manager — Current State

Current Stage: STAGE_6_MACHINE_A_SERVER_DEPLOYMENT_FOUNDATION
Current WP: R011-WP1A local integration
Current Revision: R011-WP1A-I1
Current Branch: main
Current Verdict: LOCAL_INTEGRATED_REMOTE_DELIVERY_PENDING

R011-WP1A is locally integrated by exact fast-forward from canonical
`94c33180a31597c9386554a36a9f203659789a29` to the independently approved final
candidate `09454caed3d29d98c3d9669c0512c80483bc0b62`, tree
`c7e3845eb7defa8f851b52384336e09258ca0acd`. The approved certified artifact
identity is `1629e9ebfdd91f21ea7eada6912d311dc23aac49fcc1664a64373ba5aed4b58d`.
R1B independently proved all 86 payload files against Git blobs, cross-EOL
reproducibility, path and secret safety, tamper failure, focused `44`,
qualifying critical `51`, and full `187` tests with zero failures and zero
skips. I1 re-proved the exact integrated bytes, artifact binding, collector
static safety, path/config imports, and the focused `44` tests.

WP1A supplies source-side deployment modules, immutable artifact and verifier,
read-only inventory collector, plan/preflight/dry-run/lifecycle models, evidence
sanitizer, tests, and Vietnamese-first operator runbook. No Machine A inventory,
read, or mutation occurred. WP1B read remains unauthorized until WP1A is
remotely delivered; Machine A mutation remains separately unauthorized. See
`docs/checkpoints/CHECKPOINT_STAGE6_R011_WP1A_LOCAL_INTEGRATION.md`.

Historical R011B status: the independently approved R011 roadmap was fast-forward
integrated locally into `main` at `4ff89c934`; its later remote-delivery/state
chain established the current `94c33180` WP1A baseline. The roadmap remained
docs/state only until this WP1A candidate. `MACHINE_A_MUTATION_AUTHORIZED=NO`
remains in force.
No Machine A mutation, production PostgreSQL install, Windows service/user/
registry/firewall change, real NAS, Cloudflare, public exposure, source
implementation, test/dependency/migration change, or push occurred.

R011B pre-integration baseline: local/origin `main` HEAD
`3c77a29341ecb36ae2aa90c84413206b0c7adbd1`, tree
`c45e571cc78e3fd474da19c611e99c390757c78f`. Integrated roadmap HEAD is
`4ff89c9343aac23343068e8cd3e2dfdfef4ad700`, tree
`21011b9165a1c225ac1785721301b33b90c12d4c`. The five production gaps remain
open and unchanged. The earlier R1A1 review route was superseded by the R1A2
runtime-path remediation authority.

Stage progress: Stage 0 PASS; Stage 1 PASS; Stage 2 PASS; Stage 3 PASS; Stage 4 PASS; Stage 5 PASS and remotely delivered; Stage 6 R008, R009, R010, and the R011 roadmap are remotely delivered. R011-WP1A is independently approved and locally integrated; remote delivery remains pending and no push occurred under I1.

Design system: canonical light industrial tokens in `apps/design_tokens.py`. Penpot is the intended canonical visual design authority and UICanvas is the intended local rapid-prototype canvas. Open Design 0.19.0 remains optional historical tooling only; its paid AMR generation run is retired and is not retried.
Desktop redesign: shared PySide6 token theme applied to Product Master and Tracking.
Mobile redesign: existing operational flow retained with semantic CSS token layers,
focus states, and 44px touch-safe controls.
Visual evidence: Penpot exports plus external desktop captures at 1280x720 and
1920x1080; mobile runtime was checked at 360/390/414/768 with no horizontal
overflow and no browser console errors.
Regression results: R011-WP1A-R1B focused returned `44 passed`; qualifying
critical returned `51 passed, 1 inherited warning`; and the native-exit-safe,
Qt-last full regression returned `187 passed, 1 inherited warning` with zero
failures, zero skips, exit 0, and empty stderr. I1 bounded post-integration
verification returned `44 passed` and independently reverified the approved
artifact manifest, integrated Git identity, config/path imports, and collector
AST safety. The warning is the inherited Starlette/httpx deprecation.

Latest completed work: R011-WP1A-I1 fast-forwarded local `main` from the exact
remote baseline `94c33180a31597c9386554a36a9f203659789a29` to approved WP1A
`09454caed3d29d98c3d9669c0512c80483bc0b62`. No candidate/source/test/runtime
byte was changed during integration. No Machine A action, production action,
merge commit, or push occurred.

Known gaps:

```text
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

Production PostgreSQL integration is closed by R010; Machine A production
deployment remains a separate open gap. WP1A is local-only integrated and has
not been pushed. The next exact action is
`STAGE6_R011_WP1A_REMOTE_DELIVERY`; WP1B Machine A read remains unauthorized.

Latest authority: Stage 6 R011-WP1A-I1 local integration of final independently approved WP1A (external task attachment)
Latest checkpoint: docs/checkpoints/CHECKPOINT_STAGE6_R011_WP1A_LOCAL_INTEGRATION.md
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
