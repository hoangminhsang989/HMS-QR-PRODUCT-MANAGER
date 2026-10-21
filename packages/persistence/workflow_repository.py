"""HMS SQL engine tracking workflow repository."""

from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal
from uuid import UUID

from packages.domain.tracking import TrackingError, TrackingStatus, utc_now
from packages.domain.product import format_quantity
from packages.domain.workflow import TrackingWorkflowEvent, WorkflowEventType
from .database import resolve_database


def _values(event) -> dict:
    return {
        key: str(value) if isinstance(value, UUID) else value.value if hasattr(value, "value") else value
        for key, value in asdict(event).items()
    }


class WorkflowRepository:
    """Tracking workflow persistence on the in-process HMS SQL engine."""

    def __init__(self, engine, session_factory=None):
        self.database = resolve_database(engine, session_factory)

    def submit(self, event: TrackingWorkflowEvent, inject_failure: bool = False):
        with self.database.transaction() as transaction:
            items = transaction.execute(
                "SELECT internal_id, quantity, status, updated_at, updated_by"
                " FROM order_tracking_items WHERE internal_id = ?",
                [str(event.tracking_item_id)],
            )
            if not items:
                raise LookupError("Không tìm thấy chi tiết.")
            item = items[0]
            existing = transaction.execute(
                "SELECT * FROM tracking_workflow_events WHERE request_id = ?",
                [str(event.request_id)],
            )
            if existing:
                if not self._same_semantic_request(existing[0], event):
                    raise TrackingError("Yêu cầu trùng lặp không khớp.")
                return self._event(existing[0])
            self._validate_references(transaction, event)
            existing_sequences = transaction.execute(
                "SELECT sequence_number FROM tracking_workflow_events"
                " WHERE tracking_item_id = ?",
                [str(event.tracking_item_id)],
            )
            sequence = max(
                (int(row["sequence_number"]) for row in existing_sequences), default=0
            ) + 1
            event = replace(event, sequence_number=sequence)
            status = self._validate_and_project(transaction, item, event)
            values = _values(event)
            transaction.execute(
                "INSERT INTO tracking_workflow_events (" + ", ".join(values) + ") VALUES ("
                + ", ".join("?" for _ in values) + ")",
                list(values.values()),
            )
            transaction.execute(
                "UPDATE order_tracking_items SET status = ?, updated_at = ?, updated_by = ?"
                " WHERE internal_id = ?",
                [status, utc_now(), str(event.actor_user_id), str(event.tracking_item_id)],
            )
            if inject_failure:
                raise RuntimeError("injected workflow transaction failure")
        return event

    def revise(self, original_id, event: TrackingWorkflowEvent, inject_failure: bool = False):
        with self.database.transaction() as transaction:
            originals = transaction.execute(
                "SELECT * FROM tracking_workflow_events WHERE internal_id = ?", [str(original_id)]
            )
            items = transaction.execute(
                "SELECT internal_id, quantity, status, updated_at, updated_by"
                " FROM order_tracking_items WHERE internal_id = ?",
                [str(event.tracking_item_id)],
            )
            if not originals or not items:
                raise LookupError("Không tìm thấy sự kiện.")
            original = originals[0]
            item = items[0]
            duplicate = transaction.execute(
                "SELECT * FROM tracking_workflow_events WHERE request_id = ?",
                [str(event.request_id)],
            )
            if duplicate:
                row = duplicate[0]
                if (
                    not self._same_semantic_request(row, event)
                    or row["sequence_number"] != event.sequence_number
                    or row["revision"] != event.revision
                ):
                    raise TrackingError("Yêu cầu trùng lặp không khớp.")
                return self._event(row)
            if original["status"] != "ACTIVE":
                raise TrackingError("Chỉ được sửa bản ghi mới nhất.")
            transaction.execute(
                "UPDATE tracking_workflow_events SET status = ? WHERE internal_id = ?",
                ["SUPERSEDED", str(original_id)],
            )
            self._validate_references(transaction, event)
            status = self._validate_and_project(transaction, item, event)
            values = _values(event)
            transaction.execute(
                "INSERT INTO tracking_workflow_events (" + ", ".join(values) + ") VALUES ("
                + ", ".join("?" for _ in values) + ")",
                list(values.values()),
            )
            transaction.execute(
                "UPDATE order_tracking_items SET status = ?, updated_at = ?, updated_by = ?"
                " WHERE internal_id = ?",
                [status, utc_now(), str(event.actor_user_id), str(event.tracking_item_id)],
            )
            if inject_failure:
                raise RuntimeError("injected workflow transaction failure")
        return event

    def get(self, event_id):
        rows = self.database.query(
            "SELECT * FROM tracking_workflow_events WHERE internal_id = ?", [str(event_id)]
        )
        if not rows:
            raise LookupError("Không tìm thấy sự kiện.")
        return self._event(rows[0])

    def events(self, item_id, effective_only: bool = False):
        if effective_only:
            rows = self.database.query(
                "SELECT * FROM tracking_workflow_events WHERE tracking_item_id = ?"
                " AND status = ? ORDER BY sequence_number ASC, revision ASC",
                [str(item_id), "ACTIVE"],
            )
        else:
            rows = self.database.query(
                "SELECT * FROM tracking_workflow_events WHERE tracking_item_id = ?"
                " ORDER BY sequence_number ASC, revision ASC",
                [str(item_id)],
            )
        return tuple(self._event(row) for row in rows)

    def summary(self, item_id):
        items = self.database.query(
            "SELECT internal_id, quantity, status FROM order_tracking_items"
            " WHERE internal_id = ?",
            [str(item_id)],
        )
        if not items:
            raise LookupError("Không tìm thấy chi tiết.")
        item = items[0]
        active = self.database.query(
            "SELECT * FROM tracking_workflow_events WHERE tracking_item_id = ?"
            " AND status = ?",
            [str(item_id), "ACTIVE"],
        )
        totals = self._totals(active)
        return {
            "current_status": item["status"],
            "target_quantity": format_quantity(item["quantity"]),
            "checked_quantity": str(totals[WorkflowEventType.QC_CHECKED]),
            "shortage_quantity": str(totals[WorkflowEventType.SHORTAGE_REPORTED]),
            "ng_quantity": str(totals[WorkflowEventType.QC_NG_RETURNED_TO_MACHINING]),
            "packed_quantity": str(totals[WorkflowEventType.PACKED]),
            "delivered_quantity": str(totals[WorkflowEventType.DELIVERED]),
        }

    def list_summaries(self, search=None, status_filter=None):
        clauses: list[str] = []
        parameters: list[object] = []
        if search:
            clauses.append("tracking_code LIKE ?")
            parameters.append(f"%{search}%")
        if status_filter:
            clauses.append("status = ?")
            parameters.append(str(status_filter))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        items = self.database.query(
            f"SELECT internal_id, tracking_code FROM order_tracking_items{where}"
            " ORDER BY updated_at DESC, internal_id DESC",
            parameters,
        )
        return tuple(
            self.summary(item["internal_id"])
            | {"internal_id": item["internal_id"], "tracking_code": item["tracking_code"]}
            for item in items
        )

    def history(self, item_id, process_events):
        workflow = [self._history_event(event) for event in self.events(item_id)]
        process = [{
            "source": "MACHINING", "internal_id": str(event.internal_id),
            "event_type": event.kind.value, "quantity": format_quantity(event.quantity),
            "notes": event.notes, "actor_user_id": str(event.actor_user_id),
            "actor_display_name_snapshot": event.actor_display_name_snapshot,
            "server_timestamp": event.server_timestamp.isoformat(),
            "revision": event.revision, "status": event.status,
        } for event in process_events]
        return tuple(sorted(process + workflow, key=lambda row: row["server_timestamp"]))

    def _validate_and_project(self, session, item, incoming) -> str:
        active = list(session.execute(
            "SELECT * FROM tracking_workflow_events WHERE tracking_item_id = ?"
            " AND status = ?",
            [item["internal_id"], "ACTIVE"],
        ))
        simulated = active + [_values(incoming)]
        totals = self._totals(simulated)
        target = Decimal(str(item["quantity"]))
        if incoming.quantity is not None and Decimal(incoming.quantity) > target:
            raise TrackingError(f"{incoming.event_type.value} quantity exceeds tracking quantity")
        if totals[WorkflowEventType.SHORTAGE_REPORTED] > target:
            raise TrackingError("Số lượng báo thiếu vượt quá số lượng chi tiết.")
        available = target - totals[WorkflowEventType.SHORTAGE_REPORTED]
        packed = totals[WorkflowEventType.PACKED]
        delivered = totals[WorkflowEventType.DELIVERED]
        if available < 0 or packed > available:
            raise TrackingError("Số lượng đóng gói vượt quá số lượng hiện có.")
        if delivered > packed:
            raise TrackingError("Giao hàng cần đủ số lượng đã đóng gói.")
        status_events = [
            row for row in simulated
            if WorkflowEventType(row["event_type"]) != WorkflowEventType.GENERAL_REPORT
        ]
        latest_type = (
            WorkflowEventType(max(status_events, key=lambda row: row["sequence_number"])["event_type"])
            if status_events else None
        )
        return self._project_status(latest_type, item["status"], available, packed, delivered)

    @staticmethod
    def _validate_references(session, event):
        if not session.execute(
            "SELECT internal_id FROM operators WHERE internal_id = ?", [str(event.actor_user_id)]
        ):
            raise TrackingError("Không tìm thấy người dùng.")
        if event.machining_type_id and not session.execute(
            "SELECT internal_id FROM machining_types WHERE internal_id = ?",
            [str(event.machining_type_id)],
        ):
            raise TrackingError("Không tìm thấy công đoạn.")
        if event.process_report_id:
            report = session.execute(
                "SELECT tracking_item_id FROM process_report_events WHERE internal_id = ?",
                [str(event.process_report_id)],
            )
            if not report or report[0]["tracking_item_id"] != str(event.tracking_item_id):
                raise TrackingError("Báo cáo gia công liên quan không khớp.")

    @staticmethod
    def _same_semantic_request(row, event):
        def normalized(value):
            return str(value) if value is not None else None

        return all((
            row["tracking_item_id"] == str(event.tracking_item_id),
            row["event_type"] == event.event_type.value,
            row["quantity"] == event.quantity,
            row["notes"] == event.notes,
            row["machining_type_id"] == normalized(event.machining_type_id),
            row["process_report_id"] == normalized(event.process_report_id),
            row["actor_user_id"] == str(event.actor_user_id),
            row["actor_display_name_snapshot"] == event.actor_display_name_snapshot,
            row["client_timestamp"] == event.client_timestamp,
            row["device_id"] == event.device_id,
            row["supersedes_event_id"] == normalized(event.supersedes_event_id),
        ))

    @staticmethod
    def _project_status(last_type, current_status, available, packed, delivered):
        if last_type is None:
            return current_status
        if delivered:
            return (
                TrackingStatus.DELIVERED.value
                if delivered == available
                else TrackingStatus.PARTIALLY_DELIVERED.value
            )
        if packed:
            return (
                TrackingStatus.PACKED.value
                if packed == available
                else TrackingStatus.PACKING.value
            )
        return {
            WorkflowEventType.QC_CHECKED: TrackingStatus.QC_CHECKED.value,
            WorkflowEventType.SHORTAGE_REPORTED: TrackingStatus.SHORTAGE.value,
            WorkflowEventType.QC_NG_RETURNED_TO_MACHINING: TrackingStatus.QC_NG.value,
        }.get(last_type, TrackingStatus.IN_PROCESS.value)

    @staticmethod
    def _totals(rows):
        totals = {kind: Decimal("0") for kind in WorkflowEventType}
        for row in rows:
            if row["status"] == "ACTIVE" and row["quantity"] is not None:
                totals[WorkflowEventType(row["event_type"])] += Decimal(str(row["quantity"]))
        return totals

    @staticmethod
    def _event(row):
        return TrackingWorkflowEvent(
            UUID(row["internal_id"]), UUID(row["request_id"]), UUID(row["tracking_item_id"]),
            WorkflowEventType(row["event_type"]), row["quantity"], row["notes"],
            UUID(row["machining_type_id"]) if row["machining_type_id"] else None,
            UUID(row["process_report_id"]) if row["process_report_id"] else None,
            UUID(row["actor_user_id"]), row["actor_display_name_snapshot"],
            row["server_timestamp"], row["client_timestamp"], row["device_id"],
            row["sequence_number"], row["revision"],
            UUID(row["supersedes_event_id"]) if row["supersedes_event_id"] else None,
            row["status"],
        )

    @staticmethod
    def _history_event(event):
        return {
            "source": "WORKFLOW", "internal_id": str(event.internal_id),
            "event_type": event.event_type.value,
            "quantity": format_quantity(event.quantity) if event.quantity is not None else None,
            "notes": event.notes, "actor_user_id": str(event.actor_user_id),
            "actor_display_name_snapshot": event.actor_display_name_snapshot,
            "server_timestamp": event.server_timestamp.isoformat(),
            "revision": event.revision, "status": event.status,
        }


__all__ = ["WorkflowRepository"]
