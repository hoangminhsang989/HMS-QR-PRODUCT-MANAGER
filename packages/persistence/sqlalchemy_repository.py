"""HMS SQL engine Stage 2 (customer / PO / delivery / run) repository."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from packages.domain.stage2 import (
    Customer,
    DeliveryScheduleEntry,
    DeliveryStatus,
    POStatus,
    ProductionRun,
    PurchaseOrder,
    PurchaseOrderLine,
    RunStatus,
    Stage2ValidationError,
)
from packages.sqlengine.errors import IntegrityError
from packages.sqlengine.migrations import run_migrations
from .database import ENGINE_MIGRATION_DIRECTORY, resolve_database


def _row(obj) -> dict:
    return {
        key: str(value) if isinstance(value, UUID) else value
        for key, value in asdict(obj).items()
    }


class Stage2Repository:
    """Stage 2 persistence on the in-process HMS SQL engine."""

    def __init__(self, database, session_factory=None):
        self.database = resolve_database(database, session_factory)

    def create_schema(self):
        from packages.sqlengine.migrations import load_migration_modules

        migrations = load_migration_modules(ENGINE_MIGRATION_DIRECTORY)
        run_migrations(self.database, migrations, now=lambda: _now().isoformat())
        return None

    def add_customer(self, obj: Customer):
        values = _row(obj)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        try:
            with self.database.transaction() as transaction:
                transaction.execute(
                    f"INSERT INTO customers ({columns}) VALUES ({placeholders})",
                    list(values.values()),
                )
        except IntegrityError as exc:
            raise ValueError("customer_code đã tồn tại.") from exc
        return obj

    def list_customers(self, search=None, active=None, page=1, page_size=50):
        clauses: list[str] = []
        parameters: list[object] = []
        if search:
            clauses.append("(name LIKE ? OR customer_code LIKE ?)")
            parameters.extend([f"%{search}%"] * 2)
        if active is not None:
            clauses.append("active = ?")
            parameters.append(active)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        total = int(self.database.scalar(f"SELECT COUNT(*) FROM customers{where}", parameters) or 0)
        rows = self.database.query(
            f"SELECT * FROM customers{where} ORDER BY name ASC, internal_id ASC"
            " LIMIT ? OFFSET ?",
            [*parameters, page_size, (page - 1) * page_size],
        )
        return tuple(self._customer(row) for row in rows), total

    def get_customer(self, identifier):
        rows = self.database.query(
            "SELECT * FROM customers WHERE customer_code = ?", [str(identifier)]
        )
        if not rows:
            rows = self.database.query(
                "SELECT * FROM customers WHERE internal_id = ?", [str(identifier)]
            )
        if not rows:
            raise LookupError("customer not found")
        return self._customer(rows[0])

    def update_customer(self, obj):
        values = _row(obj)
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self.database.transaction() as transaction:
            transaction.execute(
                f"UPDATE customers SET {assignments} WHERE internal_id = ?",
                [*values.values(), str(obj.internal_id)],
            )
        return obj

    def add_po(self, obj: PurchaseOrder):
        values = _row(obj)
        if not self.database.query(
            "SELECT internal_id FROM customers WHERE internal_id = ?", [str(obj.customer_id)]
        ):
            raise LookupError("customer not found")
        columns = ", ".join([*values, "internal_order_code"])
        placeholders = ", ".join("?" for _ in values) + ", ?"
        try:
            with self.database.transaction() as transaction:
                transaction.execute(
                    f"INSERT INTO purchase_orders ({columns}) VALUES ({placeholders})",
                    [*values.values(), None],
                )
        except IntegrityError as exc:
            raise ValueError("po_number đã tồn tại.") from exc
        return obj

    def list_pos(self, customer_id=None, status=None):
        clauses: list[str] = []
        parameters: list[object] = []
        if customer_id:
            clauses.append("customer_id = ?")
            parameters.append(str(customer_id))
        if status:
            clauses.append("status = ?")
            parameters.append(str(status))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.database.query(
            f"SELECT * FROM purchase_orders{where} ORDER BY po_date DESC, internal_id ASC", parameters
        )
        return tuple(self._po(row) for row in rows)

    def update_po(self, obj):
        values = _row(obj)
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self.database.transaction() as transaction:
            transaction.execute(
                f"UPDATE purchase_orders SET {assignments} WHERE internal_id = ?",
                [*values.values(), str(obj.internal_id)],
            )
        return obj

    def get_po(self, identifier):
        rows = self.database.query(
            "SELECT * FROM purchase_orders WHERE internal_id = ?", [str(identifier)]
        )
        if not rows:
            rows = self.database.query(
                "SELECT * FROM purchase_orders WHERE po_number = ?", [str(identifier)]
            )
        if not rows:
            raise LookupError("purchase order not found")
        return self._po(rows[0])

    def add_line(self, obj: PurchaseOrderLine):
        values = _row(obj)
        if not self.database.query(
            "SELECT internal_id FROM purchase_orders WHERE internal_id = ?", [str(obj.po_id)]
        ):
            raise LookupError("purchase order not found")
        if not self.database.query(
            "SELECT internal_id FROM products WHERE internal_id = ?", [str(obj.product_id)]
        ):
            raise LookupError("product not found")
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        try:
            with self.database.transaction() as transaction:
                transaction.execute(
                    f"INSERT INTO purchase_order_lines ({columns}) VALUES ({placeholders})",
                    list(values.values()),
                )
        except IntegrityError as exc:
            raise ValueError("line_number đã tồn tại trong PO.") from exc
        return obj

    def list_lines(self, po_id):
        rows = self.database.query(
            "SELECT * FROM purchase_order_lines WHERE po_id = ? ORDER BY line_number ASC,"
            " internal_id ASC",
            [str(po_id)],
        )
        return tuple(self._line(row) for row in rows)

    def add_delivery(self, obj: DeliveryScheduleEntry, ordered: Decimal):
        existing = self.database.query(
            "SELECT planned_quantity FROM delivery_schedule_entries WHERE po_line_id = ?"
            " AND status != ?",
            [str(obj.po_line_id), DeliveryStatus.CANCELLED.value],
        )
        total = sum((Decimal(str(row["planned_quantity"])) for row in existing), Decimal(0))
        total += Decimal(str(obj.planned_quantity))
        if total > ordered:
            raise Stage2ValidationError("planned_quantity", "Tổng lịch giao vượt ordered quantity.")
        values = _row(obj)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.database.transaction() as transaction:
            transaction.execute(
                f"INSERT INTO delivery_schedule_entries ({columns}) VALUES ({placeholders})",
                list(values.values()),
            )
        return obj

    def update_delivery(self, obj: DeliveryScheduleEntry, ordered: Decimal):
        existing = self.database.query(
            "SELECT planned_quantity FROM delivery_schedule_entries WHERE po_line_id = ?"
            " AND internal_id != ? AND status != ?",
            [str(obj.po_line_id), str(obj.internal_id), DeliveryStatus.CANCELLED.value],
        )
        total = sum((Decimal(str(row["planned_quantity"])) for row in existing), Decimal(0))
        total += Decimal(str(obj.planned_quantity))
        if total > ordered:
            raise Stage2ValidationError("planned_quantity", "Tổng lịch giao vượt ordered quantity.")
        if not self.database.query(
            "SELECT internal_id FROM delivery_schedule_entries WHERE internal_id = ?",
            [str(obj.internal_id)],
        ):
            raise LookupError("delivery schedule not found")
        values = _row(obj)
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self.database.transaction() as transaction:
            transaction.execute(
                f"UPDATE delivery_schedule_entries SET {assignments} WHERE internal_id = ?",
                [*values.values(), str(obj.internal_id)],
            )
        return obj

    def list_deliveries(self, line_id):
        rows = self.database.query(
            "SELECT * FROM delivery_schedule_entries WHERE po_line_id = ? ORDER BY planned_date ASC,"
            " internal_id ASC",
            [str(line_id)],
        )
        return tuple(self._delivery(row) for row in rows)

    def add_run(self, obj: ProductionRun, ordered: Decimal):
        existing = self.database.query(
            "SELECT planned_quantity FROM production_runs WHERE po_line_id = ? AND status != ?",
            [str(obj.po_line_id), RunStatus.CANCELLED.value],
        )
        planned = sum((Decimal(str(row["planned_quantity"])) for row in existing), Decimal(0))
        planned += Decimal(str(obj.planned_quantity))
        if planned > ordered:
            raise Stage2ValidationError("planned_quantity", "Tổng run vượt ordered quantity.")
        line = self.database.query(
            "SELECT product_id FROM purchase_order_lines WHERE internal_id = ?",
            [str(obj.po_line_id)],
        )
        if not line:
            raise LookupError("purchase order line not found")
        if str(line[0]["product_id"]) != str(obj.product_id):
            raise Stage2ValidationError("product_id", "Product không khớp PO Line.")
        values = _row(obj)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.database.transaction() as transaction:
            transaction.execute(
                f"INSERT INTO production_runs ({columns}) VALUES ({placeholders})",
                list(values.values()),
            )
        return obj

    def update_run(self, obj: ProductionRun, ordered: Decimal):
        existing = self.database.query(
            "SELECT planned_quantity FROM production_runs WHERE po_line_id = ?"
            " AND internal_id != ? AND status != ?",
            [str(obj.po_line_id), str(obj.internal_id), RunStatus.CANCELLED.value],
        )
        planned = sum((Decimal(str(row["planned_quantity"])) for row in existing), Decimal(0))
        planned += Decimal(str(obj.planned_quantity))
        if planned > ordered:
            raise Stage2ValidationError("planned_quantity", "Tổng run vượt ordered quantity.")
        if not self.database.query(
            "SELECT internal_id FROM production_runs WHERE internal_id = ?",
            [str(obj.internal_id)],
        ):
            raise LookupError("production run not found")
        values = _row(obj)
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self.database.transaction() as transaction:
            transaction.execute(
                f"UPDATE production_runs SET {assignments} WHERE internal_id = ?",
                [*values.values(), str(obj.internal_id)],
            )
        return obj

    def list_runs(self, po_line_id=None, status=None):
        clauses: list[str] = []
        parameters: list[object] = []
        if po_line_id:
            clauses.append("po_line_id = ?")
            parameters.append(str(po_line_id))
        if status:
            clauses.append("status = ?")
            parameters.append(str(status))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.database.query(
            f"SELECT * FROM production_runs{where} ORDER BY priority ASC, planned_start ASC,"
            " internal_id ASC",
            parameters,
        )
        return tuple(self._run(row) for row in rows)

    @staticmethod
    def _customer(row):
        return Customer(
            UUID(row["internal_id"]), row["customer_code"], row["name"], row["short_name"],
            row["address"], row["tax_code"], row["contact_name"], row["phone"], row["email"],
            row["notes"], row["active"], row["created_at"], row["updated_at"],
            row["created_by"], row["updated_by"],
        )

    @staticmethod
    def _po(row):
        return PurchaseOrder(
            UUID(row["internal_id"]), row["po_number"], UUID(row["customer_id"]),
            row["po_date"], row["requested_delivery_date"], POStatus(row["status"]),
            row["notes"], row["created_at"], row["updated_at"], row["created_by"],
            row["updated_by"],
        )

    @staticmethod
    def _line(row):
        return PurchaseOrderLine(
            UUID(row["internal_id"]), UUID(row["po_id"]), UUID(row["product_id"]),
            row["line_number"], row["ordered_quantity"], row["unit"], row["unit_price"],
            row["currency"], row["customer_part_reference"], row["notes"],
        )

    @staticmethod
    def _delivery(row):
        return DeliveryScheduleEntry(
            UUID(row["internal_id"]), UUID(row["po_line_id"]), row["planned_date"],
            row["planned_quantity"], DeliveryStatus(row["status"]), row["notes"],
            row["created_at"], row["updated_at"],
        )

    @staticmethod
    def _run(row):
        return ProductionRun(
            UUID(row["internal_id"]), row["run_code"], UUID(row["po_line_id"]),
            UUID(row["product_id"]), row["planned_quantity"], row["completed_quantity"],
            RunStatus(row["status"]), row["priority"], row["planned_start"],
            row["planned_finish"], row["actual_start"], row["actual_finish"],
            row["notes"], row["created_at"], row["updated_at"], row["created_by"],
            row["updated_by"],
        )


def _now():
    from packages.domain.tracking import utc_now

    return utc_now()


__all__ = ["Stage2Repository"]
