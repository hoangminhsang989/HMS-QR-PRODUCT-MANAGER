# Offline Python Wheels

This directory contains the Python 3.14 x64 wheels required by HMS QR Server Tool, Server, and Desktop. The current offline bundle contains 38 wheels, including PostgreSQL `psycopg`, PySide6, and all requirements.

```powershell
py -3.14 -m pip download --dest installer/wheels -r requirements.txt psycopg[binary] PySide6
```

The target Server installs only from this directory with `--no-index` and does not download packages from the Internet.
