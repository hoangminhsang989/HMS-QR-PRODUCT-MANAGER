# Test Policy

Tests are categorized by unit, integration, API, database, desktop, mobile, E2E,
migration, security, offline/reconnect, and concurrency concerns.

Pytest temporary directories, cache, coverage, screenshots, exports, and test
databases must be redirected to `F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`.

R002 verification uses `PYTHONDONTWRITEBYTECODE=1` and an external
`--basetemp` so Python caches and pytest artifacts cannot be mistaken for
production source. Generated Excel workbooks and SQLite files are created only
under the test root and are not committed.
