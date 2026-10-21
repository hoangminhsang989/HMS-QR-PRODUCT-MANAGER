"""Engine concurrency: single-writer serialization and durable recovery."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
import threading

from config.environments import AppConfig, Environment
from packages.domain.product import Product, ProductStatus
from packages.persistence.database import create_database_runtime
from packages.persistence.engine_product_repository import EngineProductRepository
from packages.persistence.stage2_repository import Stage2Repository


def _runtime(tmp_path: Path, name: str):
    return create_database_runtime(
        AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / name).as_posix()}", "local")
    )


def _seed(runtime, product_code: str, quantity: int) -> None:
    now = datetime.now(timezone.utc)
    EngineProductRepository(runtime.database).create(Product(
        internal_id=UUID(int=quantity), product_code=product_code, company="HMS",
        part_name="Plate", quantity=quantity, unit="pcs", material=None,
        requester=None, surface_treatment=None, outsourced=False, size=None,
        notes=None, delivery_schedule=None, status=ProductStatus.NEW,
        created_at=now, updated_at=now, created_by="seed", updated_by="seed",
    ))


def test_engine_database_is_durable_across_reopen(tmp_path):
    runtime = _runtime(tmp_path, "durable.sqlite")
    try:
        Stage2Repository(runtime).create_schema()
        _seed(runtime, "DUR-1", 10)
    finally:
        runtime.dispose()
    reopened = _runtime(tmp_path, "durable.sqlite")
    try:
        rows = reopened.database.query(
            "SELECT product_code FROM products WHERE product_code = ?", ["DUR-1"]
        )
        assert [row["product_code"] for row in rows] == ["DUR-1"]
    finally:
        reopened.dispose()


def test_engine_serializes_parallel_writers_without_lost_updates(tmp_path):
    runtime = _runtime(tmp_path, "writers.sqlite")
    try:
        Stage2Repository(runtime).create_schema()
        _seed(runtime, "PAR-1", 0)
        failures: list[Exception] = []

        def increment(count: int) -> None:
            try:
                for _ in range(count):
                    with runtime.database.transaction() as transaction:
                        rows = transaction.execute(
                            "SELECT quantity FROM products WHERE product_code = ?", ["PAR-1"]
                        )
                        current = int(rows[0]["quantity"])
                        transaction.execute(
                            "UPDATE products SET quantity = ? WHERE product_code = ?",
                            [current + 1, "PAR-1"],
                        )
            except Exception as exc:  # noqa: BLE001 - surfaced through failures
                failures.append(exc)

        threads = [threading.Thread(target=increment, args=(25,)) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        assert not failures
        rows = runtime.database.query(
            "SELECT quantity FROM products WHERE product_code = ?", ["PAR-1"]
        )
        assert int(rows[0]["quantity"]) == 100
    finally:
        runtime.dispose()


def test_engine_rolls_back_a_failed_transaction(tmp_path):
    runtime = _runtime(tmp_path, "rollback.sqlite")
    try:
        Stage2Repository(runtime).create_schema()
        try:
            with runtime.database.transaction() as transaction:
                _seed(runtime, "RB-1", 1)
                raise RuntimeError("injected failure")
        except RuntimeError:
            pass
        rows = runtime.database.query(
            "SELECT product_code FROM products WHERE product_code = ?", ["RB-1"]
        )
        assert rows == []
    finally:
        runtime.dispose()
