"""R010M1A1 partial historical migration forward-compatibility tests."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
import hashlib
import os
from pathlib import Path
import subprocess
import sys

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import MetaData, create_engine, inspect, select, text


REVISIONS = (
    "0001_stage2_baseline",
    "0002_tracking_qr_reporting",
    "0003_qc_packing_delivery",
)
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


def _config(url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _postgresql_url() -> str:
    value = os.environ.get("HMS_QR_R010M1_POSTGRESQL_URL", "").strip()
    if not value:
        pytest.skip("isolated R010M1A1 PostgreSQL runtime is not configured")
    return value


def _baseline_root() -> Path:
    value = os.environ.get("HMS_QR_R010M1A1_BASELINE_ROOT", "").strip()
    if not value:
        pytest.skip("delivered baseline source is not configured")
    root = Path(value)
    if not (root / "alembic.ini").is_file():
        pytest.fail("configured delivered baseline source is invalid")
    return root


def _reset_postgresql(url: str) -> None:
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def _database_url(dialect: str, tmp_path: Path, name: str) -> str:
    if dialect == "postgresql":
        url = _postgresql_url()
        _reset_postgresql(url)
        return url
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def _run_delivered(url: str, revision: str) -> None:
    code = (
        "import sys; from alembic.config import Config; from alembic import command; "
        "cfg=Config('alembic.ini'); cfg.set_main_option('sqlalchemy.url',sys.argv[1]); "
        "command.upgrade(cfg,sys.argv[2])"
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-B", "-c", code, url, revision],
        cwd=_baseline_root(),
        env=environment,
        check=True,
    )


def _semantic_schema(url: str) -> dict[str, dict[str, object]]:
    engine = create_engine(url)
    inspector = inspect(engine)
    result: dict[str, dict[str, object]] = {}
    for table in sorted(inspector.get_table_names()):
        result[table] = {
            "columns": tuple(
                sorted(
                    (
                        column["name"],
                        str(column["type"]),
                        bool(column["nullable"]),
                        column.get("default"),
                        int(column.get("primary_key", 0)),
                    )
                    for column in inspector.get_columns(table)
                )
            ),
            "pk": tuple(
                inspector.get_pk_constraint(table).get("constrained_columns") or ()
            ),
            "fks": tuple(
                sorted(
                    (
                        tuple(fk["constrained_columns"]),
                        fk["referred_table"],
                        tuple(fk["referred_columns"]),
                    )
                    for fk in inspector.get_foreign_keys(table)
                )
            ),
            "uniques": tuple(
                sorted(
                    tuple(unique["column_names"])
                    for unique in inspector.get_unique_constraints(table)
                    if unique.get("column_names")
                )
            ),
            "indexes": tuple(
                sorted(
                    (tuple(index["column_names"]), bool(index["unique"]))
                    for index in inspector.get_indexes(table)
                )
            ),
        }
    engine.dispose()
    return result


def _normalize(value):
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _legacy_rows(url: str) -> dict[str, tuple[tuple[tuple[str, object], ...], ...]]:
    engine = create_engine(url)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    result = {}
    with engine.connect() as connection:
        for table_name in LEGACY_TABLES:
            rows = connection.execute(select(metadata.tables[table_name])).mappings().all()
            result[table_name] = tuple(
                sorted(
                    tuple((key, _normalize(value)) for key, value in sorted(dict(row).items()))
                    for row in rows
                )
            )
    engine.dispose()
    return result


def _uuid(number: int) -> str:
    return f"00000000-0000-0000-0000-{number:012d}"


def _seed_every_legacy_table(url: str) -> None:
    now = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
    day = dt.date(2026, 1, 2)
    rows = {
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
    engine = create_engine(url)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.begin() as connection:
        for table_name in LEGACY_TABLES:
            connection.execute(metadata.tables[table_name].insert().values(**rows[table_name]))
    engine.dispose()


@pytest.mark.parametrize("dialect", ("postgresql", "sqlite"))
@pytest.mark.parametrize("revision", REVISIONS)
def test_delivered_partial_history_converges_without_data_loss(
    dialect: str, revision: str, tmp_path: Path
):
    suffix = revision[:4]
    url = _database_url(dialect, tmp_path, f"old-{dialect}-{suffix}.sqlite")
    _run_delivered(url, revision)
    assert len(_semantic_schema(url)) == 15
    _seed_every_legacy_table(url)
    rows_before = _legacy_rows(url)

    command.upgrade(_config(url), "head")

    assert _legacy_rows(url) == rows_before
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("select version_num from alembic_version")).scalar_one() == "0005_store_forward"
    engine.dispose()
    legacy_head = _semantic_schema(url)

    if dialect == "postgresql":
        _reset_postgresql(url)
        fresh_url = url
    else:
        fresh_url = f"sqlite:///{(tmp_path / f'fresh-{suffix}.sqlite').as_posix()}"
    command.upgrade(_config(fresh_url), "head")
    assert legacy_head == _semantic_schema(fresh_url)


@pytest.mark.parametrize("dialect", ("postgresql", "sqlite"))
def test_malformed_existing_column_fails_before_stamp_or_mutation(
    dialect: str, tmp_path: Path
):
    url = _database_url(dialect, tmp_path, f"malformed-column-{dialect}.sqlite")
    command.upgrade(_config(url), "0001_stage2_baseline")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE purchase_orders ADD COLUMN "
                "internal_order_code INTEGER NOT NULL DEFAULT 0"
            )
        )
    engine.dispose()
    before = _semantic_schema(url)

    with pytest.raises(RuntimeError, match="internal_order_code type"):
        command.upgrade(_config(url), "0002_tracking_qr_reporting")

    assert _semantic_schema(url) == before
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("select version_num from alembic_version")).scalar_one() == "0001_stage2_baseline"
    engine.dispose()


@pytest.mark.parametrize("dialect", ("postgresql", "sqlite"))
def test_malformed_existing_0002_table_fails_before_any_revision_mutation(
    dialect: str, tmp_path: Path
):
    url = _database_url(dialect, tmp_path, f"malformed-table-{dialect}.sqlite")
    command.upgrade(_config(url), "0001_stage2_baseline")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE operators (internal_id VARCHAR(36) PRIMARY KEY)"))
    engine.dispose()
    before = _semantic_schema(url)

    with pytest.raises(RuntimeError, match="operators column set"):
        command.upgrade(_config(url), "0002_tracking_qr_reporting")

    assert _semantic_schema(url) == before
    assert "internal_order_code" not in {
        column["name"] for column in inspect(create_engine(url)).get_columns("purchase_orders")
    }


@pytest.mark.parametrize("dialect", ("postgresql", "sqlite"))
def test_malformed_existing_0003_table_fails_before_stamp_or_mutation(
    dialect: str, tmp_path: Path
):
    url = _database_url(dialect, tmp_path, f"malformed-workflow-{dialect}.sqlite")
    command.upgrade(_config(url), "0002_tracking_qr_reporting")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE tracking_workflow_events (internal_id VARCHAR(36) PRIMARY KEY)")
        )
    engine.dispose()
    before = _semantic_schema(url)

    with pytest.raises(RuntimeError, match="tracking_workflow_events column set"):
        command.upgrade(_config(url), "0003_qc_packing_delivery")

    assert _semantic_schema(url) == before
    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("select version_num from alembic_version")).scalar_one() == "0002_tracking_qr_reporting"
    engine.dispose()


@pytest.mark.parametrize("dialect", ("postgresql", "sqlite"))
def test_internal_order_code_unique_conflict_fails_without_data_rewrite(
    dialect: str, tmp_path: Path
):
    url = _database_url(dialect, tmp_path, f"unique-conflict-{dialect}.sqlite")
    command.upgrade(_config(url), "0001_stage2_baseline")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE purchase_orders ADD COLUMN internal_order_code VARCHAR(64)")
        )
    metadata = MetaData()
    metadata.reflect(bind=engine)
    now = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["customers"].insert().values(
                internal_id=_uuid(201), customer_code="DUP-CUSTOMER", name="Duplicate Test",
                active=True, created_at=now, updated_at=now,
                created_by="test", updated_by="test",
            )
        )
        for number in (1, 2):
            connection.execute(
                metadata.tables["purchase_orders"].insert().values(
                    internal_id=_uuid(201 + number), po_number=f"DUP-PO-{number}",
                    customer_id=_uuid(201), po_date=dt.date(2026, 1, 2), status="OPEN",
                    created_at=now, updated_at=now, created_by="test", updated_by="test",
                    internal_order_code="DUPLICATE-CODE",
                )
            )
    engine.dispose()

    with pytest.raises(RuntimeError, match="duplicate values"):
        command.upgrade(_config(url), "0002_tracking_qr_reporting")

    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("select version_num from alembic_version")).scalar_one() == "0001_stage2_baseline"
        values = connection.execute(
            text("select internal_order_code from purchase_orders order by po_number")
        ).scalars().all()
    engine.dispose()
    assert values == ["DUPLICATE-CODE", "DUPLICATE-CODE"]
    assert len(_semantic_schema(url)) == 7


def test_delivered_existing_head_upgrade_is_raw_byte_noop(tmp_path: Path):
    database = tmp_path / "delivered-existing-head.sqlite"
    url = f"sqlite:///{database.as_posix()}"
    _run_delivered(url, "head")
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    command.upgrade(_config(url), "head")

    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
