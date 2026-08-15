"""R010M1 deterministic historical migration boundary regression tests."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect, text

# Deliberately pre-import every current ORM module before Alembic loads 0001.
# Historical revision behavior must remain independent of this registry.
from packages.persistence.sqlalchemy_models import Base
from packages.persistence import storage_models as _storage_models  # noqa: F401
from packages.persistence import store_forward_models as _store_forward_models  # noqa: F401
from packages.persistence import tracking_models as _tracking_models  # noqa: F401


REVISIONS = (
    "0001_stage2_baseline",
    "0002_tracking_qr_reporting",
    "0003_qc_packing_delivery",
    "0004_managed_files",
    "0005_store_forward",
)

TABLES_0001 = {
    "alembic_version",
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
TABLES_BY_REVISION = dict(zip(REVISIONS, (TABLES_0001, TABLES_0002, TABLES_0003, TABLES_0004, TABLES_0005)))

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
}

PRIMARY_KEYS = {
    table: ("internal_id",)
    for table in COLUMNS
    if table not in {"user_preferences", "attempt_display_state"}
}
PRIMARY_KEYS.update({
    "user_preferences": ("user_id",),
    "attempt_display_state": ("tracking_item_id", "machining_type_id"),
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
}

NON_UNIQUE_INDEXES = {
    "tracking_workflow_events": {("event_type",), ("tracking_item_id",)},
    "managed_files": {("sha256",), ("status",)},
    "product_file_relations": {("product_id",)},
    "storage_configurations": {("active",)},
    "archive_transfer_jobs": {("configuration_id",), ("state",), ("next_retry_at",), ("grace_expires_at",), ("lease_token",), ("lease_expires_at",)},
}


def _config(url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _snapshot(url: str) -> dict[str, dict[str, object]]:
    engine = create_engine(url)
    inspector = inspect(engine)
    snapshot: dict[str, dict[str, object]] = {}
    for table in sorted(inspector.get_table_names()):
        snapshot[table] = {
            "columns": tuple(sorted(
                (column["name"], str(column["type"]), column["nullable"], column.get("default"), column.get("primary_key", 0))
                for column in inspector.get_columns(table)
            )),
            "pk": tuple(inspector.get_pk_constraint(table).get("constrained_columns") or ()),
            "fks": tuple(sorted(
                (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
                for fk in inspector.get_foreign_keys(table)
            )),
            "uniques": tuple(sorted(
                tuple(unique["column_names"])
                for unique in inspector.get_unique_constraints(table)
                if unique.get("column_names")
            )),
            "indexes": tuple(sorted(
                (tuple(index["column_names"]), bool(index["unique"]))
                for index in inspector.get_indexes(table)
            )),
        }
    engine.dispose()
    return snapshot


def _assert_boundary(url: str, revision: str) -> dict[str, dict[str, object]]:
    snapshot = _snapshot(url)
    assert set(snapshot) == TABLES_BY_REVISION[revision]
    for table in TABLES_BY_REVISION[revision] - {"alembic_version"}:
        expected_columns = set(COLUMNS[table])
        if table == "purchase_orders" and revision != "0001_stage2_baseline":
            expected_columns.add("internal_order_code")
        assert {column[0] for column in snapshot[table]["columns"]} == expected_columns
        assert snapshot[table]["pk"] == PRIMARY_KEYS[table]
        assert len(snapshot[table]["fks"]) == FOREIGN_KEY_COUNTS[table]
        expected_uniques = set(UNIQUE_SETS.get(table, set()))
        if table == "purchase_orders" and revision != "0001_stage2_baseline":
            expected_uniques.add(("internal_order_code",))
        assert set(snapshot[table]["uniques"]) == expected_uniques
        actual_indexes = {columns for columns, unique in snapshot[table]["indexes"] if not unique}
        assert actual_indexes == NON_UNIQUE_INDEXES.get(table, set())
    return snapshot


def _reset_postgresql(url: str) -> None:
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def _postgresql_url() -> str:
    value = os.environ.get("HMS_QR_R010M1_POSTGRESQL_URL", "").strip()
    if not value:
        pytest.skip("isolated R010M1 PostgreSQL runtime is not configured")
    return value


def _exercise_full_traversal(url: str) -> None:
    config = _config(url)
    head_snapshot = None
    for revision in REVISIONS:
        command.upgrade(config, revision)
        current = _assert_boundary(url, revision)
        if revision == "0001_stage2_baseline":
            assert "internal_order_code" not in COLUMNS["purchase_orders"]
        if revision == "0005_store_forward":
            head_snapshot = current

    command.upgrade(config, "head")
    assert _snapshot(url) == head_snapshot

    for revision in reversed(REVISIONS[:-1]):
        command.downgrade(config, revision)
        _assert_boundary(url, revision)
    command.downgrade(config, "base")
    assert set(_snapshot(url)) <= {"alembic_version"}

    command.upgrade(config, "head")
    assert _snapshot(url) == head_snapshot


def test_revision_graph_and_historical_sources_are_deterministic():
    config = _config("sqlite://")
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["0005_store_forward"]
    assert [revision.revision for revision in scripts.walk_revisions(base="base", head="heads")][::-1] == list(REVISIONS)

    root = Path("migrations/versions")
    for name in (
        "0001_stage2_baseline.py",
        "0002_tracking_qr_reporting.py",
        "0003_qc_packing_delivery_events.py",
    ):
        source = (root / name).read_text(encoding="utf-8")
        assert "Base.metadata" not in source
        assert "packages.persistence" not in source


def test_sqlite_boundaries_downgrade_reupgrade_and_existing_head_noop(tmp_path):
    url = f"sqlite:///{(tmp_path / 'r010m1-boundaries.sqlite').as_posix()}"
    _exercise_full_traversal(url)


def test_postgresql_boundaries_downgrade_reupgrade_and_future_model_preimport():
    url = _postgresql_url()
    _reset_postgresql(url)
    _exercise_full_traversal(url)


def _assert_head_matches_current_orm(url: str, *, reset) -> None:
    reset(url)
    command.upgrade(_config(url), "head")
    migrated = _snapshot(url)
    reset(url)
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    orm = _snapshot(url)
    migrated.pop("alembic_version", None)
    assert migrated == orm


def test_sqlite_head_schema_matches_current_orm(tmp_path):
    path = tmp_path / "r010m1-head.sqlite"
    url = f"sqlite:///{path.as_posix()}"

    def reset(_url):
        path.unlink(missing_ok=True)

    _assert_head_matches_current_orm(url, reset=reset)


def test_postgresql_head_schema_matches_current_orm():
    url = _postgresql_url()
    _assert_head_matches_current_orm(url, reset=_reset_postgresql)
