"""HMS SQL engine tracking repository."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from packages.domain.tracking import (
    MachiningType,
    Operator,
    OrderTrackingItem,
    ProcessReportEvent,
    QRStatus,
    ReportKind,
    TrackingError,
    TrackingStatus,
    utc_now,
)
from packages.domain.product import format_quantity
from packages.sqlengine.errors import IntegrityError
from .database import resolve_database


def vals(obj) -> dict:
    return {
        key: str(value) if isinstance(value, UUID) else value.value if hasattr(value, "value") else value
        for key, value in asdict(obj).items()
    }


def _insert(table: str, values: dict) -> str:
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    return f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"


def _update(table: str, values: dict, key: str) -> str:
    assignments = ", ".join(f"{name} = ?" for name in values)
    return f"UPDATE {table} SET {assignments} WHERE {key} = ?"


class TrackingRepository:
    """Tracking persistence on the in-process HMS SQL engine."""

    def __init__(self, engine, session_factory=None):
        self.database = resolve_database(engine, session_factory)

    def next_tracking_sequence(self):
        return int(self.database.scalar("SELECT COUNT(*) FROM order_tracking_items") or 0) + 1

    def add_item(self, item):
        line = self.database.query(
            "SELECT po_id, product_id FROM purchase_order_lines WHERE internal_id = ?",
            [str(item.purchase_order_line_id)],
        )
        po = self.database.query(
            "SELECT customer_id FROM purchase_orders WHERE internal_id = ?",
            [str(item.purchase_order_id)],
        )
        if not line or str(line[0]["po_id"]) != str(item.purchase_order_id) or str(
            line[0]["product_id"]
        ) != str(item.product_id):
            raise TrackingError("tracking item relation mismatch")
        if not po or str(po[0]["customer_id"]) != str(item.customer_id):
            raise TrackingError("tracking item customer mismatch")
        with self.database.transaction() as transaction:
            transaction.execute(_insert("order_tracking_items", vals(item)), list(vals(item).values()))
        return item

    def save_item(self, item, event_type, actor, old=None, new=None, reason=None):
        values = vals(item)
        with self.database.transaction() as transaction:
            transaction.execute(
                _update("order_tracking_items", values, "internal_id"),
                [*values.values(), str(item.internal_id)],
            )
            audit = {
                "internal_id": str(uuid4()),
                "tracking_item_id": str(item.internal_id),
                "event_type": event_type,
                "old_value": old,
                "new_value": new,
                "actor": actor,
                "reason": reason,
                "server_timestamp": utc_now(),
            }
            transaction.execute(_insert("tracking_audit_events", audit), list(audit.values()))
        return item

    def get_item(self, identifier):
        rows = self.database.query(
            "SELECT * FROM order_tracking_items WHERE internal_id = ?", [str(identifier)]
        )
        if not rows:
            rows = self.database.query(
                "SELECT * FROM order_tracking_items WHERE tracking_code = ?", [str(identifier)]
            )
        if not rows:
            raise LookupError("tracking item not found")
        return self._item(rows[0])

    def list_items(self, search=None):
        if search:
            rows = self.database.query(
                "SELECT * FROM order_tracking_items WHERE tracking_code LIKE ?"
                " ORDER BY updated_at DESC, internal_id DESC",
                [f"%{search}%"],
            )
        else:
            rows = self.database.query(
                "SELECT * FROM order_tracking_items ORDER BY updated_at DESC, internal_id DESC"
            )
        return tuple(self._item(row) for row in rows)

    def qr_identity(self, identifier):
        item = self.get_item(identifier)
        product = self.database.query(
            "SELECT part_name, product_code FROM products WHERE internal_id = ?",
            [str(item.product_id)],
        )[0]
        customer = self.database.query(
            "SELECT name FROM customers WHERE internal_id = ?", [str(item.customer_id)]
        )[0]
        return {
            "product_name": product["part_name"],
            "customer_name": customer["name"],
            "product_code": product["product_code"],
            "tracking_code": item.tracking_code,
        }

    def scan_by_tracking_code(self, tracking_code):
        rows = self.database.query(
            "SELECT * FROM order_tracking_items WHERE tracking_code = ? AND qr_status = ?",
            [tracking_code, QRStatus.ACTIVE.value],
        )
        if not rows:
            raise LookupError("QR not found or revoked")
        item = self._item(rows[0])
        product = self.database.query(
            "SELECT product_code, part_name FROM products WHERE internal_id = ?",
            [str(item.product_id)],
        )[0]
        customer = self.database.query(
            "SELECT name FROM customers WHERE internal_id = ?", [str(item.customer_id)]
        )[0]
        po = self.database.query(
            "SELECT internal_order_code, po_number FROM purchase_orders WHERE internal_id = ?",
            [str(item.purchase_order_id)],
        )[0]
        return {
            "internal_id": item.internal_id,
            "product_id": item.product_id,
            "tracking_code": item.tracking_code,
            "product_code": product["product_code"],
            "part_name": product["part_name"],
            "customer": customer["name"],
            "order_code": po["internal_order_code"] or po["po_number"],
            "customer_po_number": po["po_number"],
            "delivery_date": item.delivery_date.isoformat(),
            "quantity": format_quantity(item.quantity),
            "unit": item.unit,
            "status": item.status,
            "qr_status": item.qr_status,
        }

    def label_data(self, identifier):
        item = self.get_item(identifier)
        product = self.database.query(
            "SELECT part_name, product_code, material, size, surface_treatment, notes"
            " FROM products WHERE internal_id = ?",
            [str(item.product_id)],
        )[0]
        customer = self.database.query(
            "SELECT name FROM customers WHERE internal_id = ?", [str(item.customer_id)]
        )[0]
        po = self.database.query(
            "SELECT internal_order_code, po_number FROM purchase_orders WHERE internal_id = ?",
            [str(item.purchase_order_id)],
        )[0]
        return {
            "product_name": product["part_name"],
            "customer_name": customer["name"],
            "product_code": product["product_code"],
            "tracking_code": item.tracking_code,
            "material": product["material"],
            "quantity": format_quantity(item.quantity),
            "unit": item.unit,
            "size": product["size"],
            "surface_treatment": product["surface_treatment"],
            "delivery_date": item.delivery_date.isoformat(),
            "order_code": po["internal_order_code"] or po["po_number"],
            "customer_po_number": po["po_number"],
            "notes": product["notes"],
        }

    def add_operator(self, obj):
        values = vals(obj)
        with self.database.transaction() as transaction:
            transaction.execute(_insert("operators", values), list(values.values()))
        return obj

    def list_operators(self):
        rows = self.database.query(
            "SELECT * FROM operators WHERE active = ? ORDER BY display_name ASC, internal_id ASC",
            [True],
        )
        return tuple(
            Operator(
                UUID(row["internal_id"]), row["display_name"], row["active"],
                row["created_at"], row["updated_at"],
            )
            for row in rows
        )

    def add_machining_type(self, obj):
        existing = self.database.query(
            "SELECT * FROM machining_types WHERE code = ?", [obj.code]
        )
        if existing:
            row = existing[0]
            return MachiningType(
                UUID(row["internal_id"]), row["code"], row["display_name"],
                row["active"], row["display_order"],
            )
        values = vals(obj)
        with self.database.transaction() as transaction:
            transaction.execute(_insert("machining_types", values), list(values.values()))
        return obj

    def list_machining_types(self):
        rows = self.database.query(
            "SELECT * FROM machining_types WHERE active = ? ORDER BY display_order ASC,"
            " internal_id ASC",
            [True],
        )
        return tuple(
            MachiningType(
                UUID(row["internal_id"]), row["code"], row["display_name"],
                row["active"], row["display_order"],
            )
            for row in rows
        )

    def atomic_new_order(self, source, order_code, po_number, delivery_date, actor, qr_public_id, fail=False):
        po_id = str(uuid4())
        line_id = str(uuid4())
        now = utc_now()
        with self.database.transaction() as transaction:
            transaction.execute(
                _insert("purchase_orders", {
                    "internal_id": po_id, "po_number": po_number,
                    "internal_order_code": order_code,
                    "customer_id": str(source.customer_id), "po_date": delivery_date,
                    "requested_delivery_date": delivery_date, "status": "DRAFT",
                    "notes": None, "created_at": now, "updated_at": now,
                    "created_by": actor, "updated_by": actor,
                }),
                [po_id, po_number, order_code, str(source.customer_id), delivery_date,
                 delivery_date, "DRAFT", None, now, now, actor, actor],
            )
            transaction.execute(
                _insert("purchase_order_lines", {
                    "internal_id": line_id, "po_id": po_id,
                    "product_id": str(source.product_id), "line_number": 1,
                    "ordered_quantity": source.quantity, "unit": source.unit,
                    "unit_price": None, "currency": None,
                    "customer_part_reference": None, "notes": None,
                }),
                [line_id, po_id, str(source.product_id), 1, source.quantity,
                 source.unit, None, None, None, None],
            )
            item = OrderTrackingItem.create(
                tracking_code=f"ITEM-{delivery_date.year}-{self.next_tracking_sequence():06d}",
                purchase_order_id=UUID(po_id), purchase_order_line_id=UUID(line_id),
                product_id=source.product_id, customer_id=source.customer_id,
                quantity=source.quantity, unit=source.unit,
                delivery_date=delivery_date, actor=actor,
            ).issue_qr(qr_public_id)
            if fail:
                raise RuntimeError("injected transaction failure")
            values = vals(item)
            transaction.execute(
                _insert("order_tracking_items", values), list(values.values())
            )
        return item

    def set_preference(self, user_id, type_id):
        values = {
            "user_id": str(user_id), "machining_type_id": str(type_id),
            "updated_at": utc_now(),
        }
        with self.database.transaction() as transaction:
            existing = transaction.execute(
                "SELECT user_id FROM user_preferences WHERE user_id = ?", [str(user_id)]
            )
            if not existing:
                transaction.execute(
                    _insert("user_preferences", values), list(values.values())
                )
            else:
                transaction.execute(
                    _update("user_preferences", values, "user_id"),
                    [*values.values(), str(user_id)],
                )
        return None

    def get_preference(self, user_id):
        rows = self.database.query(
            "SELECT machining_type_id FROM user_preferences WHERE user_id = ?", [str(user_id)]
        )
        return UUID(rows[0]["machining_type_id"]) if rows else None

    def get_attempt_max(self, item_id, type_id):
        rows = self.database.query(
            "SELECT max_visible_attempt FROM attempt_display_state WHERE tracking_item_id = ?"
            " AND machining_type_id = ?",
            [str(item_id), str(type_id)],
        )
        return rows[0]["max_visible_attempt"] if rows else 3

    def expand_attempt(self, item_id, type_id, new_max, user_id=None):
        current = self.get_attempt_max(item_id, type_id)
        if new_max < current or new_max > 99:
            raise TrackingError("attempt expansion must be monotonic and <= 99")
        values = {
            "tracking_item_id": str(item_id), "machining_type_id": str(type_id),
            "max_visible_attempt": new_max, "updated_at": utc_now(),
            "updated_by": str(user_id) if user_id else None,
        }
        with self.database.transaction() as transaction:
            existing = transaction.execute(
                "SELECT tracking_item_id FROM attempt_display_state"
                " WHERE tracking_item_id = ? AND machining_type_id = ?",
                [str(item_id), str(type_id)],
            )
            if existing:
                transaction.execute(
                    "UPDATE attempt_display_state SET max_visible_attempt = ?,"
                    " updated_at = ?, updated_by = ?"
                    " WHERE tracking_item_id = ? AND machining_type_id = ?",
                    [new_max, values["updated_at"], values["updated_by"], str(item_id), str(type_id)],
                )
            else:
                transaction.execute(
                    "INSERT INTO attempt_display_state (tracking_item_id,"
                    " machining_type_id, max_visible_attempt, updated_at, updated_by)"
                    " VALUES (?, ?, ?, ?, ?)",
                    [str(item_id), str(type_id), new_max, values["updated_at"], values["updated_by"]],
                )
        return new_max

    def submit_report(self, event):
        rows = self.database.query(
            "SELECT quantity, status FROM order_tracking_items WHERE internal_id = ?",
            [str(event.tracking_item_id)],
        )
        if not rows:
            raise LookupError("tracking item not found")
        if event.quantity > rows[0]["quantity"]:
            raise TrackingError("report quantity exceeds tracking quantity")
        existing = self.database.query(
            "SELECT * FROM process_report_events WHERE request_id = ?", [str(event.request_id)]
        )
        if existing:
            return self._report(existing[0])
        values = vals(event)
        with self.database.transaction() as transaction:
            transaction.execute(
                _insert("process_report_events", values), list(values.values())
            )
            if event.revision == 1:
                current = rows[0]["status"]
                if event.kind == ReportKind.PROCESS_COMPLETED:
                    status = TrackingStatus.WAITING_QC.value
                elif current in {TrackingStatus.QC_NG.value, TrackingStatus.REWORK.value}:
                    status = TrackingStatus.REWORK.value
                else:
                    status = TrackingStatus.IN_PROCESS.value
                transaction.execute(
                    "UPDATE order_tracking_items SET status = ?, updated_at = ?, updated_by = ?"
                    " WHERE internal_id = ?",
                    [status, utc_now(), str(event.actor_user_id), str(event.tracking_item_id)],
                )
        return event

    def history(self, item_id):
        rows = self.database.query(
            "SELECT * FROM process_report_events WHERE tracking_item_id = ?"
            " ORDER BY server_timestamp ASC, internal_id ASC",
            [str(item_id)],
        )
        return tuple(self._report(row) for row in rows)

    def audit_events(self, item_id):
        rows = self.database.query(
            "SELECT * FROM tracking_audit_events WHERE tracking_item_id = ?"
            " ORDER BY server_timestamp ASC, internal_id ASC",
            [str(item_id)],
        )
        return tuple(self._audit_event(row) for row in rows)

    def get_report(self, event_id):
        rows = self.database.query(
            "SELECT * FROM process_report_events WHERE internal_id = ?", [str(event_id)]
        )
        if not rows:
            raise LookupError("report not found")
        return self._report(rows[0])

    @staticmethod
    def _item(row):
        return OrderTrackingItem(
            UUID(row["internal_id"]), row["tracking_code"],
            UUID(row["purchase_order_id"]), UUID(row["purchase_order_line_id"]),
            UUID(row["product_id"]), UUID(row["customer_id"]), row["quantity"],
            row["unit"], row["delivery_date"], TrackingStatus(row["status"]),
            row["qr_public_id"],
            QRStatus(row["qr_status"]) if row["qr_status"] else None,
            row["created_at"], row["updated_at"], row["created_by"], row["updated_by"],
        )

    @staticmethod
    def _audit_event(row):
        stamp = row["server_timestamp"]
        return {
            "source": "AUDIT",
            "internal_id": row["internal_id"],
            "event_type": row["event_type"],
            "quantity": None,
            "notes": row["reason"],
            "actor_user_id": row["actor"],
            "actor_display_name_snapshot": row["actor"],
            "server_timestamp": stamp.isoformat() if hasattr(stamp, "isoformat") else stamp,
            "revision": None,
            "status": "ACTIVE",
        }

    @staticmethod
    def _report(row):
        return ProcessReportEvent(
            UUID(row["internal_id"]), UUID(row["request_id"]),
            UUID(row["tracking_item_id"]), UUID(row["machining_type_id"]),
            ReportKind(row["kind"]), row["attempt_number"], row["quantity"],
            row["notes"], UUID(row["actor_user_id"]),
            row["actor_display_name_snapshot"], row["server_timestamp"],
            row["client_timestamp"], row["device_id"], row["revision"],
            UUID(row["supersedes_id"]) if row["supersedes_id"] else None,
            row["status"],
        )


__all__ = ["TrackingRepository"]
