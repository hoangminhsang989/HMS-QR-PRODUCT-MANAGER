# Offline Python Wheels

`THIET_LAP_SERVER_1_CLICK.bat` installs into the bundled Python with

```
py -3.14 -m pip install --no-index --find-links installer\wheels -r requirements.txt PySide6
```

so Server setup fetches nothing from the Internet. Both `-r requirements.txt` and
the bare `PySide6` argument are needed: neither alone covers the set.

## What is actually installed

That command installs 37 distributions, which is every wheel in this directory:

- **requirements.txt** — 12 entries. FastAPI/uvicorn/pydantic are the Server
  itself, not a build tool. opencv-python and numpy do QR scanning, pillow and
  qrcode draw labels, openpyxl and xlrd read Excel, and httpx is imported by
  `packages/hms_license/client.py` for the license gate.
- **PySide6** — pulls PySide6, PySide6_Essentials, PySide6_Addons and
  shiboken6 for the Server Tool and Desktop.

## Every wheel here is installed by that command

The 37 wheels in this directory are exactly the 37 distributions that command
installs — no more, no less. `test_the_recorded_wheels_are_the_wheels_a_release_would_contain`
fails if a wheel is present that nothing installs, or a recorded wheel is
missing.

Eight wheels used to sit here that nothing installed and nothing imported:
`alembic`, `greenlet`, `mako`, `markupsafe`, `psycopg`, `psycopg_binary`,
`sqlalchemy` and `tzdata`. They were left over from the PostgreSQL path that
ADR-015 replaced with the embedded SQL engine, and
`test_r010r2_database_runtime.py` already forbids the first three by name in
`requirements.txt` and `pyproject.toml`. They were removed rather than left for
a reader to assume they were required.

## Verifying the set

`CHECKSUMS.sha256` records the SHA-256 of every wheel in this directory and is
tracked in Git, so a release can be checked against a known state even though
the wheels themselves are gitignored and a clone carries none of them.
`tests/stage6/test_offline_wheel_completeness.py` fails when
`requirements.txt` asks for a distribution with no recorded wheel, and when a
wheel does not match its checksum.

This matters because the set once shipped without `httpx` — a requirement in
`requirements.txt` that `packages/hms_license/client.py` imports — and the
offline install died on `ERROR: No matching distribution found for
httpx>=0.27.0`. `production_setup_requirements` only asks whether at least one
`*.whl` exists, which an incomplete set trivially satisfies.

## Reproducing this directory

Do not expect `pip download` to reproduce these wheels. This directory is a
snapshot, not the output of the command above: 19 of these distributions have
since moved on (fastapi 0.141.1 is now 0.162.0, pillow 12.3.0 is 13.0.0,
PySide6 6.11.2 is 6.12.0), and PySide6 6.12 added `pyside6-pdf`,
`pyside6-webengine` and `opentelemetry-api` that this snapshot predates.

To rebuild the set deliberately, download against the same target the installer
ships and then re-record the checksums:

```powershell
py -3.14 -m pip download --dest installer/wheels --only-binary=:all: `
    --python-version 3.14 --platform win_amd64 --platform any `
    -r requirements.txt PySide6
py -3.14 -m pytest tests/stage6/test_offline_wheel_completeness.py
```

Rebuilding picks up newer versions, which is a decision to make on purpose —
pin with `==` if a release must be byte-reproducible.
