# Deployment Topology

```text
Mobile --HTTPS--> reviewed ingress --> QR Server (Machine A) --> embedded SQL engine (SQLite)
                                              |
                                              +--> NAS (LAN-only files/archive)
Desktop --------API/polling-----------------+
```

No direct client-to-NAS or Internet-to-database connection is permitted.

The database layer changed on 2026-10-18: ADR-015 replaced PostgreSQL with
`packages/sqlengine`, which is embedded and SQLite-only. There is no separate
database server, no `postgresql+psycopg` URL, and no psycopg driver. The server
creates its SQLite file inside its own data root and applies the engine
migrations itself before serving traffic.
