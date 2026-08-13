from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.server.app import build_tracking_api
from packages.domain.tracking import TrackingError
from packages.domain.workflow import WorkflowEventType


def test_all_event_classes_idempotency_and_payload_conflict(workflow_env,workflow_data):
    env=workflow_env
    cases=((env["qc"],WorkflowEventType.QC_CHECKED,10,"qc"),(env["qc"],WorkflowEventType.SHORTAGE_REPORTED,1,"short"),(env["qc"],WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,2,"ng"),(env["packing"],WorkflowEventType.PACKED,10,"pack"),(env["delivery"],WorkflowEventType.DELIVERED,5,"deliver"),(env["general"],WorkflowEventType.GENERAL_REPORT,None,"report"))
    for service,kind,quantity,notes in cases:
        request=uuid4();data=workflow_data(kind,quantity,notes,request_id=request);first=service.submit(**data);same=service.submit(**data);assert same.internal_id==first.internal_id
        incompatible=dict(data);incompatible["notes"]=notes+" changed"
        with pytest.raises(TrackingError):service.submit(**incompatible)


def test_revision_effective_aggregates_for_shortage_packing_delivery(workflow_env,workflow_data):
    env=workflow_env;actor={"actor_user_id":env["operator"].internal_id,"actor_display_name":"QC User"}
    shortage=env["qc"].submit(**workflow_data(WorkflowEventType.SHORTAGE_REPORTED,4,"R1"));env["qc"].revise(shortage.internal_id,request_id=uuid4(),quantity=2,notes="R2",reason="correct",**actor);assert env["history"].summary(env["item"].internal_id)["shortage_quantity"]=="2.0000"
    packed=env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,10,"R1"));env["packing"].revise(packed.internal_id,request_id=uuid4(),quantity=8,notes="R2",reason="correct",**actor);assert env["history"].summary(env["item"].internal_id)["packed_quantity"]=="8.0000"
    delivered=env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,6,"R1"));env["delivery"].revise(delivered.internal_id,request_id=uuid4(),quantity=4,notes="R2",reason="correct",**actor);summary=env["history"].summary(env["item"].internal_id);assert summary["delivered_quantity"]=="4.0000"
    assert len(env["repo"].events(env["item"].internal_id))==6 and len(env["repo"].events(env["item"].internal_id,effective_only=True))==3


def test_additive_shortage_and_downstream_revision_guards(workflow_env,workflow_data):
    env=workflow_env;actor={"actor_user_id":env["operator"].internal_id,"actor_display_name":"QC User"}
    first=env["qc"].submit(**workflow_data(WorkflowEventType.SHORTAGE_REPORTED,2));second=env["qc"].submit(**workflow_data(WorkflowEventType.SHORTAGE_REPORTED,1));assert env["history"].summary(env["item"].internal_id)["shortage_quantity"]=="3.0000"
    env["qc"].revise(first.internal_id,request_id=uuid4(),quantity=1,notes=None,reason="correct",**actor);assert env["history"].summary(env["item"].internal_id)["shortage_quantity"]=="2.0000"
    env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,98))
    with pytest.raises(TrackingError):env["qc"].revise(second.internal_id,request_id=uuid4(),quantity=5,notes=None,reason="invalid",**actor)
    assert env["history"].summary(env["item"].internal_id)["shortage_quantity"]=="2.0000"


def test_revision_idempotency_conflict_and_api_structured_errors(workflow_env,workflow_data):
    env=workflow_env;actor={"actor_user_id":env["operator"].internal_id,"actor_display_name":"QC User"};event=env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,20));request=uuid4();data=dict(request_id=request,quantity=15,notes="R2",reason="correct",**actor);revised=env["packing"].revise(event.internal_id,**data);same=env["packing"].revise(event.internal_id,**data);assert same.internal_id==revised.internal_id
    conflict=dict(data);conflict["quantity"]=14
    with pytest.raises(TrackingError):env["packing"].revise(revised.internal_id,**conflict)
    client=TestClient(build_tracking_api(env["tracking"]));base={"request_id":str(uuid4()),"event_type":"PACKED","quantity":0,"actor_user_id":str(env["operator"].internal_id),"actor_display_name":"QC User"};response=client.post(f"/api/v1/tracking-items/{env['item'].internal_id}/packing-events",json=base);assert response.status_code==422 and response.json()["error"]["code"]=="TRACKING_VALIDATION_ERROR"
    missing=client.post(f"/api/v1/tracking-items/{uuid4()}/packing-events",json={**base,"request_id":str(uuid4()),"quantity":1});assert missing.status_code==404 and missing.json()["error"]["code"]=="TRACKING_NOT_FOUND"


def test_general_report_revision_keeps_projection(workflow_env,workflow_data):
    env=workflow_env;env["qc"].submit(**workflow_data(WorkflowEventType.QC_CHECKED,100));before=env["history"].summary(env["item"].internal_id)["current_status"];report=env["general"].submit(**workflow_data(WorkflowEventType.GENERAL_REPORT,None,"R1"));env["general"].revise(report.internal_id,request_id=uuid4(),quantity=None,notes="R2",reason="correct",actor_user_id=env["operator"].internal_id,actor_display_name="QC User");assert env["history"].summary(env["item"].internal_id)["current_status"]==before
