# HMS QR Product Manager — Current State

Current Stage: STAGE_5_UI_DESIGN_SYSTEM_OPEN_DESIGN
Current WP: QC + NG return + packing + delivery status
Current Revision: R007
Current Branch: stage5-ui-design-system-open-design
Current Verdict: CANDIDATE_STAGE5_UI_DESIGN_SYSTEM_OPEN_DESIGN_R007

Stage progress: Stage 0 PASS; Stage 1 PASS; Stage 2 PASS; Stage 3 PASS; Stage 4 PASS; Stage 5 UI implementation in progress.

Design system: canonical dark industrial tokens in `apps/design_tokens.py`; Open Design 0.19.0 installed and startup smoke passed. R007B2 recovered the exact Open Design-generated STDIO configuration; ChatGPT Desktop Add Server/save/restart is pending user UI action, with recognition/read test still pending.
Desktop redesign: shared PySide6 token theme applied to Product Master; Tracking theme integration pending final normalization.
Mobile redesign: existing operational flow retained; shared token authority documented for CSS refactor.
Visual evidence: pending fresh captures under `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`.
Regression results: `40 passed, 1 warning` in 77.88s with controlled external pytest temp root; warning is external Starlette/httpx deprecation.

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
