from uuid import uuid4

import pytest

from packages.domain.tracking import MachiningType,ReportKind,TrackingError
from packages.domain.workflow import WorkflowEventType


def test_qc_shortage_ng_rework_multiple_cycles_and_history(workflow_env,workflow_data):
    env=workflow_env;tracking=env["tracking"];item=env["item"]
    mill=tracking.repo.add_machining_type(MachiningType(uuid4(),"MILL","PHAY",True,1))
    completed=tracking.submit_report(request_id=uuid4(),tracking_item_id=item.internal_id,machining_type_id=mill.internal_id,kind=ReportKind.PROCESS_COMPLETED,quantity=100,actor_user_id=env["operator"].internal_id,actor_display_name="QC User")
    assert tracking.repo.get_item(item.internal_id).status.value=="WAITING_QC"
    env["qc"].submit(**workflow_data(WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,3,"Sai kích thước",machining_type_id=mill.internal_id,process_report_id=completed.internal_id))
    assert env["history"].summary(item.internal_id)["current_status"]=="QC_NG"
    tracking.submit_report(request_id=uuid4(),tracking_item_id=item.internal_id,machining_type_id=mill.internal_id,kind=ReportKind.ATTEMPT,attempt_number=4,quantity=3,actor_user_id=env["operator"].internal_id,actor_display_name="QC User")
    assert tracking.repo.get_item(item.internal_id).status.value=="REWORK"
    env["qc"].submit(**workflow_data(WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,1,"NG lần 2",machining_type_id=mill.internal_id))
    env["qc"].submit(**workflow_data(WorkflowEventType.QC_CHECKED,100,"Đã kiểm tra lại"))
    env["qc"].submit(**workflow_data(WorkflowEventType.SHORTAGE_REPORTED,2,"Thiếu hàng"))
    summary=env["history"].summary(item.internal_id)
    assert summary["current_status"]=="SHORTAGE" and summary["checked_quantity"]=="100.0000" and summary["ng_quantity"]=="4.0000" and summary["shortage_quantity"]=="2.0000"
    history=env["history"].history(item.internal_id)
    assert len(history)==6 and {x["source"] for x in history}=={"MACHINING","WORKFLOW"}


def test_qc_partial_invalid_quantities_idempotency_and_revision(workflow_env,workflow_data):
    env=workflow_env;item=env["item"];request=uuid4()
    first=env["qc"].submit(**workflow_data(WorkflowEventType.QC_CHECKED,40,"Kiểm một phần",request_id=request))
    duplicate=env["qc"].submit(**workflow_data(WorkflowEventType.QC_CHECKED,40,"Kiểm một phần",request_id=request))
    assert duplicate.internal_id==first.internal_id
    with pytest.raises(TrackingError):env["qc"].submit(**workflow_data(WorkflowEventType.SHORTAGE_REPORTED,1,request_id=request))
    ng=env["qc"].submit(**workflow_data(WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,3,"NG ban đầu"))
    revised=env["qc"].revise(ng.internal_id,request_id=uuid4(),quantity=2,notes="NG sửa",reason="Nhập nhầm",actor_user_id=env["operator"].internal_id,actor_display_name="QC User")
    events=env["repo"].events(item.internal_id)
    assert revised.revision==2 and revised.supersedes_event_id==ng.internal_id and len(events)==3
    assert events[-2].status=="SUPERSEDED" and events[-1].status=="ACTIVE" and "Nhập nhầm" in events[-1].notes
    assert env["history"].summary(item.internal_id)["ng_quantity"]=="2.0000"
    for value in (0,-1,101):
        with pytest.raises(TrackingError):env["qc"].submit(**workflow_data(WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,value))


def test_general_report_does_not_change_status(workflow_env,workflow_data):
    env=workflow_env;item=env["item"]
    env["qc"].submit(**workflow_data(WorkflowEventType.QC_CHECKED,100))
    before=env["history"].summary(item.internal_id)["current_status"]
    report=env["general"].submit(**workflow_data(WorkflowEventType.GENERAL_REPORT,None,"Chờ khách xác nhận"))
    assert report.quantity is None and env["history"].summary(item.internal_id)["current_status"]==before
    with pytest.raises(TrackingError):env["general"].submit(**workflow_data(WorkflowEventType.GENERAL_REPORT,None," "))
