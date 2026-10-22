"""Stage 6 migration boundary: the engine migrations must add the managed-file
tables at the right version and not before it.

The engine runner has no downgrade step, so the boundary is proven by applying
a prefix of the migration list and asserting the stage 6 tables are absent,
then applying the full list and asserting they appear with the exact contract
the application relies on.
"""

from pathlib import Path

from config.paths import SOURCE_ROOT
from packages.sqlengine import Database
from packages.sqlengine.migrations import applied_versions, load_migration_modules, run_migrations


STAGE6_TABLES = {"managed_files", "product_file_relations"}

STAGE6_CONTRACT = {
    "managed_files": {
        "columns": (
            ("internal_id", "TEXT", False, True),
            ("original_filename", "TEXT", False, False),
            ("stored_filename", "TEXT", False, False),
            ("storage_key", "TEXT", False, False),
            ("category", "TEXT", False, False),
            ("media_type", "TEXT", False, False),
            ("extension", "TEXT", False, False),
            ("size_bytes", "INTEGER", False, False),
            ("sha256", "TEXT", False, False),
            ("status", "TEXT", False, False),
            ("source", "TEXT", False, False),
            ("version", "INTEGER", False, False),
            ("created_at", "DATETIME", False, False),
            ("created_by", "TEXT", False, False),
            ("updated_at", "DATETIME", False, False),
            ("replaced_file_id", "TEXT", True, False),
            ("archived_at", "DATETIME", True, False),
            ("archived_by", "TEXT", True, False),
            ("failure_reason", "TEXT", True, False),
        ),
        "foreign_keys": (("replaced_file_id", "managed_files", "internal_id"),),
        "unique_constraints": (("storage_key",),),
    },
    "product_file_relations": {
        "columns": (
            ("internal_id", "TEXT", False, True),
            ("product_id", "TEXT", False, False),
            ("managed_file_id", "TEXT", False, False),
            ("kind", "TEXT", False, False),
            ("attachment_category", "TEXT", True, False),
            ("is_primary", "BOOLEAN", False, False),
            ("sort_order", "INTEGER", False, False),
            ("caption", "TEXT", True, False),
            ("created_at", "DATETIME", False, False),
            ("archived_at", "DATETIME", True, False),
        ),
        "foreign_keys": (
            ("managed_file_id", "managed_files", "internal_id"),
            ("product_id", "products", "internal_id"),
        ),
        "unique_constraints": (("managed_file_id",),),
    },
}

STAGE6_VERSION = 4


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


def test_engine_migration_versions_are_ordered_and_unique():
    migrations = _migrations()
    versions = [version for version, _, _ in migrations]
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)
    assert versions[0] == 1
    assert versions[-1] == 8


def test_stage6_version_boundary_and_schema_contract(tmp_path: Path):
    migrations = _migrations()
    database = Database(tmp_path / "boundary-engine")
    try:
        prefix = [item for item in migrations if item[0] < STAGE6_VERSION]
        run_migrations(database, prefix, now=_now)
        assert applied_versions(database) == {version for version, _, _ in prefix}
        assert STAGE6_TABLES.isdisjoint(set(database.schema.tables))

        run_migrations(database, migrations, now=_now)
        assert applied_versions(database) == {version for version, _, _ in migrations}
        assert STAGE6_TABLES <= set(database.schema.tables)
        for table_name in sorted(STAGE6_TABLES):
            assert _table_contract(database, table_name) == STAGE6_CONTRACT[table_name]

        assert run_migrations(database, migrations, now=_now) == []
        assert applied_versions(database) == {version for version, _, _ in migrations}
    finally:
        database.close()
