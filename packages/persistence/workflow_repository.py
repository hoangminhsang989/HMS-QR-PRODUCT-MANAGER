from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.domain.tracking import TrackingError, TrackingStatus, utc_now
from packages.domain.workflow import TrackingWorkflowEvent, WorkflowEventType
from packages.persistence.tracking_models import (
    MachiningTypeORM,
    OperatorORM,
    ProcessReportORM,
    TrackingItemORM,
    TrackingWorkflowEventORM,
)


def _values(event):
    return {
        key: str(value) if isinstance(value, UUID) else value.value if hasattr(value, "value") else value
        for key, value in asdict(event).items()
    }


class WorkflowRepository:
    def __init__(self, engine):
        self.engine = engine

    def submit(self, event: TrackingWorkflowEvent, inject_failure: bool = False):
        with Session(self.engine) as session:
            item = session.scalar(select(TrackingItemORM).where(
                TrackingItemORM.internal_id == str(event.tracking_item_id)
            ).with_for_update())
            if not item:
                raise LookupError("tracking item not found")
            existing = session.scalar(select(TrackingWorkflowEventORM).where(
                TrackingWorkflowEventORM.request_id == str(event.request_id)
            ))
            if existing:
                if existing.tracking_item_id != str(event.tracking_item_id) or existing.event_type != event.event_type.value:
                    raise TrackingError("idempotency request identity mismatch")
                return self._event(existing)
            self._validate_references(session,event)
            sequence = (session.scalar(select(func.max(TrackingWorkflowEventORM.sequence_number)).where(
                TrackingWorkflowEventORM.tracking_item_id == str(event.tracking_item_id)
            )) or 0) + 1
            event = replace(event, sequence_number=sequence)
            self._validate_and_project(session, item, event)
            session.add(TrackingWorkflowEventORM(**_values(event)))
            item.updated_at = utc_now()
            item.updated_by = str(event.actor_user_id)
            if inject_failure:
                raise RuntimeError("injected workflow transaction failure")
            session.commit()
            return event

    def revise(self, original_id, event: TrackingWorkflowEvent, inject_failure: bool = False):
        with Session(self.engine) as session:
            original = session.get(TrackingWorkflowEventORM, str(original_id))
            item = session.scalar(select(TrackingItemORM).where(
                TrackingItemORM.internal_id == str(event.tracking_item_id)
            ).with_for_update())
            if not original or not item:
                raise LookupError("workflow event not found")
            duplicate = session.scalar(select(TrackingWorkflowEventORM).where(
                TrackingWorkflowEventORM.request_id == str(event.request_id)
            ))
            if duplicate:
                if duplicate.tracking_item_id != str(event.tracking_item_id) or duplicate.sequence_number != event.sequence_number:
                    raise TrackingError("idempotency request identity mismatch")
                return self._event(duplicate)
            if original.status != "ACTIVE":
                raise TrackingError("only the current event revision can be revised")
            original.status = "SUPERSEDED"
            session.flush()
            self._validate_references(session,event)
            self._validate_and_project(session, item, event)
            session.add(TrackingWorkflowEventORM(**_values(event)))
            item.updated_at = utc_now()
            item.updated_by = str(event.actor_user_id)
            if inject_failure:
                raise RuntimeError("injected workflow transaction failure")
            session.commit()
            return event

    def get(self, event_id):
        with Session(self.engine) as session:
            row = session.get(TrackingWorkflowEventORM, str(event_id))
            if not row:
                raise LookupError("workflow event not found")
            return self._event(row)

    def events(self, item_id, effective_only: bool = False):
        with Session(self.engine) as session:
            query = select(TrackingWorkflowEventORM).where(
                TrackingWorkflowEventORM.tracking_item_id == str(item_id)
            )
            if effective_only:
                query = query.where(TrackingWorkflowEventORM.status == "ACTIVE")
            rows = session.scalars(query.order_by(
                TrackingWorkflowEventORM.sequence_number,
                TrackingWorkflowEventORM.revision,
            )).all()
            return tuple(self._event(row) for row in rows)

    def summary(self, item_id):
        with Session(self.engine) as session:
            item = session.get(TrackingItemORM, str(item_id))
            if not item:
                raise LookupError("tracking item not found")
            active = session.scalars(select(TrackingWorkflowEventORM).where(
                TrackingWorkflowEventORM.tracking_item_id == str(item_id),
                TrackingWorkflowEventORM.status == "ACTIVE",
            )).all()
            totals = self._totals(active)
            return {
                "current_status": item.status,
                "target_quantity": str(item.quantity),
                "checked_quantity": str(totals[WorkflowEventType.QC_CHECKED]),
                "shortage_quantity": str(totals[WorkflowEventType.SHORTAGE_REPORTED]),
                "ng_quantity": str(totals[WorkflowEventType.QC_NG_RETURNED_TO_MACHINING]),
                "packed_quantity": str(totals[WorkflowEventType.PACKED]),
                "delivered_quantity": str(totals[WorkflowEventType.DELIVERED]),
            }

    def list_summaries(self, search=None, status_filter=None):
        with Session(self.engine) as session:
            query = select(TrackingItemORM)
            if search:
                query = query.where(TrackingItemORM.tracking_code.contains(search))
            if status_filter:
                query = query.where(TrackingItemORM.status == str(status_filter))
            items = session.scalars(query.order_by(TrackingItemORM.updated_at.desc())).all()
            return tuple(self.summary(item.internal_id) | {"internal_id": item.internal_id, "tracking_code": item.tracking_code} for item in items)

    def history(self, item_id, process_events):
        workflow = [self._history_event(event) for event in self.events(item_id)]
        process = [{
            "source": "MACHINING", "internal_id": str(event.internal_id),
            "event_type": event.kind.value, "quantity": str(event.quantity),
            "notes": event.notes, "actor_user_id": str(event.actor_user_id),
            "actor_display_name_snapshot": event.actor_display_name_snapshot,
            "server_timestamp": event.server_timestamp.isoformat(),
            "revision": event.revision, "status": event.status,
        } for event in process_events]
        return tuple(sorted(process + workflow, key=lambda row: row["server_timestamp"]))

    def _validate_and_project(self, session, item, incoming):
        active = list(session.scalars(select(TrackingWorkflowEventORM).where(
            TrackingWorkflowEventORM.tracking_item_id == item.internal_id,
            TrackingWorkflowEventORM.status == "ACTIVE",
        )).all())
        simulated = active + [TrackingWorkflowEventORM(**_values(incoming))]
        totals = self._totals(simulated)
        target = Decimal(item.quantity)
        if incoming.quantity is not None and Decimal(incoming.quantity) > target:
            raise TrackingError(f"{incoming.event_type.value} quantity exceeds tracking quantity")
        if totals[WorkflowEventType.SHORTAGE_REPORTED] > target:
            raise TrackingError("SHORTAGE_REPORTED quantity exceeds tracking quantity")
        available = target - totals[WorkflowEventType.SHORTAGE_REPORTED]
        packed = totals[WorkflowEventType.PACKED]
        delivered = totals[WorkflowEventType.DELIVERED]
        if available < 0 or packed > available:
            raise TrackingError("packed quantity exceeds available quantity")
        if delivered > packed:
            raise TrackingError("delivery requires sufficient packed quantity")
        status_events = [row for row in simulated if WorkflowEventType(row.event_type) != WorkflowEventType.GENERAL_REPORT]
        latest_type = WorkflowEventType(max(status_events,key=lambda row:row.sequence_number).event_type) if status_events else None
        item.status = self._project_status(latest_type, item.status, available, packed, delivered)

    @staticmethod
    def _validate_references(session,event):
        if not session.get(OperatorORM,str(event.actor_user_id)):
            raise TrackingError("operator not found")
        if event.machining_type_id and not session.get(MachiningTypeORM,str(event.machining_type_id)):
            raise TrackingError("machining type not found")
        if event.process_report_id:
            report=session.get(ProcessReportORM,str(event.process_report_id))
            if not report or report.tracking_item_id!=str(event.tracking_item_id):
                raise TrackingError("related process report mismatch")

    @staticmethod
    def _project_status(last_type, current_status, available, packed, delivered):
        if last_type is None:
            return current_status
        if delivered:
            return TrackingStatus.DELIVERED.value if delivered == available else TrackingStatus.PARTIALLY_DELIVERED.value
        if packed:
            return TrackingStatus.PACKED.value if packed == available else TrackingStatus.PACKING.value
        return {
            WorkflowEventType.QC_CHECKED: TrackingStatus.QC_CHECKED.value,
            WorkflowEventType.SHORTAGE_REPORTED: TrackingStatus.SHORTAGE.value,
            WorkflowEventType.QC_NG_RETURNED_TO_MACHINING: TrackingStatus.QC_NG.value,
        }.get(last_type, TrackingStatus.IN_PROCESS.value)

    @staticmethod
    def _totals(rows):
        totals = {kind: Decimal("0") for kind in WorkflowEventType}
        for row in rows:
            if row.status == "ACTIVE" and row.quantity is not None:
                totals[WorkflowEventType(row.event_type)] += Decimal(row.quantity)
        return totals

    @staticmethod
    def _event(row):
        return TrackingWorkflowEvent(
            UUID(row.internal_id), UUID(row.request_id), UUID(row.tracking_item_id),
            WorkflowEventType(row.event_type), row.quantity, row.notes,
            UUID(row.machining_type_id) if row.machining_type_id else None,
            UUID(row.process_report_id) if row.process_report_id else None,
            UUID(row.actor_user_id), row.actor_display_name_snapshot,
            row.server_timestamp, row.client_timestamp, row.device_id,
            row.sequence_number, row.revision,
            UUID(row.supersedes_event_id) if row.supersedes_event_id else None,
            row.status,
        )

    @staticmethod
    def _history_event(event):
        return {
            "source": "WORKFLOW", "internal_id": str(event.internal_id),
            "event_type": event.event_type.value,
            "quantity": str(event.quantity) if event.quantity is not None else None,
            "notes": event.notes, "actor_user_id": str(event.actor_user_id),
            "actor_display_name_snapshot": event.actor_display_name_snapshot,
            "server_timestamp": event.server_timestamp.isoformat(),
            "revision": event.revision, "status": event.status,
        }
