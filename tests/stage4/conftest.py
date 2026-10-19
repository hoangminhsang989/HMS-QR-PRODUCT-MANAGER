from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest

from packages.application.workflow_services import DeliveryService, GeneralReportService, PackingService, QcService, TrackingHistoryService
from packages.application.tracking_service import TrackingService
from packages.domain.product import Product, ProductStatus
from packages.domain.stage2 import Customer, PurchaseOrder, PurchaseOrderLine, POStatus
from packages.domain.tracking import Operator
from packages.persistence.sqlalchemy_product_repository import SqlAlchemyProductRepository
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.persistence.tracking_repository import TrackingRepository
from packages.persistence.workflow_repository import WorkflowRepository


@pytest.fixture
def tracking_env(tmp_path):
    repo2 = Stage2Repository(f"sqlite:///{(tmp_path / 'stage4.sqlite').as_posix()}")
    repo2.create_schema()
    now = datetime.now(timezone.utc)
    ids = {
        "customer": "00000000-0000-0000-0000-000000000301",
        "product": "00000000-0000-0000-0000-000000000302",
        "po": "00000000-0000-0000-0000-000000000303",
        "line": "00000000-0000-0000-0000-000000000304",
    }
    repo2.add_customer(Customer(
        internal_id=UUID(ids["customer"]), customer_code="CUS-QC", name="HMS QC",
        short_name=None, address=None, tax_code=None, contact_name=None, phone=None,
        email=None, notes=None, active=True, created_at=now, updated_at=now,
        created_by="u", updated_by="u",
    ))
    SqlAlchemyProductRepository(repo2.database).create(Product(
        internal_id=UUID(ids["product"]), product_code="SP-QC", company="HMS",
        part_name="QC Plate", quantity=100, unit="pcs", material="SUS304",
        requester=None, surface_treatment=None, outsourced=False, size="10x20",
        notes=None, delivery_schedule=None, status=ProductStatus.NEW,
        created_at=now, updated_at=now, created_by="u", updated_by="u",
    ))
    repo2.add_po(PurchaseOrder(
        internal_id=UUID(ids["po"]), po_number="PO-QC", customer_id=UUID(ids["customer"]),
        po_date=date(2026, 8, 13), requested_delivery_date=date(2026, 8, 30),
        status=POStatus.CONFIRMED, notes=None, created_at=now, updated_at=now,
        created_by="u", updated_by="u",
    ))
    repo2.add_line(PurchaseOrderLine(
        internal_id=UUID(ids["line"]), po_id=UUID(ids["po"]),
        product_id=UUID(ids["product"]), line_number=1, ordered_quantity=100,
        unit="pcs", unit_price=None, currency=None, customer_part_reference=None,
        notes=None,
    ))
    tracking = TrackingService(TrackingRepository(repo2.database))
    item = tracking.create_item(
        purchase_order_id=ids["po"], purchase_order_line_id=ids["line"],
        product_id=ids["product"], customer_id=ids["customer"], quantity=100,
        unit="pcs", delivery_date=date(2026, 8, 30), actor="u",
    )
    return tracking, item


@pytest.fixture
def workflow_env(tracking_env):
    tracking, item = tracking_env
    operator = tracking.repo.add_operator(Operator.create("QC User"))
    repository = WorkflowRepository(tracking.repo.database)
    return {
        "tracking": tracking, "item": item, "operator": operator, "repo": repository,
        "qc": QcService(repository), "packing": PackingService(repository),
        "delivery": DeliveryService(repository), "general": GeneralReportService(repository),
        "history": TrackingHistoryService(repository, tracking.repo),
    }


@pytest.fixture
def workflow_data(workflow_env):
    env = workflow_env

    def build(event_type, quantity=None, notes=None, request_id=None, **extra):
        return dict(
            request_id=request_id or uuid4(), tracking_item_id=env["item"].internal_id,
            event_type=event_type, quantity=quantity, notes=notes,
            actor_user_id=env["operator"].internal_id,
            actor_display_name=env["operator"].display_name, **extra,
        )

    return build
