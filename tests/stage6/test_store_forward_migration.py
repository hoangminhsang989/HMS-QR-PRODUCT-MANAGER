"""Stage 6 store-forward migration boundary.

The engine runner has no downgrade step, so the R009 boundary is proven by
applying a prefix of the migration list and asserting the store-forward tables
are absent, then applying the full list and asserting they appear with the
exact contract the application relies on.
"""

from pathlib import Path

from config.paths import SOURCE_ROOT
from packages.sqlengine import Database
from packages.sqlengine.migrations import applied_versions, load_migration_modules, run_migrations


R009_TABLES = {"storage_configurations", "archive_transfer_jobs"}

R009_VERSION = 5

R009_CONTRACT = {
    "storage_configurations": {
        "columns": (
            ("internal_id", "TEXT", False, True),
            ("local_ingest_root", "TEXT", False, False),
            ("archive_target_root", "TEXT", False, False),
            ("grace_period_hours", "INTEGER", False, False),
            ("retry_schedule_seconds", "TEXT", False, False),
            ("warning_free_bytes", "INTEGER", False, False),
            ("critical_free_bytes", "INTEGER", False, False),
            ("upload_refusal_free_bytes", "INTEGER", False, False),
            ("active", "BOOLEAN", False, False),
            ("created_at", "DATETIME", False, False),
            ("updated_at", "DATETIME", False, False),
        ),
        "foreign_keys": (),
        "unique_constraints": (),
    },
    "archive_transfer_jobs": {
        "columns": (
            ("internal_id", "TEXT", False, True),
            ("managed_file_id", "TEXT", False, False),
            ("configuration_id", "TEXT", False, False),
            ("state", "TEXT", False, False),
            ("attempt_count", "INTEGER", False, False),
            ("next_retry_at", "DATETIME", True, False),
            ("last_attempt_at", "DATETIME", True, False),
            ("last_error_code", "TEXT", True, False),
            ("last_error_summary", "TEXT", True, False),
            ("remote_verified_at", "DATETIME", True, False),
            ("grace_expires_at", "DATETIME", True, False),
            ("local_purged_at", "DATETIME", True, False),
            ("lease_token", "TEXT", True, False),
            ("lease_expires_at", "DATETIME", True, False),
            ("created_at", "DATETIME", False, False),
            ("updated_at", "DATETIME", False, False),
        ),
        "foreign_keys": (
            ("configuration_id", "storage_configurations", "internal_id"),
            ("managed_file_id", "managed_files", "internal_id"),
        ),
        "unique_constraints": (("managed_file_id",),),
    },
}


def _migrations():
    return load_migration_modules(SOURCE_ROOT / "migrations" / "engine")


def _now() -> str:
    return "2026-01-01T00:00:00+00:00"


def _table_contract(database: Database, table_name: str) -> dict[str, object]:
    table = database.schema.table(table_name)
    return {
        "columns": tuple(
            (column.name, column.type.name, column.nullable, column.primary_key)
            for column in table.columns
        ),
        "foreign_keys": tuple(
            sorted(
                (foreign_key.column, foreign_key.target_table, foreign_key.target_column)
                for foreign_key in table.foreign_keys
            )
        ),
        "unique_constraints": tuple(
            sorted(tuple(constraint) for constraint in table.unique_constraints)
        ),
    }


def test_0005_revision_boundary_and_schema_contract(tmp_path: Path):
    migrations = _migrations()
    database = Database(tmp_path / "r009-boundary-engine")
    try:
        prefix = [item for item in migrations if item[0] < R009_VERSION]
        run_migrations(database, prefix, now=_now)
        assert R009_TABLES.isdisjoint(set(database.schema.tables))

        run_migrations(database, migrations, now=_now)
        assert R009_TABLES <= set(database.schema.tables)
        for table_name in sorted(R009_TABLES):
            assert _table_contract(database, table_name) == R009_CONTRACT[table_name]

        assert run_migrations(database, migrations, now=_now) == []
        assert applied_versions(database) == {version for version, _, _ in migrations}
    finally:
        database.close()
