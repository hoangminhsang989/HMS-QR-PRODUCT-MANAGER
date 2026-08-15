"""Real PostgreSQL row-locking and concurrency acceptance for R010R2."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from config.environments import AppConfig, Environment
from config.paths import TEST_ROOT
from packages.application.stage2_service import Stage2Service
from packages.application.tracking_service import TrackingService
from packages.application.workflow_services import DeliveryService, PackingService, QcService
from packages.domain.store_forward import ArchiveTransferState, StorageConfiguration
from packages.domain.tracking import Operator, TrackingError
from packages.domain.workflow import WorkflowEventType
from packages.persistence.database import create_database_runtime
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.sqlalchemy_models import (
    CustomerORM,
    ProductORM,
    PurchaseOrderLineORM,
    PurchaseOrderORM,
)
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.persistence.storage_models import ManagedFileORM, ProductFileRelationORM
from packages.persistence.store_forward_models import ArchiveTransferJobORM, StorageConfigurationORM
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.persistence.tracking_models import TrackingWorkflowEventORM
from packages.persistence.tracking_repository import TrackingRepository
from packages.persistence.workflow_repository import WorkflowRepository


def _postgresql_url() -> str:
    value = (
        os.environ.get("HMS_QR_R010R2_POSTGRESQL_URL", "").strip()
        or os.environ.get("HMS_QR_R010M1_POSTGRESQL_URL", "").strip()
    )
    if not value:
        pytest.skip("isolated R010R2 PostgreSQL runtime is not configured")
    return value


@pytest.fixture(scope="module")
def runtime():
    url = _postgresql_url()
    probe = create_database_runtime(AppConfig(Environment.PROD, url, "test"))
    with probe.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")
    probe.dispose()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    value = create_database_runtime(AppConfig(Environment.PROD, url, "test"))
    yield value
    value.dispose()


def _seed_product(runtime, *, code: str | None = None) -> UUID:
    product_id = uuid4()
    now = datetime.now(timezone.utc)
    with runtime.session_factory.begin() as session:
        session.add(ProductORM(
            internal_id=str(product_id), product_code=code or f"PG-{uuid4().hex[:10]}",
            company="HMS", part_name="Concurrency Plate", quantity=Decimal("100.0000"),
            unit="pcs", material="SUS304", requester=None, surface_treatment=None,
            outsourced=False, size="10x20", notes=None, delivery_schedule=None,
            status="NEW", created_at=now, updated_at=now,
            created_by="r010r2", updated_by="r010r2",
        ))
    return product_id


def _seed_tracking(runtime):
    token = uuid4().hex[:10]
    now = datetime.now(timezone.utc)
    customer_id, product_id, po_id, line_id = (uuid4() for _ in range(4))
    with runtime.session_factory.begin() as session:
        session.add(CustomerORM(
            internal_id=str(customer_id), customer_code=f"CUS-{token}", name="PG Customer",
            short_name=None, address=None, tax_code=None, contact_name=None, phone=None,
            email=None, notes=None, active=True, created_at=now, updated_at=now,
            created_by="r010r2", updated_by="r010r2",
        ))
        session.add(ProductORM(
            internal_id=str(product_id), product_code=f"PROD-{token}", company="HMS",
            part_name="PG Tracking Part", quantity=Decimal("100.0000"), unit="pcs",
            material="SUS304", requester=None, surface_treatment=None, outsourced=False,
            size=None, notes=None, delivery_schedule=None, status="NEW",
            created_at=now, updated_at=now, created_by="r010r2", updated_by="r010r2",
        ))
        session.add(PurchaseOrderORM(
            internal_id=str(po_id), po_number=f"PO-{token}", internal_order_code=f"ORD-{token}",
            customer_id=str(customer_id), po_date=date(2026, 8, 15),
            requested_delivery_date=date(2026, 8, 30), status="CONFIRMED", notes=None,
            created_at=now, updated_at=now, created_by="r010r2", updated_by="r010r2",
        ))
        session.add(PurchaseOrderLineORM(
            internal_id=str(line_id), po_id=str(po_id), product_id=str(product_id),
            line_number=1, ordered_quantity=Decimal("100.0000"), unit="pcs",
            unit_price=None, currency=None, customer_part_reference=None, notes=None,
        ))
    repository = TrackingRepository(runtime)
    service = TrackingService(repository)
    item = service.create_item(
        purchase_order_id=po_id, purchase_order_line_id=line_id, product_id=product_id,
        customer_id=customer_id, quantity=Decimal("100"), unit="pcs",
        delivery_date=date(2026, 8, 30), actor="r010r2",
    )
    operator = repository.add_operator(Operator.create(f"Operator {token}"))
    return service, item, operator


def test_customer_po_production_run_and_tracking_qr_invariants(runtime):
    product_id = _seed_product(runtime)
    service = Stage2Service(Stage2Repository(runtime))
    customer = service.create_customer(actor="r010r2", name=f"Customer {uuid4().hex[:8]}")
    po = service.create_po(
        actor="r010r2", po_number=f"PO-{uuid4().hex[:8]}",
        customer_id=customer.internal_id, po_date=date(2026, 8, 15),
    )
    line = service.add_line(
        po_id=po.internal_id, product_id=product_id, line_number=1,
        ordered_quantity=Decimal("10"), unit="pcs",
    )
    run = service.create_run(
        actor="r010r2", run_code=f"RUN-{uuid4().hex[:8]}", po_line_id=line.internal_id,
        product_id=product_id, ordered_quantity=Decimal("10"), planned_quantity=Decimal("8"),
    )
    assert service.list_runs(po_line_id=line.internal_id) == (run,)

    tracking, item, _ = _seed_tracking(runtime)
    issued = tracking.issue_qr(item.internal_id, "r010r2")
    payload = tracking.qr_payload_data(issued.internal_id)
    assert set(payload.__dict__ if hasattr(payload, "__dict__") else payload.__slots__) == {
        "product_name", "customer_name", "product_code", "tracking_code"
    }
    changed = tracking.change_date(issued.internal_id, date(2026, 9, 1), "r010r2")
    assert changed.tracking_code == issued.tracking_code
    new_item = tracking.create_new_order_from_item(
        issued.internal_id, new_po_number=f"PO-NEW-{uuid4().hex[:8]}",
        delivery_date=date(2026, 9, 2), actor="r010r2",
    )
    assert new_item.tracking_code != issued.tracking_code


def test_real_row_lock_serializes_concurrent_idempotency(runtime):
    _, item, operator = _seed_tracking(runtime)
    request_id = uuid4()

    def submit(quantity=Decimal("10")):
        return QcService(WorkflowRepository(runtime)).submit(
            request_id=request_id, tracking_item_id=item.internal_id,
            event_type=WorkflowEventType.QC_CHECKED, quantity=quantity, notes="PG lock",
            actor_user_id=operator.internal_id, actor_display_name=operator.display_name,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: submit(), range(2)))
    assert results[0].internal_id == results[1].internal_id
    with runtime.session_factory() as session:
        rows = session.scalar(select(func.count()).select_from(TrackingWorkflowEventORM).where(
            TrackingWorkflowEventORM.request_id == str(request_id)
        ))
    assert rows == 1
    with pytest.raises(TrackingError, match="idempotency"):
        submit(Decimal("11"))


def test_qc_packing_delivery_and_transaction_failure_are_atomic(runtime):
    tracking, item, operator = _seed_tracking(runtime)
    repository = WorkflowRepository(runtime)
    common = {
        "tracking_item_id": item.internal_id,
        "actor_user_id": operator.internal_id,
        "actor_display_name": operator.display_name,
    }
    QcService(repository).submit(
        request_id=uuid4(), event_type=WorkflowEventType.QC_CHECKED,
        quantity=Decimal("10"), notes=None, **common,
    )
    PackingService(repository).submit(
        request_id=uuid4(), event_type=WorkflowEventType.PACKED,
        quantity=Decimal("8"), notes=None, **common,
    )
    DeliveryService(repository).submit(
        request_id=uuid4(), event_type=WorkflowEventType.DELIVERED,
        quantity=Decimal("8"), notes=None, **common,
    )
    before = repository.summary(item.internal_id)
    with pytest.raises(RuntimeError, match="injected"):
        QcService(repository).submit(
            request_id=uuid4(), event_type=WorkflowEventType.SHORTAGE_REPORTED,
            quantity=Decimal("1"), notes=None, inject_failure=True, **common,
        )
    assert repository.summary(item.internal_id) == before


def _configuration() -> StorageConfiguration:
    token = uuid4().hex
    root = Path(TEST_ROOT, "r010r2-postgresql-concurrency", token)
    return StorageConfiguration(
        configuration_id=uuid4(), local_ingest_root=str(root / "local"),
        archive_target_root=str(root / "archive"), grace_period_hours=24,
        retry_schedule_seconds=(60, 300), warning_free_bytes=300,
        critical_free_bytes=200, upload_refusal_free_bytes=100,
    )


def _managed_file(runtime, product_id: UUID) -> UUID:
    file_id = uuid4()
    now = datetime.now(timezone.utc)
    with runtime.session_factory.begin() as session:
        session.add(ManagedFileORM(
            internal_id=str(file_id), original_filename="drawing.pdf",
            stored_filename=f"{file_id}.pdf", storage_key=f"r010r2/{file_id}.pdf",
            category="DRAWING", media_type="application/pdf", extension=".pdf",
            size_bytes=8, sha256="0" * 64, status="READY", source="UPLOAD",
            version=1, created_at=now, created_by="r010r2", updated_at=now,
            replaced_file_id=None, archived_at=None, archived_by=None, failure_reason=None,
        ))
    return file_id


def test_store_forward_ensure_lease_and_stale_recovery_concurrency(runtime):
    product_id = _seed_product(runtime)
    file_id = _managed_file(runtime, product_id)
    repository = StoreForwardRepository(runtime)
    configuration = repository.create_configuration(_configuration())

    def ensure():
        return StoreForwardRepository(runtime).ensure_job(
            file_id, configuration.configuration_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = tuple(executor.map(lambda _: ensure(), range(2)))
    assert jobs[0].job_id == jobs[1].job_id
    with runtime.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ArchiveTransferJobORM).where(
            ArchiveTransferJobORM.managed_file_id == str(file_id)
        )) == 1

    now = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = tuple(executor.map(
            lambda worker: StoreForwardRepository(runtime).claim_next(
                worker_id=f"worker-{worker}", now=now, lease_seconds=1
            ),
            range(2),
        ))
    active = tuple(claim for claim in claims if claim is not None)
    assert len(active) == 1
    assert active[0].state is ArchiveTransferState.TRANSFERRING
    assert repository.recover_expired_leases(at=now + timedelta(seconds=2)) == 1
    reclaimed = repository.claim_next(worker_id="worker-recovery", now=now + timedelta(seconds=2))
    assert reclaimed is not None


def test_active_storage_configuration_and_primary_image_concurrency(runtime):
    repository = StoreForwardRepository(runtime)
    configurations = (_configuration(), _configuration())
    with ThreadPoolExecutor(max_workers=2) as executor:
        tuple(executor.map(repository.create_configuration, configurations))
    with runtime.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(StorageConfigurationORM).where(
            StorageConfigurationORM.active.is_(True)
        )) == 1

    product_id = _seed_product(runtime)
    file_ids = (_managed_file(runtime, product_id), _managed_file(runtime, product_id))
    now = datetime.now(timezone.utc)
    with runtime.session_factory.begin() as session:
        for order, file_id in enumerate(file_ids):
            session.add(ProductFileRelationORM(
                internal_id=str(uuid4()), product_id=str(product_id), managed_file_id=str(file_id),
                kind="IMAGE", attachment_category=None, is_primary=False,
                sort_order=order, caption=None, created_at=now, archived_at=None,
            ))
    managed = ManagedFileRepository(runtime)
    with ThreadPoolExecutor(max_workers=2) as executor:
        tuple(executor.map(
            lambda file_id: managed.set_primary_image(product_id=product_id, file_id=file_id),
            file_ids,
        ))
    with runtime.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProductFileRelationORM).where(
            ProductFileRelationORM.product_id == str(product_id),
            ProductFileRelationORM.is_primary.is_(True),
        )) == 1


def test_managed_file_relation_unique_conflict_is_controlled(runtime):
    product_id = _seed_product(runtime)
    file_id = _managed_file(runtime, product_id)
    now = datetime.now(timezone.utc)

    def insert_relation():
        try:
            with runtime.session_factory.begin() as session:
                session.add(ProductFileRelationORM(
                    internal_id=str(uuid4()), product_id=str(product_id),
                    managed_file_id=str(file_id), kind="ATTACHMENT",
                    attachment_category="DRAWING", is_primary=False,
                    sort_order=0, caption=None, created_at=now, archived_at=None,
                ))
            return "committed"
        except IntegrityError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(lambda _: insert_relation(), range(2)))
    assert sorted(outcomes) == ["committed", "conflict"]
    with runtime.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProductFileRelationORM).where(
            ProductFileRelationORM.managed_file_id == str(file_id)
        )) == 1
