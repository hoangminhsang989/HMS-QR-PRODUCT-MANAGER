"""R010M1A1 partial-history forward-compatibility tests for the SQL engine.

The engine runner applies versioned callables inside one transaction per
migration, so a partial history converges to head exactly once and a failing
step leaves the database untouched.  These tests prove that with real seeded
rows: apply a prefix, seed every legacy table, apply the remainder, and require
the rows and the schema to survive unchanged.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

from config.paths import SOURCE_ROOT
from packages.sqlengine import Database
from packages.sqlengine.errors import ExecutionError
from packages.sqlengine.migrations import applied_versions, load_migration_modules, run_migrations


PARTIAL_REVISIONS = (1, 2, 3)

LEGACY_TABLES = (
    "products",
    "customers",
    "purchase_orders",
    "purchase_order_lines",
    "delivery_schedule_entries",
    "production_runs",
    "operators",
    "machining_types",
    "order_tracking_items",
    "user_preferences",
    "attempt_display_state",
    "process_report_events",
    "tracking_audit_events",
    "tracking_workflow_events",
)

HEAD_VERSION = 7


def _migrations():
    return load_migration_modules(SOURCE_ROOT / "migrations" / "engine")


def _now() -> str:
    return "2026-01-01T00:00:00+00:00"


def _uuid(number: int) -> str:
    return f"00000000-0000-0000-0000-{number:012d}"


def _seed_rows() -> dict[str, dict[str, object]]:
    now = "2026-01-02T03:04:05+00:00"
    day = "2026-01-02"
    return {
        "products": dict(
            internal_id=_uuid(1), product_code="LEGACY-PRODUCT-001", company="HMS",
            part_name="Legacy Part", quantity=Decimal("5"), unit="pcs",
            outsourced=False, status="ACTIVE",
        ),
        "customers": dict(
            internal_id=_uuid(2), customer_code="LEGACY-CUSTOMER-001",
            name="Legacy Customer", active=True, created_at=now, updated_at=now,
            created_by="legacy", updated_by="legacy",
        ),
        "purchase_orders": dict(
            internal_id=_uuid(3), po_number="LEGACY-PO-001", customer_id=_uuid(2),
            po_date=day, status="OPEN", created_at=now, updated_at=now,
            created_by="legacy", updated_by="legacy",
            internal_order_code="LEGACY-INTERNAL-001",
        ),
        "purchase_order_lines": dict(
            internal_id=_uuid(4), po_id=_uuid(3), product_id=_uuid(1), line_number=1,
            ordered_quantity=Decimal("5"), unit="pcs",
        ),
        "delivery_schedule_entries": dict(
            internal_id=_uuid(5), po_line_id=_uuid(4), planned_date=day,
            planned_quantity=Decimal("5"), status="PLANNED", created_at=now,
            updated_at=now,
        ),
        "production_runs": dict(
            internal_id=_uuid(6), run_code="LEGACY-RUN-001", po_line_id=_uuid(4),
            product_id=_uuid(1), planned_quantity=Decimal("5"),
            completed_quantity=Decimal("1"), status="ACTIVE", priority=1,
            created_at=now, updated_at=now, created_by="legacy", updated_by="legacy",
        ),
        "operators": dict(
            internal_id=_uuid(7), display_name="Legacy Operator", active=True,
            created_at=now, updated_at=now,
        ),
        "machining_types": dict(
            internal_id=_uuid(8), code="LEGACY-MACHINE", display_name="Legacy Machine",
            active=True, display_order=1,
        ),
        "order_tracking_items": dict(
            internal_id=_uuid(9), tracking_code="LEGACY-TRACK-001",
            purchase_order_id=_uuid(3), purchase_order_line_id=_uuid(4),
            product_id=_uuid(1), customer_id=_uuid(2), quantity=Decimal("5"), unit="pcs",
            delivery_date=day, status="IN_PROCESS", qr_public_id="LEGACY-QR-001",
            qr_status="ACTIVE", created_at=now, updated_at=now,
            created_by="legacy", updated_by="legacy",
        ),
        "user_preferences": dict(
            user_id=_uuid(7), machining_type_id=_uuid(8), updated_at=now,
        ),
        "attempt_display_state": dict(
            tracking_item_id=_uuid(9), machining_type_id=_uuid(8),
            max_visible_attempt=1, updated_at=now, updated_by=_uuid(7),
        ),
        "process_report_events": dict(
            internal_id=_uuid(10), request_id=_uuid(101), tracking_item_id=_uuid(9),
            machining_type_id=_uuid(8), kind="COMPLETED", quantity=Decimal("1"),
            actor_user_id=_uuid(7), actor_display_name_snapshot="Legacy Operator",
            server_timestamp=now, revision=1, status="ACTIVE",
        ),
        "tracking_audit_events": dict(
            internal_id=_uuid(11), tracking_item_id=_uuid(9),
            event_type="LEGACY_CREATED", actor="legacy", server_timestamp=now,
        ),
        "tracking_workflow_events": dict(
            internal_id=_uuid(12), request_id=_uuid(102), tracking_item_id=_uuid(9),
            event_type="GENERAL_REPORT", quantity=Decimal("1"),
            machining_type_id=_uuid(8), process_report_id=_uuid(10),
            actor_user_id=_uuid(7), actor_display_name_snapshot="Legacy Operator",
            server_timestamp=now, sequence_number=1, revision=1, status="ACTIVE",
        ),
    }


def _seed(database: Database) -> None:
    rows = _seed_rows()
    with database.transaction() as transaction:
        for table_name in LEGACY_TABLES:
            row = rows[table_name]
            columns = ", ".join(row)
            placeholders = ", ".join("?" for _ in row)
            transaction.execute(
                f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                list(row.values()),
            )


def _read_rows(database: Database) -> dict[str, list[dict]]:
    return {
        table_name: database.query(f"SELECT * FROM {table_name}")
        for table_name in LEGACY_TABLES
    }


def _schema_only(database: Database) -> dict[str, object]:
    return {"tables": database.schema.to_dict()["tables"]}


def _normalize(rows: dict[str, list[dict]]) -> dict[str, list[tuple]]:
    def plain(value):
        if isinstance(value, (dt.datetime, dt.date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return value

    return {
        table_name: sorted(
            tuple(sorted((key, plain(value)) for key, value in row.items()))
            for row in table_rows
        )
        for table_name, table_rows in rows.items()
    }


def _assert_seeded_values_survive(before: dict[str, list[tuple]], after: dict[str, list[tuple]]) -> None:
    """Every key/value pair captured before the later migrations must survive.

    A later migration may add a column (``products.outsourced_company``), which
    legitimately appears as a new ``None`` pair afterwards; that is additive,
    not a rewrite of seeded data.
    """

    assert set(after) == set(before)
    for table_name, before_rows in before.items():
        after_rows = after[table_name]
        assert len(after_rows) == len(before_rows)
        for before_row, after_row in zip(before_rows, after_rows):
            after_pairs = dict(after_row)
            for key, value in before_row:
                assert after_pairs[key] == value


def test_partial_history_converges_without_data_loss(tmp_path: Path):
    migrations = _migrations()
    database = Database(tmp_path / "partial-history-engine")
    try:
        prefix = [item for item in migrations if item[0] <= max(PARTIAL_REVISIONS)]
        run_migrations(database, prefix, now=_now)
        assert applied_versions(database) == set(PARTIAL_REVISIONS)
        _seed(database)
        rows_before = _normalize(_read_rows(database))

        run_migrations(database, migrations, now=_now)

        _assert_seeded_values_survive(rows_before, _normalize(_read_rows(database)))
        assert applied_versions(database) == {version for version, _, _ in migrations}
        assert "tracking_workflow_events" in database.schema.tables
    finally:
        database.close()


def test_partial_history_converges_to_the_same_schema_as_fresh_head(tmp_path: Path):
    migrations = _migrations()
    partial = Database(tmp_path / "converged-engine")
    fresh = Database(tmp_path / "fresh-engine")
    try:
        prefix = [item for item in migrations if item[0] <= max(PARTIAL_REVISIONS)]
        run_migrations(partial, prefix, now=_now)
        _seed(partial)
        run_migrations(partial, migrations, now=_now)
        run_migrations(fresh, migrations, now=_now)
        assert _schema_only(partial) == _schema_only(fresh)
    finally:
        partial.close()
        fresh.close()


def test_reapplying_head_is_a_noop(tmp_path: Path):
    migrations = _migrations()
    database = Database(tmp_path / "noop-engine")
    try:
        run_migrations(database, migrations, now=_now)
        before = database.schema.to_dict()
        assert run_migrations(database, migrations, now=_now) == []
        assert database.schema.to_dict() == before
        assert applied_versions(database) == {version for version, _, _ in migrations}
    finally:
        database.close()


def test_failing_migration_rolls_back_the_whole_step(tmp_path: Path):
    migrations = _migrations()
    database = Database(tmp_path / "rollback-engine")
    try:
        prefix = [item for item in migrations if item[0] == 1]
        run_migrations(database, prefix, now=_now)
        before = database.schema.to_dict()

        def broken(transaction):
            transaction.execute("CREATE TABLE rollback_probe (id TEXT PRIMARY KEY)")
            raise RuntimeError("intentional migration failure")

        with pytest_raises_engine_error():
            run_migrations(database, [(2, "broken", broken)], now=_now)

        assert database.schema.to_dict() == before
        assert "rollback_probe" not in database.schema.tables
        assert applied_versions(database) == {1}
    finally:
        database.close()


def pytest_raises_engine_error():
    import pytest

    return pytest.raises(RuntimeError, match="intentional migration failure")
