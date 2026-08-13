# CHECKPOINT

Date: 2026-08-13
Stage: STAGE_0_PROJECT_BOOTSTRAP_AND_AUTHORITY
WP: WP0.1-WP0.6
Revision: R001
Branch: main
HEAD: c7023fec2db677c8b41610f4ab4f143631213810
Tree: d03f36bef2f60575ffd79c09d9723b3a54f2998c
Parent: UNBORN_REPOSITORY

## Objective

Establish the QR Product Manager foundation, architecture records, source layout,
test isolation, and minimal smoke gate.

## Work completed

- Read-only preflight and inventory of production/test roots.
- Added source/documentation skeleton for server, desktop, mobile, packages, config,
  tests, and scripts.
- Added test isolation guard and redirected pytest cache/temp output to the test root.
- Added minimal server/desktop import smoke tests.

## Changed files

See the foundation commit and `git show --stat`.

## Tests executed

- `python scripts/check_test_isolation.py`
- `python -m pytest -q --basetemp=F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\pytest-tmp`

## Results

`TEST_ISOLATION_PASS`; `2 passed`.

## Known issues

- PostgreSQL CLI tools are not available in PATH in this environment.
- `npm.ps1` is blocked by the PowerShell execution policy; Node itself is present.

## Decisions

Live database on Machine A, NAS server-mediated, opaque QR references, immutable
audit/revision direction, and external test artifacts are recorded in
`docs/DECISIONS.md`.

## Risks

No database or frontend runtime integration has been attempted in Stage 0.

## Next exact action

Begin Stage 1 only under a fresh authority after reviewing the recorded blockers.

## Resume instruction

Read `PROJECT_STATE.md`, this checkpoint, and the latest authority before acting.
