from __future__ import annotations

from packages.domain.tracking import TrackingError
from packages.domain.workflow import TrackingWorkflowEvent, WorkflowEventType


class WorkflowEventService:
    allowed_types: frozenset[WorkflowEventType] = frozenset()

    def __init__(self, repository):
        self.repository = repository

    def submit(self, *, event_type, inject_failure=False, **data):
        kind = WorkflowEventType(event_type)
        if kind not in self.allowed_types:
            raise TrackingError(f"event type {kind.value} is not valid for this service")
        event = TrackingWorkflowEvent.create(
            event_type=kind,
            sequence_number=1,
            **data,
        )
        return self.repository.submit(event, inject_failure=inject_failure)

    def revise(self, event_id, *, request_id, quantity, notes, actor_user_id,
               actor_display_name, reason, client_timestamp=None, device_id=None,
               machining_type_id=None, process_report_id=None, inject_failure=False):
        original = self.repository.get(event_id)
        if original.event_type not in self.allowed_types:
            raise TrackingError("event does not belong to this service")
        revision_notes = str(notes).strip() if notes is not None else None
        correction_reason = str(reason).strip()
        if not correction_reason:
            raise TrackingError("revision reason is required")
        if revision_notes:
            revision_notes = f"{revision_notes}\n[Lý do sửa: {correction_reason}]"
        else:
            revision_notes = f"Lý do sửa: {correction_reason}"
        event = TrackingWorkflowEvent.create(
            request_id=request_id, tracking_item_id=original.tracking_item_id,
            event_type=original.event_type, quantity=quantity, notes=revision_notes,
            machining_type_id=machining_type_id if machining_type_id is not None else original.machining_type_id,
            process_report_id=process_report_id if process_report_id is not None else original.process_report_id,
            actor_user_id=actor_user_id, actor_display_name=actor_display_name,
            client_timestamp=client_timestamp, device_id=device_id,
            sequence_number=original.sequence_number, revision=original.revision + 1,
            supersedes_event_id=original.internal_id,
        )
        return self.repository.revise(original.internal_id, event, inject_failure=inject_failure)


class QcService(WorkflowEventService):
    allowed_types = frozenset({
        WorkflowEventType.QC_CHECKED,
        WorkflowEventType.SHORTAGE_REPORTED,
        WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,
    })


class PackingService(WorkflowEventService):
    allowed_types = frozenset({WorkflowEventType.PACKED})


class DeliveryService(WorkflowEventService):
    allowed_types = frozenset({WorkflowEventType.DELIVERED})


class GeneralReportService(WorkflowEventService):
    allowed_types = frozenset({WorkflowEventType.GENERAL_REPORT})


class TrackingHistoryService:
    def __init__(self, workflow_repository, tracking_repository):
        self.workflow_repository = workflow_repository
        self.tracking_repository = tracking_repository

    def history(self, item_id):
        return self.workflow_repository.history(item_id, self.tracking_repository.history(item_id))

    def summary(self, item_id):
        return self.workflow_repository.summary(item_id)

    def list_summaries(self, search=None, status_filter=None):
        return self.workflow_repository.list_summaries(search, status_filter)
