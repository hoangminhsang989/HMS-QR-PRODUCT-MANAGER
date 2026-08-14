# HMS QR Product Manager — Current State

Current Stage: STAGE_6_NAS_STORAGE_IMAGES_ATTACHMENTS_BACKUP_EXCEL
Current WP: Managed storage + product files + backup + Excel template foundation
Current Revision: R008A1
Current Branch: stage6-r008a1-alembic-boundary-fix
Current Verdict: PASS_STAGE6_R008A1_ALEMBIC_REVISION_BOUNDARY_REMEDIATION_CANDIDATE

Stage progress: Stage 0 PASS; Stage 1 PASS; Stage 2 PASS; Stage 3 PASS; Stage 4 PASS; Stage 5 PASS and remotely delivered; Stage 6 R008 bounded foundation candidate ready for independent review.

Design system: canonical light industrial tokens in `apps/design_tokens.py`. Penpot is the intended canonical visual design authority and UICanvas is the intended local rapid-prototype canvas. Open Design 0.19.0 remains optional historical tooling only; its paid AMR generation run is retired and is not retried.
Desktop redesign: shared PySide6 token theme applied to Product Master and Tracking.
Mobile redesign: existing operational flow retained with semantic CSS token layers,
focus states, and 44px touch-safe controls.
Visual evidence: Penpot exports plus external desktop captures at 1280x720 and
1920x1080; mobile runtime was checked at 360/390/414/768 with no horizontal
overflow and no browser console errors.
Regression results: `40 passed, 1 warning` in 92.18s with controlled external
pytest temp root; warning is external Starlette/httpx deprecation.

Latest completed work: typed event-based QC/shortage/NG-rework/packing/delivery/
general-report workflows anchored to Tracking Item, atomic status projection,
active-revision quantity aggregates, semantic idempotency, structured APIs,
desktop actions/history, mobile QC/GIAO HÀNG mode and fresh R006A review.

Known gaps:

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

Next exact action: separately authorize NAS storage + Product images/attachments
+ backup foundation + exact Excel template preparation. Do not start it inside
R006A without new authority.

Latest authority: docs/authorities/AUTHORITY_STAGE4_R006A.md
Latest checkpoint: docs/checkpoints/CHECKPOINT_STAGE4_R006A_INTEGRATION.md
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
