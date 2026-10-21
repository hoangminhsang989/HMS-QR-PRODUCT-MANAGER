from datetime import date, datetime, timezone

import pytest

from packages.domain.stage2 import Customer, PurchaseOrder, PurchaseOrderLine, POStatus
from packages.domain.product import Product, ProductStatus
from packages.persistence.stage2_repository import Stage2Repository
from packages.persistence.engine_product_repository import EngineProductRepository
from packages.persistence.tracking_repository import TrackingRepository
from packages.application.tracking_service import TrackingService
from uuid import UUID


@pytest.fixture
def tracking_env(tmp_path):
    repo2 = Stage2Repository(f"sqlite:///{(tmp_path / 'tracking.sqlite').as_posix()}")
    repo2.create_schema()
    cid = "00000000-0000-0000-0000-000000000101"
    pid = "00000000-0000-0000-0000-000000000102"
    poid = "00000000-0000-0000-0000-000000000103"
    lid = "00000000-0000-0000-0000-000000000104"
    now = datetime.now(timezone.utc)
    repo2.add_customer(Customer(
        internal_id=UUID(cid), customer_code="CUS-T", name="HMS", short_name=None,
        address=None, tax_code=None, contact_name=None, phone=None, email=None,
        notes=None, active=True, created_at=now, updated_at=now,
        created_by="u", updated_by="u",
    ))
    EngineProductRepository(repo2.database).create(Product(
        internal_id=UUID(pid), product_code="SP-T", company="HMS", part_name="Plate",
        quantity=100, unit="pcs", material="SUS304", requester=None,
        surface_treatment="Anodized", outsourced=False, size="10x20x30",
        notes="Label note", delivery_schedule=None, status=ProductStatus.NEW,
        created_at=now, updated_at=now, created_by="u", updated_by="u",
    ))
    repo2.add_po(PurchaseOrder(
        internal_id=UUID(poid), po_number="PO-T", customer_id=UUID(cid),
        po_date=date(2026, 8, 1), requested_delivery_date=date(2026, 8, 20),
        status=POStatus.CONFIRMED, notes=None, created_at=now, updated_at=now,
        created_by="u", updated_by="u",
    ))
    repo2.add_line(PurchaseOrderLine(
        internal_id=UUID(lid), po_id=UUID(poid), product_id=UUID(pid),
        line_number=1, ordered_quantity=100, unit="pcs", unit_price=None,
        currency=None, customer_part_reference=None, notes=None,
    ))
    service = TrackingService(TrackingRepository(repo2.database))
    item = service.create_item(
        purchase_order_id=poid, purchase_order_line_id=lid, product_id=pid,
        customer_id=cid, quantity=100, unit="pcs",
        delivery_date=date(2026, 8, 20), actor="u",
    )
    return service, item
