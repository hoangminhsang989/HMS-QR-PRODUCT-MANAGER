"""Portal dashboard reads: engine-backed stats and live feed.

The portal used to open the SQLite file directly with ``sqlite3`` and express
its lookups as one joined statement using ``coalesce``, ``case when``, ``||``
and ``LEFT JOIN``. The engine supports none of those, and its join merges rows
by column name, so a column shared between the driving table and a joined table
(``quantity``, ``notes``, ``status``) is overwritten by the joined table's
value. These tests pin the Python-side resolution that replaced it.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

import apps.server.portal as portal
from packages.persistence.database import engine_path
from packages.sqlengine import connect


PORTAL_TABLES = (
    "CREATE TABLE products (internal_id TEXT PRIMARY KEY, part_name TEXT NOT NULL)",
    "CREATE TABLE purchase_orders (internal_id TEXT PRIMARY KEY, po_number TEXT NOT NULL)",
    "CREATE TABLE operators (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL)",
    "CREATE TABLE machining_types (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL)",
    "CREATE TABLE order_tracking_items ("
    " internal_id TEXT PRIMARY KEY, tracking_code TEXT NOT NULL,"
    " product_id TEXT NOT NULL, status TEXT NOT NULL)",
    "CREATE TABLE process_report_events ("
    " internal_id TEXT PRIMARY KEY, tracking_item_id TEXT NOT NULL,"
    " machining_type_id TEXT NOT NULL, attempt_number INTEGER,"
    " quantity NUMERIC(18,4) NOT NULL, notes TEXT,"
    " actor_display_name_snapshot TEXT NOT NULL, server_timestamp DATETIME NOT NULL)",
    "CREATE TABLE tracking_workflow_events ("
    " internal_id TEXT PRIMARY KEY, tracking_item_id TEXT NOT NULL,"
    " event_type TEXT NOT NULL, quantity NUMERIC(18,4), notes TEXT,"
    " actor_display_name_snapshot TEXT NOT NULL, server_timestamp DATETIME NOT NULL)",
)

EMPTY_STATS = {
    "products": 0, "pos": 0, "tracking": 0, "operators": 0, "machining": 7,
    "in_prod": 0, "qc": 0, "packed": 0, "deliv": 0,
}

DEMO_STATS = {
    "products": 76, "pos": 75, "tracking": 76, "operators": 3, "machining": 7,
    "in_prod": 75, "qc": 1, "packed": 0, "deliv": 0,
}


def _point_portal_at(tmp_path: Path, monkeypatch) -> Path:
    """Create the SQLite path the portal resolves and return the engine directory."""

    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = db_dir / "stage1_r002_dev.sqlite"
    sqlite_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("HMS_QR_DATABASE_URL", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.delenv("HMS_QR_TEST_ROOT", raising=False)
    return engine_path(f"sqlite:///{sqlite_path.as_posix()}")


def _seed_portal_data(engine_dir: Path) -> None:
    db = connect(engine_dir)
    try:
        for statement in PORTAL_TABLES:
            db.execute(statement)
        db.execute("INSERT INTO products (internal_id, part_name) VALUES ('p1', 'BỘ PHẬN A')")
        db.execute("INSERT INTO products (internal_id, part_name) VALUES ('p2', 'BỘ PHẬN B')")
        db.execute("INSERT INTO purchase_orders (internal_id, po_number) VALUES ('po1', 'PO-1')")
        db.execute("INSERT INTO operators (internal_id, display_name) VALUES ('o1', 'Nguyễn Văn A')")
        db.execute("INSERT INTO machining_types (internal_id, display_name) VALUES ('m1', 'TIỆN')")
        for code, product, status in (
            ("t1", "p1", "IN_PRODUCTION"),
            ("t2", "p2", "QC_CHECKED"),
            ("t3", "p1", "PACKED"),
            ("t4", "p1", "DELIVERED"),
            ("t5", "p2", "IN_PRODUCTION"),
        ):
            db.execute(
                "INSERT INTO order_tracking_items (internal_id, tracking_code, product_id, status)"
                f" VALUES ('{code}', 'TRK-{code[1]}', '{product}', '{status}')"
            )
        # A dangling machining_type_id exercises the coalesce fallback.
        db.execute(
            "INSERT INTO process_report_events (internal_id, tracking_item_id, machining_type_id,"
            " attempt_number, quantity, notes, actor_display_name_snapshot, server_timestamp)"
            " VALUES ('r1', 't1', 'm1', 2, 7, 'note-from-report', 'Công nhân 1',"
            " '2026-10-18 10:00:00')"
        )
        db.execute(
            "INSERT INTO process_report_events (internal_id, tracking_item_id, machining_type_id,"
            " attempt_number, quantity, notes, actor_display_name_snapshot, server_timestamp)"
            " VALUES ('r2', 't2', 'm-missing', NULL, 3, NULL, 'Công nhân 2',"
            " '2026-10-18 11:00:00')"
        )
        db.execute(
            "INSERT INTO tracking_workflow_events (internal_id, tracking_item_id, event_type,"
            " quantity, notes, actor_display_name_snapshot, server_timestamp)"
            " VALUES ('w1', 't3', 'QC_CHECKED', 5, 'ok', 'QC Viên', '2026-10-18 12:00:00')"
        )
    finally:
        db.close()


def test_portal_stats_count_every_table_and_status(tmp_path, monkeypatch):
    engine_dir = _point_portal_at(tmp_path, monkeypatch)
    _seed_portal_data(engine_dir)

    assert portal.get_stats() == {
        "products": 2, "pos": 1, "tracking": 5, "operators": 1, "machining": 7,
        "in_prod": 2, "qc": 1, "packed": 1, "deliv": 1,
    }


def test_portal_live_feed_resolves_joins_in_python(tmp_path, monkeypatch):
    """quantity/notes must come from the event row, not the joined tables."""

    engine_dir = _point_portal_at(tmp_path, monkeypatch)
    _seed_portal_data(engine_dir)

    events = portal.get_live_events()
    assert len(events) == 3

    newest = events[0]
    assert newest["category"] == "WORKFLOW"
    assert newest["tracking_code"] == "TRK-3"
    assert newest["part_name"] == "BỘ PHẬN A"
    assert newest["action"] == "QC_CHECKED"
    assert newest["detail"] == "Quy trình QC/Giao"
    assert newest["quantity"] == "5"

    unmatched = events[1]
    assert unmatched["category"] == "PROCESS"
    assert unmatched["tracking_code"] == "TRK-2"
    assert unmatched["action"] == "Gia công"
    assert unmatched["detail"] == "Đã xong"
    assert unmatched["part_name"] == "BỘ PHẬN B"
    assert unmatched["quantity"] == "3"

    joined = events[2]
    assert joined["tracking_code"] == "TRK-1"
    assert joined["action"] == "TIỆN"
    assert joined["detail"] == "Lần 2"
    assert joined["quantity"] == "7"
    assert joined["notes"] == "note-from-report"
    assert joined["part_name"] == "BỘ PHẬN A"


def test_portal_never_creates_a_database(tmp_path, monkeypatch):
    engine_dir = _point_portal_at(tmp_path, monkeypatch)

    assert not engine_dir.exists()
    assert portal.get_stats() == EMPTY_STATS
    assert portal.get_live_events() == []
    assert not engine_dir.exists()


def test_portal_keeps_demo_counters_when_tables_are_missing(tmp_path, monkeypatch):
    engine_dir = _point_portal_at(tmp_path, monkeypatch)
    engine_dir.mkdir(parents=True)
    connect(engine_dir).close()

    assert portal.get_stats() == DEMO_STATS
    assert portal.get_live_events() == []


def test_portal_ignores_a_non_sqlite_database_url(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/hms_qr")
    monkeypatch.delenv("HMS_QR_TEST_ROOT", raising=False)

    assert portal._resolve_engine() is None
    assert portal.get_stats() == EMPTY_STATS
    assert portal.get_live_events() == []
