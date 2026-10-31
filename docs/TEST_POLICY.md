# Test Policy

Tests are categorized by unit, integration, API, database, desktop, mobile, E2E,
migration, security, offline/reconnect, and concurrency concerns.

Pytest temporary directories, cache, coverage, screenshots, exports, and test
databases must be redirected to `D:\HMS-QR-CHECK`.

The path is not hardcoded: `HMS_QR_TEST_ROOT` selects it, every root
launcher sets it, and `config/paths.py` rejects a root that is not an
absolute path outside the source tree. A root that disappears with its
drive is exactly what happened here - `H:` held this repository for a
while and no longer exists on the machine, so the launchers and this
policy both named a dead drive until the move to `D:`.

R002 verification uses `PYTHONDONTWRITEBYTECODE=1` and an external
`--basetemp` so Python caches and pytest artifacts cannot be mistaken for
production source. Generated Excel workbooks and SQLite files are created only
under the test root and are not committed.
