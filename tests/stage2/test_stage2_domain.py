from datetime import date
from decimal import Decimal
from uuid import uuid4
import pytest
from packages.domain.stage2 import Customer, DeliveryScheduleEntry, POStatus, PurchaseOrder, PurchaseOrderLine, ProductionRun, RunStatus, Stage2ValidationError

def test_customer_po_line_delivery_run_invariants():
    customer=Customer.create(customer_code="cus-1",name="HMS",actor="u")
    po=PurchaseOrder.create(po_number="PO-1",customer_id=customer.internal_id,po_date=date(2026,8,1),actor="u")
    line=PurchaseOrderLine.create(po_id=po.internal_id,product_id=uuid4(),line_number=1,ordered_quantity=100,unit="pcs")
    delivery=DeliveryScheduleEntry.create(po_line_id=line.internal_id,planned_date=date(2026,8,20),planned_quantity=30)
    run=ProductionRun.create(run_code="RUN-1",po_line_id=line.internal_id,product_id=line.product_id,planned_quantity=100,completed_quantity=40,actor="u")
    assert customer.customer_code == "CUS-1" and po.status is POStatus.DRAFT
    assert line.ordered_quantity == Decimal("100") and delivery.planned_quantity == Decimal("30")
    assert run.completed_quantity == Decimal("40") and run.status is RunStatus.PLANNED
    with pytest.raises(Stage2ValidationError): ProductionRun.create(run_code="RUN-2",po_line_id=line.internal_id,product_id=line.product_id,planned_quantity=10,completed_quantity=11,actor="u")
    with pytest.raises(Stage2ValidationError): PurchaseOrder.create(po_number="PO-2",customer_id=customer.internal_id,po_date=date(2026,8,5),requested_delivery_date=date(2026,8,1),actor="u")
