# HMS QR Product Manager — Stage 0 to Stage 1 Handoff

## Closeout status

Stage 0 R001 closeout is process-only. No Stage 1 implementation, architecture
change, business logic, PostgreSQL installation, or PowerShell execution-policy
change was performed.

External authority verdict: `PASS_STAGE0_FOUNDATION_R001`

## Accepted Stage 0 baseline

- Repository: `F:\PHAN-MEM-QUAN-LY-QR`
- Branch: `main`
- Accepted baseline HEAD: `34dc36ad02e56e9611b6880ff73b5adff25af5da`
- Accepted baseline tree: `574e8bd1cc0f200cbea978a81c778585583c24c3`
- Working tree at the accepted Stage 0 report: clean

The process-only handoff commit that adds this document may advance repository
HEAD; that metadata commit does not change the accepted Stage 0 verdict or
baseline identity above.

## Stage 0 completed work

Stage 0 established the QR Product Manager foundation (WP0.1–WP0.6):

- completed read-only environment preflight and production/test-root inventory;
- added the source and documentation skeleton for server, desktop, mobile,
  packages, configuration, scripts, and tests;
- recorded the architecture, deployment topology, security, data-model, and
  product decisions;
- added the test-isolation guard and redirected pytest cache/temp output to the
  external test root;
- added minimal server/desktop import smoke coverage;
- recorded the immutable Stage 0 authority and checkpoint.

## Test evidence

The accepted checkpoint records these bounded commands and results:

```text
python scripts/check_test_isolation.py
TEST_ISOLATION_PASS

python -m pytest -q --basetemp=F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\pytest-tmp
2 passed
```

Closeout verification must keep all generated pytest/cache/temp output under the
test root and must not create runtime or test artifacts in the production root.

## Test isolation rules

- Production root is source/documentation only.
- Test, runtime, build, coverage, screenshot, export, temporary, and test
  database artifacts belong only under the test root.
- The client must not access the NAS directly; all production data/file access
  is server-mediated.
- Do not treat a local smoke test or preflight as production readiness.

Production root: `F:\PHAN-MEM-QUAN-LY-QR`

Test root: `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`

## Deployment facts to carry forward

- NAS production share: `\\192.168.1.58\data-pm-qr`
- This machine is the **DEV WORKSTATION**, not Machine A production.
- Machine A is not currently present on site.
- The live production database will later run on Machine A.
- Clients do not access or mount the NAS directly; the server on Machine A is
  the authority for database and NAS access.

## Files a new Codex chat must read first

Read these files before taking any further action:

1. `PROJECT_STATE.md`
2. `docs/handoffs/HANDOFF_STAGE0_TO_STAGE1.md` (this handoff)
3. `docs/authorities/AUTHORITY_STAGE0_R001.md`
4. `docs/checkpoints/CHECKPOINT_STAGE0_R001.md`
5. `README.md`
6. `docs/ARCHITECTURE.md`
7. `docs/DECISIONS.md`
8. `docs/DEPLOYMENT_TOPOLOGY.md`
9. `docs/TEST_POLICY.md`
10. `docs/SECURITY.md`
11. `docs/DATA_MODEL.md`

## Known non-blockers

- `psql` and `pg_isready` are not available on `PATH`.
- `npm.ps1` is blocked by the PowerShell execution policy, but Node exists.

These are environment observations, not reasons to alter the accepted Stage 0
verdict.

## Next exact action

`STAGE1_PRODUCT_MASTER_VERTICAL_SLICE_R002`

Begin it only under fresh Stage 1 authority in a new Codex chat. This handoff
does not authorize implementation by itself.
