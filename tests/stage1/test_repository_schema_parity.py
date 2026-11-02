"""The DEV/test adapter's hand-written schema must match what the migrations build.

Two implementations of ``ProductRepository`` run against the same engine:

- ``EngineProductRepository`` — production. Its schema comes from
  ``migrations/engine/*.py``, seven versioned migrations, and it passes native
  Python types (``Decimal``, ``bool``, ``date``) straight to the engine.
- ``SQLiteProductRepository`` — the adapter stage1 tests use. It bootstraps its
  own two tables by hand in ``_initialize()`` and pre-stringifies every value.

``tests/stage1/test_sqlengine_schema_parity.py`` compares the migrations against
a frozen ORM contract, and ``test_r010r2_database_runtime.py`` proves the engine
round-trips native types. Nothing compared the adapter's hand-written schema to
the migration-produced one. That is the quiet direction of drift: a column added
to the adapter but not to a migration makes stage1 tests pass against a schema
production never has, and the loud direction - a NOT NULL column only the
migrations have - surfaces as a confusing INSERT failure in stage1 rather than
as a schema mismatch.

So this test builds both schemas with the engine itself and compares them.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from config.paths import SOURCE_ROOT
from packages.domain.product import Product, ProductStatus
from packages.persistence.engine_product_repository import EngineProductRepository
from packages.persistence.sqlite_product_repository import SQLiteProductRepository
from packages.sqlengine import Database
from packages.sqlengine.migrations import load_migration_modules, run_migrations

TYPED_COLUMNS = ("quantity", "outsourced", "delivery_schedule")


def _migrated_schema(tmp_path: Path) -> dict[str, tuple[str, bool]]:
    """The products table as the seven engine migrations leave it."""
    database = Database(tmp_path / "migrated-engine")
    try:
        run_migrations(
            database,
            load_migration_modules(SOURCE_ROOT / "migrations" / "engine"),
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        return {
            column.name: (str(column.type), column.nullable)
            for column in database.schema.table("products").columns
        }
    finally:
        database.close()


def _adapter_schema(tmp_path: Path) -> dict[str, tuple[str, bool]]:
    """The products table as the adapter's hand-written bootstrap leaves it."""
    database_path = tmp_path / "adapter" / "adapter.sqlite"
    SQLiteProductRepository(database_path)
    database = Database(database_path.with_name(database_path.stem + "-engine"))
    try:
        return {
            column.name: (str(column.type), column.nullable)
            for column in database.schema.table("products").columns
        }
    finally:
        database.close()


def _describe(schema: dict[str, tuple[str, bool]], name: str) -> str:
    column_type, nullable = schema[name]
    return f"{column_type}{'' if nullable else ' NOT NULL'}"


def test_the_adapter_schema_matches_the_migration_schema(tmp_path):
    migrated = _migrated_schema(tmp_path)
    adapter = _adapter_schema(tmp_path)

    only_in_adapter = sorted(set(adapter) - set(migrated))
    assert not only_in_adapter, (
        "SQLiteProductRepository bootstraps columns the migrations do not "
        "create, so stage1 tests run against a schema production never has: "
        + ", ".join(only_in_adapter)
    )

    only_in_migrations = sorted(set(migrated) - set(adapter))
    assert not only_in_migrations, (
        "the migrations create columns the adapter does not bootstrap, so "
        "stage1 tests cannot produce rows production can: "
        + ", ".join(only_in_migrations)
    )

    differing = {
        name: (adapter[name], migrated[name])
        for name in sorted(set(adapter) & set(migrated))
        if adapter[name] != migrated[name]
    }
    assert not differing, (
        "the adapter's products table differs from the one the migrations "
        "build, so stage1 tests run against a schema production never has:\n"
        + "\n".join(
            f"  {name}: adapter={_describe(adapter, name)} "
            f"migrations={_describe(migrated, name)}"
            for name in differing
        )
    )


@pytest.mark.parametrize("column", TYPED_COLUMNS)
def test_the_adapter_stores_the_same_type_the_migrations_declare(tmp_path, column):
    """Type parity on the columns the two adapters write differently.

    ``EngineProductRepository`` hands the engine a ``Decimal``, a ``bool`` and a
    ``date``; the adapter hands it ``str``, ``int`` and an ISO string. Both land
    in the same column, so the column has to accept both shapes.
    """
    migrated = _migrated_schema(tmp_path)
    adapter = _adapter_schema(tmp_path)

    assert adapter.get(column) == migrated.get(column), (
        f"{column} is {_describe(adapter, column)} in the adapter but "
        f"{_describe(migrated, column)} in the migrations"
    )


def test_a_product_survives_the_adapter_and_the_migrations_identically(tmp_path):
    """The same Product, written through both adapters, reads back the same.

    This is the behavioural half: type parity on paper is not proof the values
    survive. ``test_r010r2_database_runtime.py`` already proves the engine
    round-trips native types; this proves the adapter's stringified values land
    in the same place and read back as the same Python objects.
    """
    product = Product(
        uuid4(), "PAR-0001", "Parity Co", "Parity part", Decimal("12.3400"), "cai",
        "steel", "requester", "none", True, "10x10", None, date(2026, 3, 4),
        ProductStatus.IN_PROGRESS, datetime(2026, 1, 1, 8, 0, 0),
        datetime(2026, 1, 1, 8, 0, 0), "parity-actor", "parity-actor", "Outsource Ltd",
    )

    adapter_path = tmp_path / "roundtrip" / "adapter.sqlite"
    adapter = SQLiteProductRepository(adapter_path)
    adapter.create(product)
    from_adapter = adapter.get_by_code("PAR-0001")

    migrated = Database(tmp_path / "roundtrip" / "migrated-engine")
    try:
        run_migrations(
            migrated,
            load_migration_modules(SOURCE_ROOT / "migrations" / "engine"),
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        from config.environments import AppConfig, Environment
        from packages.persistence.database import DatabaseRuntime

        runtime = DatabaseRuntime(
            AppConfig(Environment.PROD, "postgresql+psycopg://u:p@localhost/hms_qr", "nas"),
            migrated,
            getattr(migrated, "path", None),
        )
        engine = EngineProductRepository(runtime)
        engine.create(product)
        from_migrations = engine.get_by_code("PAR-0001")
    finally:
        migrated.close()

    assert from_adapter.quantity == from_migrations.quantity
    assert from_adapter.outsourced == from_migrations.outsourced
    assert from_adapter.delivery_schedule == from_migrations.delivery_schedule
    assert from_adapter.status == from_migrations.status
    assert from_adapter.outsourced_company == from_migrations.outsourced_company
