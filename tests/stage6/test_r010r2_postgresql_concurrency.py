"""Real SQL-engine concurrency acceptance for R010R2.

The engine serializes every write transaction on one lock, so these tests prove
the arbitration the engine actually performs: two overlapping operations reach
the decisive SQL together and exactly one of them wins.  Each case keeps the
invariant the PostgreSQL runtime used to guarantee (one committed event, one
transfer job, one active lease, one active configuration, one primary image,
one logical relation).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from config.environments import AppConfig, Environment
from config.paths import SOURCE_ROOT, require_test_root
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
from packages.persistence.database import DatabaseRuntime
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.stage2_repository import Stage2Repository
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.persistence.tracking_repository import TrackingRepository
from packages.persistence.workflow_repository import WorkflowRepository
from packages.sqlengine import Database
from packages.sqlengine.errors import IntegrityError
from packages.sqlengine.migrations import load_migration_modules, run_migrations
from tests.stage6.true_concurrency import DecisiveSqlWindow, run_worker_pair


CONCURRENCY_REPEAT_ITERATIONS = 10
CONCURRENCY_EVIDENCE_MATRIX = (
    ("SERIALIZATION", "single writer lock", "decisive SQL barrier", "one effective event", "missing arbitration"),
    ("IDEMPOTENCY", "row lock + unique request UUID", "decisive SQL barrier", "one winner and one semantic replay/conflict", "one committed event", "duplicate or incompatible reuse"),
    ("ENSURE_JOB", "unique managed_file_id", "INSERT barrier", "concurrent insert arbitration", "one transfer job", "duplicate job"),
    ("LEASE", "conditional UPDATE", "UPDATE barrier", "one rowcount winner", "one active lease", "double ownership"),
    ("ACTIVE_CONFIG", "serialized activation", "activation barrier", "one active config", "multiple active configs"),
    ("PRIMARY_IMAGE", "product-scoped serialization", "primary-update barrier", "one primary", "multiple primaries"),
    ("FILE_RELATION", "PK/unique constraints", "INSERT barrier", "one commit and one conflict", "one logical relation", "duplicate relation"),
)


def _now() -> str:
    return "2026-01-01T00:00:00+00:00"


def _sql_contains(*tokens: str):
    lowered = tuple(token.casefold() for token in tokens)
    return lambda statement: all(token in statement.casefold() for token in lowered)


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    path = tmp_path_factory.mktemp("engine-concurrency") / "database"
    database = Database(path)
    run_migrations(
        database,
        load_migration_modules(SOURCE_ROOT / "migrations" / "engine"),
        now=_now,
    )
    value = DatabaseRuntime(
        AppConfig(Environment.PROD, "sqlite:///concurrency.sqlite", "test"),
        database,
        path,
    )
    yield value
    database.close()


def _seed_product(runtime, *, code: str | None = None) -> UUID:
    product_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()
    with runtime.database.transaction() as transaction:
        transaction.execute(
            "INSERT INTO products (internal_id, product_code, company, part_name, "
            "quantity, unit, outsourced, status, created_at, updated_at, "
            "created_by, updated_by) VALUES (?, ?, 'HMS', 'Concurrency Plate', "
            "?, 'pcs', 0, 'NEW', ?, ?, 'r010r2', 'r010r2')",
            [str(product_id), code or f"ENGINE-{uuid4().hex[:10]}", Decimal("100.0000"), now, now],
        )
    return product_id


def _seed_tracking(runtime):
    token = uuid4().hex[:10]
    now = datetime.now(timezone.utc).isoformat()
    customer_id, product_id, po_id, line_id = (uuid4() for _ in range(4))
    with runtime.database.transaction() as transaction:
        transaction.execute(
            "INSERT INTO customers (internal_id, customer_code, name, active, "
            "created_at, updated_at, created_by, updated_by) "
            "VALUES (?, ?, 'Engine Customer', 1, ?, ?, 'r010r2', 'r010r2')",
            [str(customer_id), f"CUS-{token}", now, now],
        )
        transaction.execute(
            "INSERT INTO products (internal_id, product_code, company, part_name, "
            "quantity, unit, outsourced, status, created_at, updated_at, "
            "created_by, updated_by) VALUES (?, ?, 'HMS', 'Engine Tracking Part', "
            "?, 'pcs', 0, 'NEW', ?, ?, 'r010r2', 'r010r2')",
            [str(product_id), f"PROD-{token}", Decimal("100.0000"), now, now],
        )
        transaction.execute(
            "INSERT INTO purchase_orders (internal_id, po_number, internal_order_code, "
            "customer_id, po_date, requested_delivery_date, status, created_at, "
            "updated_at, created_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED', "
            "?, ?, 'r010r2', 'r010r2')",
            [
                str(po_id), f"PO-{token}", f"ORD-{token}", str(customer_id),
                date(2026, 8, 15), date(2026, 8, 30), now, now,
            ],
        )
        transaction.execute(
            "INSERT INTO purchase_order_lines (internal_id, po_id, product_id, "
            "line_number, ordered_quantity, unit) VALUES (?, ?, ?, 1, ?, 'pcs')",
            [str(line_id), str(po_id), str(product_id), Decimal("100.0000")],
        )
    repository = TrackingRepository(runtime)
    service = TrackingService(repository)
    item = service.create_item(
        purchase_order_id=po_id, purchase_order_line_id=line_id, product_id=product_id,
        customer_id=customer_id, quantity=Decimal("100"), unit="pcs",
        delivery_date=date(2026, 8, 30), actor="r010r2",
    )
    operator = repository.add_operator(Operator.create(f"Operator {token}"))
    return service, item, operator


def _event_count(runtime, request_id) -> int:
    return int(runtime.database.scalar(
        "SELECT COUNT(*) FROM tracking_workflow_events WHERE request_id = ?",
        [str(request_id)],
    ) or 0)


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


def test_overlapping_idempotent_requests_commit_exactly_one_event(runtime):
    for _iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        _, item, operator = _seed_tracking(runtime)
        request_id = uuid4()

        def submit():
            return QcService(WorkflowRepository(runtime)).submit(
                request_id=request_id, tracking_item_id=item.internal_id,
                event_type=WorkflowEventType.QC_CHECKED, quantity=Decimal("10"),
                notes="engine true overlap", actor_user_id=operator.internal_id,
                actor_display_name=operator.display_name,
            )

        with DecisiveSqlWindow(
            runtime.database,
            _sql_contains("from order_tracking_items"),
            hold_first_result=True,
        ) as window:
            def observe_wait(futures):
                window.assert_distinct_workers()
                assert not futures[0].done() and not futures[1].done()

            outcomes = run_worker_pair(
                window, submit, submit, while_first_result_held=observe_wait
            )

        assert all(outcome.error is None for outcome in outcomes)
        assert outcomes[0].value.internal_id == outcomes[1].value.internal_id
        assert _event_count(runtime, request_id) == 1


def test_overlapping_incompatible_idempotency_reuse_fails_closed(runtime):
    for _iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        _, item, operator = _seed_tracking(runtime)
        request_id = uuid4()

        def submit(quantity: Decimal):
            return QcService(WorkflowRepository(runtime)).submit(
                request_id=request_id, tracking_item_id=item.internal_id,
                event_type=WorkflowEventType.QC_CHECKED, quantity=quantity,
                notes="engine incompatible overlap", actor_user_id=operator.internal_id,
                actor_display_name=operator.display_name,
            )

        with DecisiveSqlWindow(
            runtime.database,
            _sql_contains("from order_tracking_items"),
            hold_first_result=True,
        ) as window:
            def observe_wait(futures):
                assert not futures[0].done() and not futures[1].done()

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
        assert "trùng lặp" in str(errors[0])
        assert _event_count(runtime, request_id) == 1


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
    root = Path(require_test_root(), "r010r2-engine-concurrency", token)
    return StorageConfiguration(
        configuration_id=uuid4(), local_ingest_root=str(root / "local"),
        archive_target_root=str(root / "archive"), grace_period_hours=24,
        retry_schedule_seconds=(60, 300), warning_free_bytes=300,
        critical_free_bytes=200, upload_refusal_free_bytes=100,
    )


def _managed_file(runtime) -> UUID:
    file_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()
    with runtime.database.transaction() as transaction:
        transaction.execute(
            "INSERT INTO managed_files (internal_id, original_filename, "
            "stored_filename, storage_key, category, media_type, extension, "
            "size_bytes, sha256, status, source, version, created_at, created_by, "
            "updated_at) VALUES (?, 'drawing.pdf', ?, ?, 'DRAWING', "
            "'application/pdf', '.pdf', 8, ?, 'READY', 'UPLOAD', 1, ?, 'r010r2', ?)",
            [
                str(file_id), f"{file_id}.pdf", f"r010r2/{file_id}.pdf",
                "0" * 64, now, now,
            ],
        )
    return file_id


def _count(runtime, table: str, where: str, parameters: list) -> int:
    return int(runtime.database.scalar(
        f"SELECT COUNT(*) FROM {table} WHERE {where}", parameters
    ) or 0)


def test_concurrent_ensure_job_converges_to_one_row(runtime):
    for _iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        file_id = _managed_file(runtime)
        configuration = StoreForwardRepository(runtime).create_configuration(_configuration())

        def ensure():
            return StoreForwardRepository(runtime).ensure_job(
                file_id, configuration.configuration_id
            )

        with DecisiveSqlWindow(
            runtime.database, _sql_contains("insert into archive_transfer_jobs")
        ) as window:
            outcomes = run_worker_pair(window, ensure, ensure)
        assert all(outcome.error is None for outcome in outcomes)
        assert outcomes[0].value.job_id == outcomes[1].value.job_id
        assert _count(
            runtime, "archive_transfer_jobs", "managed_file_id = ?", [str(file_id)]
        ) == 1


def test_concurrent_lease_claim_and_stale_recovery(runtime):
    pre_expiry_second_owner_count = 0
    post_expiry_recovery_owner_count = 0
    # claim_next is intentionally queue-wide. Quarantine jobs left QUEUED by
    # earlier module tests so each repetition contains exactly one eligible
    # job and therefore measures competing ownership of that same job.
    with runtime.database.transaction() as transaction:
        transaction.execute(
            "UPDATE archive_transfer_jobs SET state = ? WHERE state IN (?, ?, ?)",
            [
                ArchiveTransferState.TRANSFER_FAILED_PERMANENT.value,
                ArchiveTransferState.LOCAL_READY.value,
                ArchiveTransferState.TRANSFER_QUEUED.value,
                ArchiveTransferState.TRANSFER_FAILED_RETRYABLE.value,
            ],
        )
    for iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        file_id = _managed_file(runtime)
        repository = StoreForwardRepository(runtime)
        configuration = repository.create_configuration(_configuration())
        repository.ensure_job(file_id, configuration.configuration_id)
        now = datetime.now(timezone.utc)

        def claim(label: str, at: datetime):
            return repository.claim_next(
                worker_id=f"worker-{iteration}-{label}", now=at, lease_seconds=1
            )

        with DecisiveSqlWindow(
            runtime.database,
            _sql_contains("update archive_transfer_jobs", "lease_token"),
        ) as claim_window:
            outcomes = run_worker_pair(
                claim_window, lambda: claim("A", now), lambda: claim("B", now)
            )
        assert all(outcome.error is None for outcome in outcomes)
        active = tuple(outcome.value for outcome in outcomes if outcome.value is not None)
        assert len(active) == 1
        assert active[0].state is ArchiveTransferState.TRANSFERRING
        assert _count(
            runtime, "archive_transfer_jobs",
            "internal_id = ? AND state = ? AND lease_token IS NOT NULL",
            [str(active[0].job_id), ArchiveTransferState.TRANSFERRING.value],
        ) == 1

        pre_expiry = now + timedelta(milliseconds=500)
        with DecisiveSqlWindow(
            runtime.database,
            _sql_contains("select internal_id from archive_transfer_jobs", "state in"),
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


def test_concurrent_active_storage_configuration(runtime):
    for iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        repository = StoreForwardRepository(runtime)
        configurations = [_configuration(), _configuration()]
        if iteration % 2:
            configurations.reverse()
        with DecisiveSqlWindow(
            runtime.database, _sql_contains("update storage_configurations", "active")
        ) as window:
            outcomes = run_worker_pair(
                window,
                lambda: repository.create_configuration(configurations[0]),
                lambda: repository.create_configuration(configurations[1]),
            )
        assert all(outcome.error is None for outcome in outcomes)
        assert _count(runtime, "storage_configurations", "active = 1", []) == 1


def test_concurrent_product_primary_selection(runtime):
    for iteration in range(CONCURRENCY_REPEAT_ITERATIONS):
        product_id = _seed_product(runtime)
        file_ids = [_managed_file(runtime), _managed_file(runtime)]
        if iteration % 2:
            file_ids.reverse()
        now = datetime.now(timezone.utc).isoformat()
        with runtime.database.transaction() as transaction:
            for order, file_id in enumerate(file_ids):
                transaction.execute(
                    "INSERT INTO product_file_relations (internal_id, product_id, "
                    "managed_file_id, kind, is_primary, sort_order, created_at) "
                    "VALUES (?, ?, ?, 'IMAGE', 0, ?, ?)",
                    [str(uuid4()), str(product_id), str(file_id), order, now],
                )
        with DecisiveSqlWindow(
            runtime.database, _sql_contains("update product_file_relations", "is_primary")
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
        assert _count(
            runtime, "product_file_relations",
            "product_id = ? AND is_primary = 1", [str(product_id)],
        ) == 1


def test_concurrent_managed_file_relation_conflict(runtime):
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
            runtime.database, _sql_contains("insert into managed_files")
        ) as window:
            outcomes = run_worker_pair(window, create_relation, create_relation)
        errors = tuple(outcome.error for outcome in outcomes if outcome.error is not None)
        committed = tuple(outcome for outcome in outcomes if outcome.error is None)
        assert len(committed) == 1
        assert len(errors) == 1 and isinstance(errors[0], IntegrityError)
        assert _count(
            runtime, "managed_files", "internal_id = ?", [str(file_id)]
        ) == 1
        assert _count(
            runtime, "product_file_relations", "managed_file_id = ?", [str(file_id)]
        ) == 1


def test_concurrency_evidence_matrix_is_complete():
    assert len(CONCURRENCY_EVIDENCE_MATRIX) == 7
    assert {row[0] for row in CONCURRENCY_EVIDENCE_MATRIX} == {
        "SERIALIZATION", "IDEMPOTENCY", "ENSURE_JOB", "LEASE",
        "ACTIVE_CONFIG", "PRIMARY_IMAGE", "FILE_RELATION",
    }
    assert all(all(str(value).strip() for value in row) for row in CONCURRENCY_EVIDENCE_MATRIX)
