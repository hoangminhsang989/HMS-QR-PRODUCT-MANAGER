from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from packages.domain.tracking import TrackingError, qty, utc_now


class WorkflowEventType(StrEnum):
    QC_CHECKED = "QC_CHECKED"
    SHORTAGE_REPORTED = "SHORTAGE_REPORTED"
    QC_NG_RETURNED_TO_MACHINING = "QC_NG_RETURNED_TO_MACHINING"
    PACKED = "PACKED"
    DELIVERED = "DELIVERED"
    GENERAL_REPORT = "GENERAL_REPORT"


QUANTITY_EVENT_TYPES = frozenset({
    WorkflowEventType.QC_CHECKED,
    WorkflowEventType.SHORTAGE_REPORTED,
    WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,
    WorkflowEventType.PACKED,
    WorkflowEventType.DELIVERED,
})


@dataclass(frozen=True, slots=True)
class TrackingWorkflowEvent:
    internal_id: UUID
    request_id: UUID
    tracking_item_id: UUID
    event_type: WorkflowEventType
    quantity: Decimal | None
    notes: str | None
    machining_type_id: UUID | None
    process_report_id: UUID | None
    actor_user_id: UUID
    actor_display_name_snapshot: str
    server_timestamp: datetime
    client_timestamp: datetime | None
    device_id: str | None
    sequence_number: int
    revision: int
    supersedes_event_id: UUID | None
    status: str

    @classmethod
    def create(
        cls, *, request_id, tracking_item_id, event_type, actor_user_id,
        actor_display_name, sequence_number, quantity=None, notes=None,
        machining_type_id=None, process_report_id=None, client_timestamp=None,
        device_id=None, revision=1, supersedes_event_id=None,
    ):
        kind = WorkflowEventType(event_type)
        amount = qty(quantity) if kind in QUANTITY_EVENT_TYPES else None
        content = str(notes).strip() if notes is not None else None
        if kind == WorkflowEventType.GENERAL_REPORT and not content:
            raise TrackingError("general report content is required")
        actor_name = str(actor_display_name).strip()
        if not actor_name:
            raise TrackingError("actor display name is required")
        if sequence_number < 1 or revision < 1:
            raise TrackingError("invalid workflow event sequence or revision")
        return cls(
            uuid4(), UUID(str(request_id)), UUID(str(tracking_item_id)), kind,
            amount, content, UUID(str(machining_type_id)) if machining_type_id else None,
            UUID(str(process_report_id)) if process_report_id else None,
            UUID(str(actor_user_id)), actor_name, utc_now(), client_timestamp,
            str(device_id).strip() if device_id else None, sequence_number,
            revision, UUID(str(supersedes_event_id)) if supersedes_event_id else None,
            "ACTIVE",
        )
