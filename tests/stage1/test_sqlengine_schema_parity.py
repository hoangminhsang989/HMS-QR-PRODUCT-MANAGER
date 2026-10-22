"""Schema contract: the engine migrations must reproduce the frozen ORM contract.

This was the cutover gate.  It ran the eight engine migrations against a fresh
database and compared the result, table by table, against the SQLAlchemy ORM
metadata the application used at cutover.  The ORM models are gone now, so the
expected contract is frozen here as a literal: any future migration that
changes a column name, type, nullability, primary key, unique constraint or
foreign key must update this file deliberately, in the same commit.

Indexes are intentionally excluded: the engine scans rows in memory and needs
no indexes for correctness.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from config.paths import SOURCE_ROOT
from packages.sqlengine import connect
from packages.sqlengine.migrations import applied_versions, load_migration_modules, run_migrations

MIGRATION_DIRECTORY = SOURCE_ROOT / "migrations" / "engine"

EXPECTED_TABLES = {
    "archive_transfer_jobs": {
        "columns": (
            ('attempt_count', 'INTEGER', False),
            ('configuration_id', 'TEXT', False),
            ('created_at', 'DATETIME', False),
            ('grace_expires_at', 'DATETIME', True),
            ('internal_id', 'TEXT', False),
            ('last_attempt_at', 'DATETIME', True),
            ('last_error_code', 'TEXT', True),
            ('last_error_summary', 'TEXT', True),
            ('lease_expires_at', 'DATETIME', True),
            ('lease_token', 'TEXT', True),
            ('local_purged_at', 'DATETIME', True),
            ('managed_file_id', 'TEXT', False),
            ('next_retry_at', 'DATETIME', True),
            ('remote_verified_at', 'DATETIME', True),
            ('state', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('managed_file_id',),
        ),
        "fk": (
            ('configuration_id', 'storage_configurations', 'internal_id'),
            ('managed_file_id', 'managed_files', 'internal_id'),
        ),
    },
    "attempt_display_state": {
        "columns": (
            ('machining_type_id', 'TEXT', False),
            ('max_visible_attempt', 'INTEGER', False),
            ('tracking_item_id', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
            ('updated_by', 'TEXT', True),
        ),
        "pk": ['tracking_item_id', 'machining_type_id'],
        "unique": (
        ),
        "fk": (
            ('machining_type_id', 'machining_types', 'internal_id'),
            ('tracking_item_id', 'order_tracking_items', 'internal_id'),
        ),
    },
    "customers": {
        "columns": (
            ('active', 'BOOLEAN', False),
            ('address', 'TEXT', True),
            ('contact_name', 'TEXT', True),
            ('created_at', 'DATETIME', False),
            ('created_by', 'TEXT', False),
            ('customer_code', 'TEXT', False),
            ('email', 'TEXT', True),
            ('internal_id', 'TEXT', False),
            ('name', 'TEXT', False),
            ('notes', 'TEXT', True),
            ('phone', 'TEXT', True),
            ('short_name', 'TEXT', True),
            ('tax_code', 'TEXT', True),
            ('updated_at', 'DATETIME', False),
            ('updated_by', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('customer_code',),
        ),
        "fk": (
        ),
    },
    "delivery_schedule_entries": {
        "columns": (
            ('created_at', 'DATETIME', False),
            ('internal_id', 'TEXT', False),
            ('notes', 'TEXT', True),
            ('planned_date', 'DATE', False),
            ('planned_quantity', 'NUMERIC(18,4)', False),
            ('po_line_id', 'TEXT', False),
            ('status', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
        ),
        "pk": ['internal_id'],
        "unique": (
        ),
        "fk": (
            ('po_line_id', 'purchase_order_lines', 'internal_id'),
        ),
    },
    "machining_types": {
        "columns": (
            ('active', 'BOOLEAN', False),
            ('code', 'TEXT', False),
            ('display_name', 'TEXT', False),
            ('display_order', 'INTEGER', False),
            ('internal_id', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('code',),
        ),
        "fk": (
        ),
    },
    "managed_files": {
        "columns": (
            ('archived_at', 'DATETIME', True),
            ('archived_by', 'TEXT', True),
            ('category', 'TEXT', False),
            ('created_at', 'DATETIME', False),
            ('created_by', 'TEXT', False),
            ('extension', 'TEXT', False),
            ('failure_reason', 'TEXT', True),
            ('internal_id', 'TEXT', False),
            ('media_type', 'TEXT', False),
            ('original_filename', 'TEXT', False),
            ('replaced_file_id', 'TEXT', True),
            ('sha256', 'TEXT', False),
            ('size_bytes', 'INTEGER', False),
            ('source', 'TEXT', False),
            ('status', 'TEXT', False),
            ('storage_key', 'TEXT', False),
            ('stored_filename', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
            ('version', 'INTEGER', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('storage_key',),
        ),
        "fk": (
            ('replaced_file_id', 'managed_files', 'internal_id'),
        ),
    },
    "operators": {
        "columns": (
            ('active', 'BOOLEAN', False),
            ('created_at', 'DATETIME', False),
            ('display_name', 'TEXT', False),
            ('internal_id', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
        ),
        "pk": ['internal_id'],
        "unique": (
        ),
        "fk": (
        ),
    },
    "order_tracking_items": {
        "columns": (
            ('created_at', 'DATETIME', False),
            ('created_by', 'TEXT', False),
            ('customer_id', 'TEXT', False),
            ('delivery_date', 'DATE', False),
            ('internal_id', 'TEXT', False),
            ('product_id', 'TEXT', False),
            ('purchase_order_id', 'TEXT', False),
            ('purchase_order_line_id', 'TEXT', False),
            ('qr_public_id', 'TEXT', True),
            ('qr_status', 'TEXT', True),
            ('quantity', 'NUMERIC(18,4)', False),
            ('status', 'TEXT', False),
            ('tracking_code', 'TEXT', False),
            ('unit', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
            ('updated_by', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('qr_public_id',),
            ('tracking_code',),
        ),
        "fk": (
            ('customer_id', 'customers', 'internal_id'),
            ('product_id', 'products', 'internal_id'),
            ('purchase_order_id', 'purchase_orders', 'internal_id'),
            ('purchase_order_line_id', 'purchase_order_lines', 'internal_id'),
        ),
    },
    "process_report_events": {
        "columns": (
            ('actor_display_name_snapshot', 'TEXT', False),
            ('actor_user_id', 'TEXT', False),
            ('attempt_number', 'INTEGER', True),
            ('client_timestamp', 'DATETIME', True),
            ('device_id', 'TEXT', True),
            ('internal_id', 'TEXT', False),
            ('kind', 'TEXT', False),
            ('machining_type_id', 'TEXT', False),
            ('notes', 'TEXT', True),
            ('quantity', 'NUMERIC(18,4)', False),
            ('request_id', 'TEXT', False),
            ('revision', 'INTEGER', False),
            ('server_timestamp', 'DATETIME', False),
            ('status', 'TEXT', False),
            ('supersedes_id', 'TEXT', True),
            ('tracking_item_id', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('request_id',),
        ),
        "fk": (
            ('actor_user_id', 'operators', 'internal_id'),
            ('machining_type_id', 'machining_types', 'internal_id'),
            ('supersedes_id', 'process_report_events', 'internal_id'),
            ('tracking_item_id', 'order_tracking_items', 'internal_id'),
        ),
    },
    "product_file_relations": {
        "columns": (
            ('archived_at', 'DATETIME', True),
            ('attachment_category', 'TEXT', True),
            ('caption', 'TEXT', True),
            ('created_at', 'DATETIME', False),
            ('internal_id', 'TEXT', False),
            ('is_primary', 'BOOLEAN', False),
            ('kind', 'TEXT', False),
            ('managed_file_id', 'TEXT', False),
            ('product_id', 'TEXT', False),
            ('sort_order', 'INTEGER', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('managed_file_id',),
        ),
        "fk": (
            ('managed_file_id', 'managed_files', 'internal_id'),
            ('product_id', 'products', 'internal_id'),
        ),
    },
    "production_runs": {
        "columns": (
            ('actual_finish', 'DATE', True),
            ('actual_start', 'DATE', True),
            ('completed_quantity', 'NUMERIC(18,4)', False),
            ('created_at', 'DATETIME', False),
            ('created_by', 'TEXT', False),
            ('internal_id', 'TEXT', False),
            ('notes', 'TEXT', True),
            ('planned_finish', 'DATE', True),
            ('planned_quantity', 'NUMERIC(18,4)', False),
            ('planned_start', 'DATE', True),
            ('po_line_id', 'TEXT', False),
            ('priority', 'INTEGER', False),
            ('product_id', 'TEXT', False),
            ('run_code', 'TEXT', False),
            ('status', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
            ('updated_by', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('run_code',),
        ),
        "fk": (
            ('po_line_id', 'purchase_order_lines', 'internal_id'),
            ('product_id', 'products', 'internal_id'),
        ),
    },
    "products": {
        "columns": (
            ('company', 'TEXT', False),
            ('created_at', 'DATETIME', True),
            ('created_by', 'TEXT', True),
            ('delivery_schedule', 'DATE', True),
            ('internal_id', 'TEXT', False),
            ('material', 'TEXT', True),
            ('notes', 'TEXT', True),
            ('outsourced', 'BOOLEAN', False),
            ('outsourced_company', 'TEXT', True),
            ('part_name', 'TEXT', False),
            ('product_code', 'TEXT', False),
            ('quantity', 'NUMERIC(18,4)', False),
            ('requester', 'TEXT', True),
            ('size', 'TEXT', True),
            ('status', 'TEXT', False),
            ('surface_treatment', 'TEXT', True),
            ('unit', 'TEXT', False),
            ('updated_at', 'DATETIME', True),
            ('updated_by', 'TEXT', True),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('product_code',),
        ),
        "fk": (
        ),
    },
    "purchase_order_lines": {
        "columns": (
            ('currency', 'TEXT', True),
            ('customer_part_reference', 'TEXT', True),
            ('internal_id', 'TEXT', False),
            ('line_number', 'INTEGER', False),
            ('notes', 'TEXT', True),
            ('ordered_quantity', 'NUMERIC(18,4)', False),
            ('po_id', 'TEXT', False),
            ('product_id', 'TEXT', False),
            ('unit', 'TEXT', False),
            ('unit_price', 'NUMERIC(18,4)', True),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('po_id', 'line_number'),
        ),
        "fk": (
            ('po_id', 'purchase_orders', 'internal_id'),
            ('product_id', 'products', 'internal_id'),
        ),
    },
    "purchase_orders": {
        "columns": (
            ('created_at', 'DATETIME', False),
            ('created_by', 'TEXT', False),
            ('customer_id', 'TEXT', False),
            ('internal_id', 'TEXT', False),
            ('internal_order_code', 'TEXT', True),
            ('notes', 'TEXT', True),
            ('po_date', 'DATE', False),
            ('po_number', 'TEXT', False),
            ('requested_delivery_date', 'DATE', True),
            ('status', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
            ('updated_by', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('internal_order_code',),
            ('po_number',),
        ),
        "fk": (
            ('customer_id', 'customers', 'internal_id'),
        ),
    },
    "server_settings": {
        "columns": (
            ('setting_key', 'TEXT', False),
            ('setting_value', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
        ),
        "pk": ['setting_key'],
        "unique": (
        ),
        "fk": (
        ),
    },
    "storage_configurations": {
        "columns": (
            ('active', 'BOOLEAN', False),
            ('archive_target_root', 'TEXT', False),
            ('created_at', 'DATETIME', False),
            ('critical_free_bytes', 'INTEGER', False),
            ('grace_period_hours', 'INTEGER', False),
            ('internal_id', 'TEXT', False),
            ('local_ingest_root', 'TEXT', False),
            ('retry_schedule_seconds', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
            ('upload_refusal_free_bytes', 'INTEGER', False),
            ('warning_free_bytes', 'INTEGER', False),
        ),
        "pk": ['internal_id'],
        "unique": (
        ),
        "fk": (
        ),
    },
    "tracking_audit_events": {
        "columns": (
            ('actor', 'TEXT', False),
            ('event_type', 'TEXT', False),
            ('internal_id', 'TEXT', False),
            ('new_value', 'TEXT', True),
            ('old_value', 'TEXT', True),
            ('reason', 'TEXT', True),
            ('server_timestamp', 'DATETIME', False),
            ('tracking_item_id', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
        ),
        "fk": (
            ('tracking_item_id', 'order_tracking_items', 'internal_id'),
        ),
    },
    "tracking_workflow_events": {
        "columns": (
            ('actor_display_name_snapshot', 'TEXT', False),
            ('actor_user_id', 'TEXT', False),
            ('client_timestamp', 'DATETIME', True),
            ('device_id', 'TEXT', True),
            ('event_type', 'TEXT', False),
            ('internal_id', 'TEXT', False),
            ('machining_type_id', 'TEXT', True),
            ('notes', 'TEXT', True),
            ('process_report_id', 'TEXT', True),
            ('quantity', 'NUMERIC(18,4)', True),
            ('request_id', 'TEXT', False),
            ('revision', 'INTEGER', False),
            ('sequence_number', 'INTEGER', False),
            ('server_timestamp', 'DATETIME', False),
            ('status', 'TEXT', False),
            ('supersedes_event_id', 'TEXT', True),
            ('tracking_item_id', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('request_id',),
            ('tracking_item_id', 'sequence_number', 'revision'),
        ),
        "fk": (
            ('actor_user_id', 'operators', 'internal_id'),
            ('machining_type_id', 'machining_types', 'internal_id'),
            ('process_report_id', 'process_report_events', 'internal_id'),
            ('supersedes_event_id', 'tracking_workflow_events', 'internal_id'),
            ('tracking_item_id', 'order_tracking_items', 'internal_id'),
        ),
    },
    "user_accounts": {
        "columns": (
            ('active', 'BOOLEAN', False),
            ('created_at', 'DATETIME', False),
            ('internal_id', 'TEXT', False),
            ('password_hash', 'TEXT', False),
            ('role', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
            ('username', 'TEXT', False),
        ),
        "pk": ['internal_id'],
        "unique": (
            ('username',),
        ),
        "fk": (
        ),
    },
    "user_preferences": {
        "columns": (
            ('machining_type_id', 'TEXT', False),
            ('updated_at', 'DATETIME', False),
            ('user_id', 'TEXT', False),
        ),
        "pk": ['user_id'],
        "unique": (
        ),
        "fk": (
            ('machining_type_id', 'machining_types', 'internal_id'),
            ('user_id', 'operators', 'internal_id'),
        ),
    },
    "license_keys": {
        "columns": (
            ('activated_at', 'DATETIME', True),
            ('created_at', 'DATETIME', False),
            ('customer_email', 'TEXT', True),
            ('expires_at', 'DATETIME', True),
            ('hwid', 'TEXT', True),
            ('key_id', 'TEXT', False),
            ('license_key', 'TEXT', False),
            ('payment_id', 'TEXT', True),
            ('product_tier', 'TEXT', False),
            ('status', 'TEXT', False),
        ),
        "pk": ['key_id'],
        "unique": (
            ('license_key',),
        ),
        "fk": (
        ),
    },
    "payments": {
        "columns": (
            ('amount', 'INTEGER', False),
            ('confirmed_at', 'DATETIME', True),
            ('created_at', 'DATETIME', False),
            ('currency', 'TEXT', False),
            ('customer_email', 'TEXT', True),
            ('payment_id', 'TEXT', False),
            ('qr_payload', 'TEXT', True),
            ('status', 'TEXT', False),
            ('vietqr_reference', 'TEXT', True),
            ('webhook_payload', 'TEXT', True),
        ),
        "pk": ['payment_id'],
        "unique": (
        ),
        "fk": (
        ),
    },
}

def _build_database(tmp_path: Path):
    database = connect(tmp_path / "engine-db")
    migrations = load_migration_modules(MIGRATION_DIRECTORY)
    run_migrations(database, migrations, now=lambda: "2026-10-18T00:00:00Z")
    return database, migrations


@pytest.fixture(scope="module")
def engine_schema(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("engine-parity")
    database, migrations = _build_database(tmp_path)
    yield database, migrations
    database.close()


def test_all_eight_migrations_apply(engine_schema):
    database, migrations = engine_schema
    assert [version for version, _, _ in migrations] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert applied_versions(database) == {1, 2, 3, 4, 5, 6, 7, 8}


def test_table_set_matches_the_frozen_contract(engine_schema):
    database, _ = engine_schema
    actual = set(database.table_names()) - {"_hms_migrations"}
    assert actual == set(EXPECTED_TABLES)


def test_every_table_matches_its_frozen_contract(engine_schema):
    database, _ = engine_schema
    for name, expected in sorted(EXPECTED_TABLES.items()):
        table = database.schema.table(name)
        # Column order is not part of the data contract: repositories address
        # columns by name, and migration 0006 appends a column the baseline
        # did not declare.  Names, types, and nullability must match exactly.
        assert {column.name for column in table.columns} == {
            column[0] for column in expected["columns"]
        }, name

        for column_name, type_name, nullable in expected["columns"]:
            engine_column = table.column(column_name)
            assert engine_column.type.name == type_name, f"{name}.{column_name}"
            assert engine_column.nullable == nullable, f"{name}.{column_name}"

        assert list(table.primary_key) == expected["pk"], name

        actual_unique = {tuple(constraint) for constraint in table.unique_constraints}
        actual_unique.update(
            (column.name,)
            for column in table.columns
            if column.unique and not column.primary_key
        )
        assert actual_unique == {tuple(item) for item in expected["unique"]}, name

        actual_fk = {
            (foreign_key.column, foreign_key.target_table, foreign_key.target_column)
            for foreign_key in table.foreign_keys
        }
        assert actual_fk == {tuple(item) for item in expected["fk"]}, name


def test_schema_survives_reopen(engine_schema):
    database, _ = engine_schema
    database.close()
    reopened = connect(database.path)
    assert set(reopened.table_names()) - {"_hms_migrations"} == set(EXPECTED_TABLES)
    assert applied_versions(reopened) == {1, 2, 3, 4, 5, 6, 7, 8}