# PostgreSQL LAN Deployment

> **Superseded on the database layer by ADR-015 (2026-10-18).** The server no
> longer runs PostgreSQL and no longer accepts a `postgresql+psycopg` URL: it
> embeds its own SQL engine (`packages/sqlengine`) and creates a local SQLite
> database file at `D:\HMS-QR-PROD\hms_qr.db`. The LAN topology, NAS storage
> rules, firewall guidance, and environment-variable handling below remain the
> deployment reference; ignore every PostgreSQL-specific step and set
> `HMS_QR_DATABASE_URL` to the SQLite file path the Server Tool writes.

This runbook deploys one central HMS QR server for trusted LAN desktops.
It does not expose the database to desktops or the public Internet.

## Scope And Prerequisites

- Install supported Python dependencies with `pip install -r requirements.txt`.
- Run PostgreSQL on the server only. Bind PostgreSQL to loopback unless a database administrator has approved another isolated server-to-server network.
- Create a PostgreSQL database and least-privilege application role. The application connection URL must use `postgresql+psycopg`.
- Create the configured NAS/storage root and grant the server service identity access. Desktop users must not access this share directly.
- Store environment variables in the host's protected service configuration. Do not commit a `.env` containing live credentials.
- Confirm the server firewall and chosen HTTP port are approved by the network administrator. This runbook does not change firewall rules or stop conflicting processes.

## Server Environment

Set these values for the account that starts the service. Use `config/.env.example` only as a non-secret field reference.

```text
HMS_QR_ENV=prod
HMS_QR_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/hms_qr
HMS_QR_STORAGE_ROOT=\\NAS-SERVER\hms-qr-files
HMS_QR_AUTH_SECRET=<long-random-secret>
HMS_QR_BOOTSTRAP_ADMIN_USERNAME=<initial-admin-name>
HMS_QR_BOOTSTRAP_ADMIN_PASSWORD=<initial-admin-password>
HMS_QR_ALLOW_EMPTY_PASSWORDS=false
```

`HMS_QR_AUTH_SECRET` signs bearer sessions. Generate a unique high-entropy value and retain it in the protected server secret store. Changing it invalidates all active sessions. Account activity and role are rechecked against the server database on every authenticated request, so disabling an account or changing its role in `/admin` applies to its existing sessions immediately. On the first production startup against an empty account table, the server creates the bootstrap `ADMIN` account before serving traffic; missing or invalid bootstrap credentials stop startup. Once an account exists, the bootstrap values are ignored and may be removed from the service environment.

The application validates the database URL, storage root, and authentication configuration at startup. `prod` requires a complete `postgresql+psycopg` URL, an existing writable external storage root, and an `HMS_QR_AUTH_SECRET` of at least 32 characters. Startup writes and removes a probe file in the storage root, so it will fail if the NAS mount is unavailable or not writable. It will not start with SQLite, a placeholder value, or `HMS_QR_ALLOW_EMPTY_PASSWORDS=true`.

Before starting or upgrading the server, apply the shipped engine migrations with the same `HMS_QR_DATABASE_URL`. Production startup verifies the applied engine migration versions are at least the head shipped with the server; it does not apply migrations automatically.

## Migrate Then Start

Run migrations from the repository root in the same protected environment:

```powershell
py -3.14 -c "from config.environments import load_config; from packages.persistence.database import create_database_runtime; from packages.persistence.stage2_repository import Stage2Repository; runtime=create_database_runtime(load_config()); Stage2Repository(runtime).create_schema(); runtime.dispose()"
uvicorn apps.server.app:app --host 0.0.0.0 --port 8000
```

`load_config()` reads `HMS_QR_DATABASE_URL` from the environment, so no configuration file carries a connection string. The engine migrations under `migrations/engine/` are what `require_database_schema_current` compares against, so a successful run leaves the applied versions at the shipped head.

Do not use `--reload` for the deployed server. Terminate and restart the managed server process only through the approved service-management procedure when updating code or configuration.

## Verify Server Readiness

From the server, then from an approved LAN workstation, verify the database readiness endpoint:

```powershell
Invoke-WebRequest http://SERVER-LAN-IP:8000/health/readiness/database
Invoke-WebRequest http://SERVER-LAN-IP:8000/files/health/readiness/files
```

The database endpoint must return a successful response before connecting Desktop clients. A `200` response means the database is reachable and its schema matches the deployed engine migration head; a schema problem returns `503 DATABASE_SCHEMA_UNAVAILABLE`. The configured storage root is write-probed during startup, so a running production server has already passed that check. Configure a distinct archive target through the storage administration API before file uploads; the file endpoint returns `503 FILE_TRANSFER_UNAVAILABLE` until an active configuration and writable local ingest exist. It returns `200` with `DEGRADED` when the archive is temporarily unavailable but local-first uploads remain safe to queue. Sign in at `http://SERVER-LAN-IP:8000/admin` using the bootstrap administrator, create named `EDITOR` and `VIEWER` accounts, and confirm the diagnostics page reports the intended server address.

## Native Server Tool LAN operations

`HMS QR Server Tool` can bind the local test service to all network interfaces and displays the LAN URL that Desktop clients should use. Open the firewall only through its **MỞ FIREWALL LAN** action while running the tool as a Windows Administrator; it creates a TCP rule limited to the Private profile and the configured Server port. Do not expose the port on Public networks.

The **ÁP DỤNG IP TĨNH** action requires an explicit adapter name, IPv4 address, prefix, gateway, and DNS values, then a confirmation because changing the active adapter can disconnect the operator. It requires Windows Administrator privileges and does not guess network values.

Use separate writable folders for **Data vận hành** and **Data backup**. The tool rejects identical or nested paths, applies a changed data location only after a Server Tool restart, and can create a point-in-time SQLite database backup on demand. Production PostgreSQL backup remains an operator-managed database backup procedure; do not substitute a file copy for PostgreSQL backup.

The legacy portal's Excel import, paste import, QR catalog, and Excel export routes are SQLite-only. On this PostgreSQL deployment they deliberately return `501 SQLITE_LEGACY_ENDPOINT_UNSUPPORTED`; use the supported Product, File, and Tracking API/Desktop workflows instead.

Use roles as follows:

- `ADMIN`: account, storage, and server administration plus product writes.
- `EDITOR`: product, file, and tracking writes.
- `VIEWER`: read-only API access.

The server will not disable or demote the final active `ADMIN` account. Before removing an administrator's access, create or retain another active `ADMIN` account to preserve the management recovery path.

Keep `HMS_QR_ALLOW_EMPTY_PASSWORDS=false` unless an explicitly approved internal-only deployment requires empty passwords. Never enable it for public or VPN-exposed service access.

## Configure Desktop Clients

Set only these values in each Desktop launch environment:

```text
HMS_QR_SERVER_URL=http://SERVER-LAN-IP:8000
HMS_QR_USERNAME=<named-account>
HMS_QR_PASSWORD=<account-password>
```

Do not set `HMS_QR_DATABASE_URL`, `HMS_QR_STORAGE_ROOT`, NAS credentials, or bootstrap credentials on Desktop. Start with `python -m apps.desktop` and verify that a product can be listed, created by an `EDITOR`, and read but not written by a `VIEWER`.

For two-machine acceptance, open the same product on two `EDITOR` desktops. Save from the first desktop, then attempt to save the stale copy from the second. The second update must return the Product Master conflict message rather than overwrite the first update. The second Desktop detects the newer list state within 30 seconds without replacing an open worksheet draft.

## Network And Recovery Boundaries

- Permit client HTTP access only to the reviewed HMS QR server listener. PostgreSQL remains server-local.
- Add TLS/reverse proxy and explicit public-access review before any Internet exposure. Do not publish the direct Uvicorn listener.
- Back up PostgreSQL using the database administrator's approved procedure and back up NAS-managed files separately.
- Before upgrade, take a verified database backup, apply the shipped engine migrations, check readiness, and retain the previous application release for rollback. The engine has no downgrade support, so a rollback means restoring the backup rather than reversing a migration.
