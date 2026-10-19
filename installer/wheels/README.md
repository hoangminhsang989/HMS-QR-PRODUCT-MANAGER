# Offline Python Wheels

This directory contains the Python 3.14 x64 wheels required by HMS QR Server Tool, Server, and Desktop. The application itself has no third-party runtime dependencies since ADR-015 moved persistence to the embedded SQL engine; the remaining wheels cover the toolchain only (PySide6 for the Server Tool and Desktop, FastAPI/uvicorn for the Server, openpyxl for Excel, pytest for the test suite).

```powershell
py -3.14 -m pip download --dest installer/wheels -r requirements.txt PySide6
```

The target Server installs only from this directory with `--no-index` and does not download packages from the Internet.
