from uuid import uuid4

import pytest

from packages.domain.tracking import TrackingError
from packages.domain.workflow import WorkflowEventType


def test_partial_packing_delivery_invariants_and_idempotency(workflow_env,workflow_data):
    env=workflow_env;item=env["item"]
    with pytest.raises(TrackingError):env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,1))
    request=uuid4();first=env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,40,request_id=request));same=env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,40,request_id=request));assert same.internal_id==first.internal_id
    assert env["history"].summary(item.internal_id)["current_status"]=="PACKING"
    env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,10))
    assert env["history"].summary(item.internal_id)["current_status"]=="PARTIALLY_DELIVERED"
    with pytest.raises(TrackingError):env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,31))
    env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,60))
    assert env["history"].summary(item.internal_id)["packed_quantity"]=="100.0000"
    delivered_request=uuid4();env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,90,request_id=delivered_request));env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,90,request_id=delivered_request))
    summary=env["history"].summary(item.internal_id)
    assert summary["delivered_quantity"]=="100.0000" and summary["current_status"]=="DELIVERED"
    assert env["repo"].events(item.internal_id)[-1].server_timestamp is not None


def test_shortage_reduces_available_pack_quantity(workflow_env,workflow_data):
    env=workflow_env;item=env["item"]
    env["qc"].submit(**workflow_data(WorkflowEventType.SHORTAGE_REPORTED,2))
    env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,98))
    assert env["history"].summary(item.internal_id)["current_status"]=="PACKED"
    with pytest.raises(TrackingError):env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,1))


def test_event_and_projection_are_atomic(workflow_env,workflow_data):
    env=workflow_env;item=env["item"]
    with pytest.raises(RuntimeError):env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,10),inject_failure=True)
    assert env["repo"].events(item.internal_id)==()
    summary=env["history"].summary(item.internal_id)
    assert summary["current_status"]=="NEW" and summary["packed_quantity"]=="0"


def test_full_status_projection_sequence_preserves_history(workflow_env,workflow_data):
    env=workflow_env;item=env["item"]
    env["qc"].submit(**workflow_data(WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,5,"NG"));assert env["history"].summary(item.internal_id)["current_status"]=="QC_NG"
    env["qc"].submit(**workflow_data(WorkflowEventType.QC_CHECKED,100,"Kiểm lại"));assert env["history"].summary(item.internal_id)["current_status"]=="QC_CHECKED"
    env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,100));assert env["history"].summary(item.internal_id)["current_status"]=="PACKED"
    env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,40));assert env["history"].summary(item.internal_id)["current_status"]=="PARTIALLY_DELIVERED"
    env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,60));assert env["history"].summary(item.internal_id)["current_status"]=="DELIVERED"
    assert [event.event_type for event in env["repo"].events(item.internal_id)]==[WorkflowEventType.QC_NG_RETURNED_TO_MACHINING,WorkflowEventType.QC_CHECKED,WorkflowEventType.PACKED,WorkflowEventType.DELIVERED,WorkflowEventType.DELIVERED]


def test_revision_recomputes_projection_and_rolls_back_invalid_correction(workflow_env,workflow_data):
    env=workflow_env;item=env["item"]
    packed=env["packing"].submit(**workflow_data(WorkflowEventType.PACKED,100));env["delivery"].submit(**workflow_data(WorkflowEventType.DELIVERED,80))
    with pytest.raises(TrackingError):env["packing"].revise(packed.internal_id,request_id=uuid4(),quantity=70,notes="Sai",reason="Nhập nhầm",actor_user_id=env["operator"].internal_id,actor_display_name="QC User")
    summary=env["history"].summary(item.internal_id);assert summary["packed_quantity"]=="100.0000" and summary["delivered_quantity"]=="80.0000" and summary["current_status"]=="PARTIALLY_DELIVERED"
    corrected=env["packing"].revise(packed.internal_id,request_id=uuid4(),quantity=90,notes="Sửa",reason="Đối chiếu",actor_user_id=env["operator"].internal_id,actor_display_name="QC User")
    assert corrected.revision==2 and env["history"].summary(item.internal_id)["current_status"]=="PARTIALLY_DELIVERED"
