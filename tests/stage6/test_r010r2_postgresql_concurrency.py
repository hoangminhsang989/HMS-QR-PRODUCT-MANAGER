"""Real PostgreSQL row-locking and concurrency acceptance for R010R2."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from config.environments import AppConfig, Environment
from config.paths import TEST_ROOT
from packages.application.stage2_service import Stage2Service
from packages.application.tracking_service import TrackingService
from packages.application.workflow_services import DeliveryService, PackingService, QcService
from packages.domain.attachments import (
    ManagedFile,
    ManagedFileSource,
    ManagedFileStatus,
    ProductFileKind,
    ProductFileRelation,
)
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
from tests.stage6.true_concurrency import DecisiveSqlWindow, run_worker_pair


CONCURRENCY_REPEAT_ITERATIONS = 10
CONCURRENCY_EVIDENCE_MATRIX = (
    ("ROW_LOCK", "SELECT FOR UPDATE", "decisive SQL barrier + held result", "pg_stat_activity Lock wait", "one effective event", "missing row lock"),
    ("IDEMPOTENCY", "row lock + unique request UUID", "decisive SQL barrier", "one winner and one semantic replay/conflict", "one committed event", "duplicate or incompatible reuse"),
    ("ENSURE_JOB", "unique managed_file_id", "INSERT barrier", "concurrent insert arbitration", "one transfer job", "duplicate job"),
    ("LEASE", "conditional UPDATE", "UPDATE barrier", "one rowcount winner", "one active lease", "double ownership"),
    ("ACTIVE_CONFIG", "transaction advisory lock", "advisory-lock barrier", "serialized activation", "one active config", "multiple active configs"),
    ("PRIMARY_IMAGE", "product-scoped advisory lock", "advisory-lock barrier", "serialized primary update", "one primary", "multiple primaries"),
    ("FILE_RELATION", "PK/unique constraints", "INSERT barrier", "one commit and one conflict", "one logical relation", "duplicate relation"),
)


def _postgresql_url() -> str:
    value = (
        os.environ.get("HMS_QR_R010R2_POSTGRESQL_URL", "").strip()
        or os.environ.get("HMS_QR_R010M1_POSTGRESQL_URL", "").strip()
    )
    if not value:
        pytest.skip("isolated R010R2 PostgreSQL runtime is not configured")
    return value


def _sql_contains(*tokens: str):
    lowered = tuple(token.casefold() for token in tokens)
    return lambda statement: all(token in statement.casefold() for token in lowered)


def _wait_for_backend_lock(runtime, backend_pid: int) -> tuple[str, str]:
    deadline = monotonic() + 5.0
    poll_gate = Event()
    with runtime.engine.connect() as connection:
        while monotonic() < deadline:
            row = connection.execute(text(
                "SELECT wait_event_type, wait_event FROM pg_stat_activity WHERE pid = :pid"
            ), {"pid": backend_pid}).one()
            if row.wait_event_type == "Lock":
                return row.wait_event_type, row.wait_event
            poll_gate.wait(0.02)
    raise AssertionError(f"backend {backend_pid} was not observed waiting on a PostgreSQL lock")


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


def test_true_row_lock_serializes_overlapping_idempotent_requests(runtime):
    blocking_observations = 0
    for _iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        _, item, operator = _seed_tracking(runtime)
        request_id = uuid4()

        def submit():
            return QcService(WorkflowRepository(runtime)).submit(
                request_id=request_id, tracking_item_id=item.internal_id,
                event_type=WorkflowEventType.QC_CHECKED, quantity=Decimal("10"),
                notes="PG true overlap", actor_user_id=operator.internal_id,
                actor_display_name=operator.display_name,
            )

        predicate = _sql_contains("from order_tracking_items", "for update")
        with DecisiveSqlWindow(
            runtime.engine, predicate, hold_first_result=True
        ) as window:
            def observe_wait(futures):
                nonlocal blocking_observations
                window.assert_distinct_backends()
                waiter_pid = next(
                    pid for pid in window.backend_pids.values()
                    if pid != window.holder_backend_pid
                )
                assert not futures[0].done() and not futures[1].done()
                wait_type, _wait_event = _wait_for_backend_lock(runtime, waiter_pid)
                assert wait_type == "Lock"
                assert not futures[0].done() and not futures[1].done()
                blocking_observations += 1

            outcomes = run_worker_pair(
                window, submit, submit, while_first_result_held=observe_wait
            )

        assert all(outcome.error is None for outcome in outcomes)
        assert outcomes[0].value.internal_id == outcomes[1].value.internal_id
        with runtime.session_factory() as session:
            rows = session.scalar(select(func.count()).select_from(
                TrackingWorkflowEventORM
            ).where(TrackingWorkflowEventORM.request_id == str(request_id)))
        assert rows == 1
    assert blocking_observations == CONCURRENCY_REPEAT_ITERATIONS


def test_overlapping_incompatible_idempotency_reuse_fails_closed(runtime):
    for _iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        _, item, operator = _seed_tracking(runtime)
        request_id = uuid4()

        def submit(quantity: Decimal):
            return QcService(WorkflowRepository(runtime)).submit(
                request_id=request_id, tracking_item_id=item.internal_id,
                event_type=WorkflowEventType.QC_CHECKED, quantity=quantity,
                notes="PG incompatible overlap", actor_user_id=operator.internal_id,
                actor_display_name=operator.display_name,
            )

        predicate = _sql_contains("from order_tracking_items", "for update")
        with DecisiveSqlWindow(
            runtime.engine, predicate, hold_first_result=True
        ) as window:
            def observe_wait(futures):
                waiter_pid = next(
                    pid for pid in window.backend_pids.values()
                    if pid != window.holder_backend_pid
                )
                assert not futures[0].done() and not futures[1].done()
                assert _wait_for_backend_lock(runtime, waiter_pid)[0] == "Lock"

            outcomes = run_worker_pair(
                window,
                lambda: submit(Decimal("10")),
                lambda: submit(Decimal("11")),
                while_first_result_held=observe_wait,
            )

        errors = tuple(outcome.error for outcome in outcomes if outcome.error is not None)
        committed = tuple(outcome.value for outcome in outcomes if outcome.error is None)
        assert len(committed) == 1
        assert len(errors) == 1 and isinstance(errors[0], TrackingError)
        assert "idempotency" in str(errors[0])
        with runtime.session_factory() as session:
            rows = session.scalar(select(func.count()).select_from(
                TrackingWorkflowEventORM
            ).where(TrackingWorkflowEventORM.request_id == str(request_id)))
        assert rows == 1


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


def test_true_concurrent_ensure_job_converges_to_one_row(runtime):
    for _iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        product_id = _seed_product(runtime)
        file_id = _managed_file(runtime, product_id)
        configuration = StoreForwardRepository(runtime).create_configuration(_configuration())

        def ensure():
            return StoreForwardRepository(runtime).ensure_job(
                file_id, configuration.configuration_id
            )

        with DecisiveSqlWindow(
            runtime.engine, _sql_contains("insert into archive_transfer_jobs")
        ) as window:
            outcomes = run_worker_pair(window, ensure, ensure)
        assert all(outcome.error is None for outcome in outcomes)
        assert outcomes[0].value.job_id == outcomes[1].value.job_id
        with runtime.session_factory() as session:
            count = session.scalar(select(func.count()).select_from(
                ArchiveTransferJobORM
            ).where(ArchiveTransferJobORM.managed_file_id == str(file_id)))
        assert count == 1


def test_true_concurrent_lease_claim_and_stale_recovery(runtime):
    pre_expiry_second_owner_count = 0
    post_expiry_recovery_owner_count = 0
    # claim_next is intentionally queue-wide. Quarantine jobs left QUEUED by
    # earlier module tests so each repetition contains exactly one eligible
    # job and therefore measures competing ownership of that same job.
    with runtime.session_factory.begin() as session:
        session.execute(update(ArchiveTransferJobORM).where(
            ArchiveTransferJobORM.state.in_((
                ArchiveTransferState.LOCAL_READY.value,
                ArchiveTransferState.TRANSFER_QUEUED.value,
                ArchiveTransferState.TRANSFER_FAILED_RETRYABLE.value,
            ))
        ).values(state=ArchiveTransferState.TRANSFER_FAILED_PERMANENT.value))
    for iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        product_id = _seed_product(runtime)
        file_id = _managed_file(runtime, product_id)
        repository = StoreForwardRepository(runtime)
        configuration = repository.create_configuration(_configuration())
        repository.ensure_job(file_id, configuration.configuration_id)
        now = datetime.now(timezone.utc)

        def claim(label: str, at: datetime):
            return StoreForwardRepository(runtime).claim_next(
                worker_id=f"worker-{iteration}-{label}", now=at, lease_seconds=1
            )

        with DecisiveSqlWindow(
            runtime.engine,
            _sql_contains("update archive_transfer_jobs", "lease_token"),
        ) as claim_window:
            outcomes = run_worker_pair(
                claim_window, lambda: claim("A", now), lambda: claim("B", now)
            )
        assert all(outcome.error is None for outcome in outcomes)
        active = tuple(outcome.value for outcome in outcomes if outcome.value is not None)
        assert len(active) == 1
        assert active[0].state is ArchiveTransferState.TRANSFERRING
        with runtime.session_factory() as session:
            owners = session.scalar(select(func.count()).select_from(
                ArchiveTransferJobORM
            ).where(
                ArchiveTransferJobORM.internal_id == str(active[0].job_id),
                ArchiveTransferJobORM.state == ArchiveTransferState.TRANSFERRING.value,
                ArchiveTransferJobORM.lease_token.is_not(None),
            ))
        assert owners == 1

        pre_expiry = now + timedelta(milliseconds=500)
        with DecisiveSqlWindow(
            runtime.engine,
            _sql_contains("select archive_transfer_jobs.internal_id", "limit"),
        ) as pre_expiry_window:
            denied = run_worker_pair(
                pre_expiry_window,
                lambda: claim("pre-A", pre_expiry),
                lambda: claim("pre-B", pre_expiry),
            )
        pre_expiry_second_owner_count += sum(
            outcome.value is not None for outcome in denied
        )
        assert all(outcome.error is None for outcome in denied)
        assert all(outcome.value is None for outcome in denied)

        expired = now + timedelta(seconds=2)
        assert repository.recover_expired_leases(at=expired) == 1
        reclaimed = repository.claim_next(
            worker_id=f"worker-{iteration}-recovery", now=expired
        )
        assert reclaimed is not None
        post_expiry_recovery_owner_count += 1

    assert pre_expiry_second_owner_count == 0
    assert post_expiry_recovery_owner_count == CONCURRENCY_REPEAT_ITERATIONS


def test_true_concurrent_active_storage_configuration(runtime):
    for iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        repository = StoreForwardRepository(runtime)
        configurations = [_configuration(), _configuration()]
        if iteration % 2:
            configurations.reverse()
        with DecisiveSqlWindow(
            runtime.engine, _sql_contains("pg_advisory_xact_lock")
        ) as window:
            outcomes = run_worker_pair(
                window,
                lambda: repository.create_configuration(configurations[0]),
                lambda: repository.create_configuration(configurations[1]),
            )
        assert all(outcome.error is None for outcome in outcomes)
        with runtime.session_factory() as session:
            active = session.scalar(select(func.count()).select_from(
                StorageConfigurationORM
            ).where(StorageConfigurationORM.active.is_(True)))
        assert active == 1


def test_true_concurrent_product_primary_selection(runtime):
    for iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        product_id = _seed_product(runtime)
        file_ids = [_managed_file(runtime, product_id), _managed_file(runtime, product_id)]
        if iteration % 2:
            file_ids.reverse()
        now = datetime.now(timezone.utc)
        with runtime.session_factory.begin() as session:
            for order, file_id in enumerate(file_ids):
                session.add(ProductFileRelationORM(
                    internal_id=str(uuid4()), product_id=str(product_id),
                    managed_file_id=str(file_id), kind="IMAGE",
                    attachment_category=None, is_primary=False, sort_order=order,
                    caption=None, created_at=now, archived_at=None,
                ))
        with DecisiveSqlWindow(
            runtime.engine, _sql_contains("pg_advisory_xact_lock")
        ) as window:
            outcomes = run_worker_pair(
                window,
                lambda: ManagedFileRepository(runtime).set_primary_image(
                    product_id=product_id, file_id=file_ids[0]
                ),
                lambda: ManagedFileRepository(runtime).set_primary_image(
                    product_id=product_id, file_id=file_ids[1]
                ),
            )
        assert all(outcome.error is None for outcome in outcomes)
        with runtime.session_factory() as session:
            primary_count = session.scalar(select(func.count()).select_from(
                ProductFileRelationORM
            ).where(
                ProductFileRelationORM.product_id == str(product_id),
                ProductFileRelationORM.is_primary.is_(True),
            ))
        assert primary_count == 1


def test_true_concurrent_managed_file_relation_conflict(runtime):
    for _iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        product_id = _seed_product(runtime)
        file_id = uuid4()
        relation_id = uuid4()
        now = datetime.now(timezone.utc)
        managed_file = ManagedFile(
            file_id=file_id, original_filename="drawing.pdf",
            stored_filename=f"{file_id}.pdf", storage_key=f"r010r2a1/{file_id}.pdf",
            category="DRAWING", media_type="application/pdf", extension=".pdf",
            size_bytes=8, sha256="0" * 64, status=ManagedFileStatus.PENDING,
            source=ManagedFileSource.UPLOAD, version=1, created_at=now,
            created_by="r010r2a1", updated_at=now,
        )
        relation = ProductFileRelation(
            relation_id=relation_id, product_id=product_id, managed_file_id=file_id,
            kind=ProductFileKind.ATTACHMENT, attachment_category="DRAWING",
            is_primary=False, sort_order=0, caption=None, created_at=now,
        )

        def create_relation():
            return ManagedFileRepository(runtime).create_pending(managed_file, relation)

        with DecisiveSqlWindow(
            runtime.engine, _sql_contains("insert into managed_files")
        ) as window:
            outcomes = run_worker_pair(window, create_relation, create_relation)
        errors = tuple(outcome.error for outcome in outcomes if outcome.error is not None)
        committed = tuple(outcome for outcome in outcomes if outcome.error is None)
        assert len(committed) == 1
        assert len(errors) == 1 and isinstance(errors[0], IntegrityError)
        with runtime.session_factory() as session:
            managed_count = session.scalar(select(func.count()).select_from(
                ManagedFileORM
            ).where(ManagedFileORM.internal_id == str(file_id)))
            relation_count = session.scalar(select(func.count()).select_from(
                ProductFileRelationORM
            ).where(ProductFileRelationORM.managed_file_id == str(file_id)))
        assert managed_count == 1
        assert relation_count == 1


def test_concurrency_evidence_matrix_is_complete():
    assert len(CONCURRENCY_EVIDENCE_MATRIX) == 7
    assert {row[0] for row in CONCURRENCY_EVIDENCE_MATRIX} == {
        "ROW_LOCK", "IDEMPOTENCY", "ENSURE_JOB", "LEASE",
        "ACTIVE_CONFIG", "PRIMARY_IMAGE", "FILE_RELATION",
    }
    assert all(all(str(value).strip() for value in row) for row in CONCURRENCY_EVIDENCE_MATRIX)
