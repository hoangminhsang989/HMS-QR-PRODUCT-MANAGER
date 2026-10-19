"""R010M1 deterministic historical migration boundary regression tests.

The engine runner applies versioned, ordered callables and records each applied
version in ``_hms_migrations``.  There is no downgrade step, so each boundary is
proven by applying migrations one version at a time and asserting the exact
table set, columns, primary keys, foreign keys and unique constraints that
version must produce.
"""

from __future__ import annotations

from pathlib import Path

from config.paths import SOURCE_ROOT
from packages.sqlengine import Database
from packages.sqlengine.migrations import applied_versions, load_migration_modules, run_migrations


REVISIONS = (
    (1, "0001_stage2_baseline"),
    (2, "0002_tracking_qr_reporting"),
    (3, "0003_qc_packing_delivery_events"),
    (4, "0004_managed_files"),
    (5, "0005_store_forward"),
    (6, "0006_outsourced_company"),
    (7, "0007_server_accounts"),
)

VERSION_TABLE = "_hms_migrations"

TABLES_0001 = {
    VERSION_TABLE,
    "customers",
    "delivery_schedule_entries",
    "production_runs",
    "products",
    "purchase_order_lines",
    "purchase_orders",
}
TABLES_0002 = TABLES_0001 | {
    "attempt_display_state",
    "machining_types",
    "operators",
    "order_tracking_items",
    "process_report_events",
    "tracking_audit_events",
    "user_preferences",
}
TABLES_0003 = TABLES_0002 | {"tracking_workflow_events"}
TABLES_0004 = TABLES_0003 | {"managed_files", "product_file_relations"}
TABLES_0005 = TABLES_0004 | {"storage_configurations", "archive_transfer_jobs"}
TABLES_0007 = TABLES_0005 | {"user_accounts", "server_settings"}
TABLES_BY_REVISION = dict(
    zip(
        (version for version, _ in REVISIONS),
        (TABLES_0001, TABLES_0002, TABLES_0003, TABLES_0004, TABLES_0005, TABLES_0005, TABLES_0007),
    )
)

COLUMNS = {
    "products": {"internal_id", "product_code", "company", "part_name", "quantity", "unit", "material", "requester", "surface_treatment", "outsourced", "size", "notes", "delivery_schedule", "status", "created_at", "updated_at", "created_by", "updated_by"},
    "customers": {"internal_id", "customer_code", "name", "short_name", "address", "tax_code", "contact_name", "phone", "email", "notes", "active", "created_at", "updated_at", "created_by", "updated_by"},
    "purchase_orders": {"internal_id", "po_number", "customer_id", "po_date", "requested_delivery_date", "status", "notes", "created_at", "updated_at", "created_by", "updated_by"},
    "purchase_order_lines": {"internal_id", "po_id", "product_id", "line_number", "ordered_quantity", "unit", "unit_price", "currency", "customer_part_reference", "notes"},
    "delivery_schedule_entries": {"internal_id", "po_line_id", "planned_date", "planned_quantity", "status", "notes", "created_at", "updated_at"},
    "production_runs": {"internal_id", "run_code", "po_line_id", "product_id", "planned_quantity", "completed_quantity", "status", "priority", "planned_start", "planned_finish", "actual_start", "actual_finish", "notes", "created_at", "updated_at", "created_by", "updated_by"},
    "order_tracking_items": {"internal_id", "tracking_code", "purchase_order_id", "purchase_order_line_id", "product_id", "customer_id", "quantity", "unit", "delivery_date", "status", "qr_public_id", "qr_status", "created_at", "updated_at", "created_by", "updated_by"},
    "operators": {"internal_id", "display_name", "active", "created_at", "updated_at"},
    "machining_types": {"internal_id", "code", "display_name", "active", "display_order"},
    "user_preferences": {"user_id", "machining_type_id", "updated_at"},
    "attempt_display_state": {"tracking_item_id", "machining_type_id", "max_visible_attempt", "updated_at", "updated_by"},
    "process_report_events": {"internal_id", "request_id", "tracking_item_id", "machining_type_id", "kind", "attempt_number", "quantity", "notes", "actor_user_id", "actor_display_name_snapshot", "server_timestamp", "client_timestamp", "device_id", "revision", "supersedes_id", "status"},
    "tracking_audit_events": {"internal_id", "tracking_item_id", "event_type", "old_value", "new_value", "actor", "reason", "server_timestamp"},
    "tracking_workflow_events": {"internal_id", "request_id", "tracking_item_id", "event_type", "quantity", "notes", "machining_type_id", "process_report_id", "actor_user_id", "actor_display_name_snapshot", "server_timestamp", "client_timestamp", "device_id", "sequence_number", "revision", "supersedes_event_id", "status"},
    "managed_files": {"internal_id", "original_filename", "stored_filename", "storage_key", "category", "media_type", "extension", "size_bytes", "sha256", "status", "source", "version", "created_at", "created_by", "updated_at", "replaced_file_id", "archived_at", "archived_by", "failure_reason"},
    "product_file_relations": {"internal_id", "product_id", "managed_file_id", "kind", "attachment_category", "is_primary", "sort_order", "caption", "created_at", "archived_at"},
    "storage_configurations": {"internal_id", "local_ingest_root", "archive_target_root", "grace_period_hours", "retry_schedule_seconds", "warning_free_bytes", "critical_free_bytes", "upload_refusal_free_bytes", "active", "created_at", "updated_at"},
    "archive_transfer_jobs": {"internal_id", "managed_file_id", "configuration_id", "state", "attempt_count", "next_retry_at", "last_attempt_at", "last_error_code", "last_error_summary", "remote_verified_at", "grace_expires_at", "local_purged_at", "lease_token", "lease_expires_at", "created_at", "updated_at"},
    "user_accounts": {"internal_id", "username", "password_hash", "role", "active", "created_at", "updated_at"},
    "server_settings": {"setting_key", "setting_value", "updated_at"},
}

PRIMARY_KEYS = {
    table: ("internal_id",)
    for table in COLUMNS
    if table not in {"user_preferences", "attempt_display_state"}
}
PRIMARY_KEYS.update({
    "user_preferences": ("user_id",),
    "attempt_display_state": ("tracking_item_id", "machining_type_id"),
    "server_settings": ("setting_key",),
})

FOREIGN_KEY_COUNTS = {
    "products": 0, "customers": 0, "purchase_orders": 1,
    "purchase_order_lines": 2, "delivery_schedule_entries": 1,
    "production_runs": 2, "operators": 0, "machining_types": 0,
    "order_tracking_items": 4, "user_preferences": 2,
    "attempt_display_state": 2, "process_report_events": 4,
    "tracking_audit_events": 1, "tracking_workflow_events": 5,
    "managed_files": 1, "product_file_relations": 2,
    "storage_configurations": 0, "archive_transfer_jobs": 2,
    "user_accounts": 0, "server_settings": 0,
}

UNIQUE_SETS = {
    "products": {("product_code",)},
    "customers": {("customer_code",)},
    "purchase_orders": {("po_number",)},
    "purchase_order_lines": {("po_id", "line_number")},
    "production_runs": {("run_code",)},
    "order_tracking_items": {("qr_public_id",), ("tracking_code",)},
    "machining_types": {("code",)},
    "process_report_events": {("request_id",)},
    "tracking_workflow_events": {("request_id",), ("tracking_item_id", "sequence_number", "revision")},
    "managed_files": {("storage_key",)},
    "product_file_relations": {("managed_file_id",)},
    "archive_transfer_jobs": {("managed_file_id",)},
    "user_accounts": {("username",)},
}


def _migrations():
    return load_migration_modules(SOURCE_ROOT / "migrations" / "engine")


def _now() -> str:
    return "2026-01-01T00:00:00+00:00"


def _uniques(table) -> set[tuple[str, ...]]:
    result = {tuple(constraint) for constraint in table.unique_constraints}
    result.update(
        (column.name,) for column in table.columns if column.unique and not column.primary_key
    )
    return result


def _assert_boundary(database: Database, version: int) -> None:
    expected_tables = TABLES_BY_REVISION[version]
    assert set(database.schema.tables) == expected_tables
    for table_name in expected_tables - {VERSION_TABLE}:
        table = database.schema.table(table_name)
        expected_columns = set(COLUMNS[table_name])
        if table_name == "products" and version >= 6:
            expected_columns.add("outsourced_company")
        if table_name == "purchase_orders" and version != 1:
            expected_columns.add("internal_order_code")
        assert {column.name for column in table.columns} == expected_columns
        assert tuple(table.primary_key) == PRIMARY_KEYS[table_name]
        assert len(table.foreign_keys) == FOREIGN_KEY_COUNTS[table_name]
        expected_uniques = set(UNIQUE_SETS.get(table_name, set()))
        if table_name == "purchase_orders" and version != 1:
            expected_uniques.add(("internal_order_code",))
        assert _uniques(table) == expected_uniques


def test_revision_graph_is_deterministic():
    migrations = _migrations()
    assert [version for version, _, _ in migrations] == [version for version, _ in REVISIONS]
    assert [name for _, name, _ in migrations] == [name for _, name in REVISIONS]

    root = SOURCE_ROOT / "migrations" / "engine"
    for _, name in REVISIONS:
        source = (root / f"{name}.py").read_text(encoding="utf-8")
        assert "packages.persistence" not in source


def test_engine_boundaries_apply_one_version_at_a_time(tmp_path: Path):
    migrations = _migrations()
    database = Database(tmp_path / "r010m1-boundaries-engine")
    try:
        for version, _name in REVISIONS:
            single = [item for item in migrations if item[0] == version]
            assert run_migrations(database, single, now=_now) == [version]
            assert applied_versions(database) == {
                applied for applied, _ in REVISIONS if applied <= version
            }
            _assert_boundary(database, version)

        assert run_migrations(database, migrations, now=_now) == []
        _assert_boundary(database, 7)
    finally:
        database.close()


def test_engine_head_schema_is_reproducible_from_scratch(tmp_path: Path):
    migrations = _migrations()
    first = Database(tmp_path / "head-a-engine")
    second = Database(tmp_path / "head-b-engine")
    try:
        run_migrations(first, migrations, now=_now)
        run_migrations(second, migrations, now=_now)
        assert first.schema.to_dict() == second.schema.to_dict()
        assert applied_versions(first) == applied_versions(second) == {
            version for version, _, _ in migrations
        }
    finally:
        first.close()
        second.close()
