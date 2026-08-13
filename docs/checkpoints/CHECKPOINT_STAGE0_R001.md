# CHECKPOINT

Date: 2026-08-13
Stage: STAGE_0_PROJECT_BOOTSTRAP_AND_AUTHORITY
WP: WP0.1-WP0.6
Revision: R001
Branch: main
HEAD: c300648a0d6be8568316630a0d3502c1394ec5b4
Tree: 4baafc1c6c36f3d1191502a373d9a59018753aba
Parent: UNBORN_REPOSITORY

Checkpoint identity is the immutable foundation baseline; later metadata-only
commits may advance repository HEAD without changing the Stage 0 result.

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
