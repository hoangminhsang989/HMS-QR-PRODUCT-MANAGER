from datetime import date
from sqlalchemy.orm import Session
import pytest
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.persistence.sqlalchemy_models import CustomerORM,ProductORM,PurchaseOrderORM,PurchaseOrderLineORM
from packages.persistence.tracking_repository import TrackingRepository
from packages.application.tracking_service import TrackingService

@pytest.fixture
def tracking_env(tmp_path):
    repo2=Stage2Repository(f"sqlite:///{(tmp_path/'tracking.sqlite').as_posix()}");repo2.create_schema();cid="00000000-0000-0000-0000-000000000101";pid="00000000-0000-0000-0000-000000000102";poid="00000000-0000-0000-0000-000000000103";lid="00000000-0000-0000-0000-000000000104"
    with Session(repo2.engine) as s:
        s.add(CustomerORM(internal_id=cid,customer_code="CUS-T",name="HMS",short_name=None,address=None,tax_code=None,contact_name=None,phone=None,email=None,notes=None,active=True,created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),updated_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),created_by="u",updated_by="u"));s.add(ProductORM(internal_id=pid,product_code="SP-T",company="HMS",part_name="Plate",quantity=100,unit="pcs",status="NEW"));s.add(PurchaseOrderORM(internal_id=poid,po_number="PO-T",internal_order_code="ORD-2026-000001",customer_id=cid,po_date=date(2026,8,1),requested_delivery_date=date(2026,8,20),status="CONFIRMED",notes=None,created_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),updated_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),created_by="u",updated_by="u"));s.add(PurchaseOrderLineORM(internal_id=lid,po_id=poid,product_id=pid,line_number=1,ordered_quantity=100,unit="pcs",unit_price=None,currency=None,customer_part_reference=None,notes=None));s.commit()
    service=TrackingService(TrackingRepository(repo2.engine));item=service.create_item(purchase_order_id=poid,purchase_order_line_id=lid,product_id=pid,customer_id=cid,quantity=100,unit="pcs",delivery_date=date(2026,8,20),actor="u");return service,item
