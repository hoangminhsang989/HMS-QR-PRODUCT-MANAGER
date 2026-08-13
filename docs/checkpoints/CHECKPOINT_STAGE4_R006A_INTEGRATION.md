# CHECKPOINT

Date: 2026-08-13
Stage: Stage 4 — QC + NG Return + Packing + Delivery Status
Revision: R006A
Verdict: PASS_STAGE4_QC_PACKING_DELIVERY_R006A_INTEGRATED

## Input and review identity

- Input candidate verdict: `PASS_STAGE4_QC_PACKING_DELIVERY_R006`
- Input candidate HEAD/tree: `c37587f06144ba4176e7df830a0e2a8af67927b7` /
  `c98c4132b52b910ff75e354b818c02be257036fe`
- Accepted main baseline HEAD/tree: `fd2148a4c89ecde4c399addc41858c63106c452d` /
  `ef85816744cfc56e002802c851d2266a489f3cd0`
- R006A authority SHA256 source/saved:
  `C5F5D6A8131E41B8400736CFA84918C7FE56CAE769039A2A7FBACB2F0405E410`

## Independent review findings and bounded remediation

Review confirmed the event source-of-truth model, typed persistence, atomic
projection, active-revision aggregate semantics, NG/rework, API, desktop,
mobile, Alembic, and Stage 3 non-regression. One bounded candidate defect was
found: same request UUID retries did not fingerprint all semantic payload
fields, so an incompatible notes/quantity/reference retry could be treated as
the original event.

Remediation:

- `WorkflowRepository` now compares item, event type, quantity, notes,
  machining/process references, actor identity/snapshot, client/device and
  supersession identity for idempotency conflicts.
- Added R006A tests for all six event classes, incompatible payload retries,
  revision retry conflicts, active effective aggregates, additive shortage,
  downstream packing guard, structured API errors, and general-report revision.
- No unrelated refactor or next-stage work was added.

Remediated candidate:

- `REMEDIATED_HEAD=7797dad1814fc441909054eb1606b775c859d849`
- `REMEDIATED_TREE=6a795ebb2faa654d31015e8668ae2fe6134c8cf8`
- Changed paths versus accepted main: `24`
- `UNRELATED_CHANGE_COUNT=0`
- Fresh pre-integration approval:
  `APPROVE_STAGE4_R006A_INTEGRATION`

## Revision and aggregate audit

- Effective aggregate includes only active/current revision for each event.
- Superseded shortage/packing/delivery/NG revisions contribute zero.
- Independent shortage events are additive; correcting one event changes only
  that event's active contribution.
- Packed corrections revalidate downstream delivered quantity; invalid
  corrections fail transactionally without deleting delivery history or
  leaving a partial projection.
- Effective rules remain `packed <= target - shortage` and `delivered <= packed`.
- Multiple QC cycles and rework on the same Tracking Item/QR remain supported.

## Integration method

- Verified main exact baseline and clean before integration.
- Method: `git merge --ff-only stage4-qc-packing-delivery`
- No squash, rebase, force operation, or remote push.
- Final main HEAD/tree: `7797dad1814fc441909054eb1606b775c859d849` /
  `6a795ebb2faa654d31015e8668ae2fe6134c8cf8`

## Fresh post-integration evidence

```text
R006A critical post-integration: 13 passed, 1 external warning
Full Stage 0-4 post-integration regression: 40 passed, 1 external warning
ALEMBIC_SQLITE_MIGRATION_SMOKE_PASS
TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION
git diff --check: PASS
Mobile browser: fresh local QR scan, user picker, QC event/history refresh,
all six actions, viewport 390x844, scrollWidth == clientWidth, no console errors.
NAS: read-only existence check only; no write.
```

The unchanged warning is
`STARLETTE_HTTPX_DEPRECATION_EXTERNAL_NON_BLOCKING`; no new own-code warning
was accepted.

## Truthful known gaps

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED
```

R006A did not start another stage, add Routing, write NAS/production PostgreSQL,
deploy Cloudflare/Machine A, claim camera acceptance, or claim exact Excel
template fidelity.

## Next exact action

The next authorized development mega-WP is NAS storage + Product images/
attachments + backup foundation + exact Excel template preparation. Production
PostgreSQL/Machine A remains a later separately authorized gate.
