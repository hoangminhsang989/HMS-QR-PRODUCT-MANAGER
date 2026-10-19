from datetime import datetime, timezone

import pytest

from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.sqlalchemy_product_repository import SqlAlchemyProductRepository
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.domain.product import Product, ProductStatus
from packages.domain.store_forward import StorageConfiguration
from packages.storage import FilesystemStorage, LocalDevStorage
from packages.storage.managed_files import ManagedFileService
from packages.storage.store_forward import StoreForwardService
from packages.sqlengine import Database
from packages.sqlengine.migrations import load_migration_modules, run_migrations
from uuid import uuid4

from pathlib import Path

ENGINE_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations" / "engine"


def _engine_database(tmp_path, name):
    database = Database(tmp_path / name)
    run_migrations(
        database,
        load_migration_modules(ENGINE_MIGRATIONS),
        now=lambda: datetime.now(timezone.utc).isoformat(),
    )
    return database


def _seed_product(database, product_id, product_code, part_name):
    repository = SqlAlchemyProductRepository(database)
    now = datetime.now(timezone.utc)
    repository.create(Product(
        internal_id=uuid4().__class__(product_id),
        product_code=product_code,
        company="HMS",
        part_name=part_name,
        quantity=1,
        unit="pcs",
        material="SUS304",
        requester=None,
        surface_treatment=None,
        outsourced=False,
        size="10x20",
        notes=None,
        delivery_schedule=None,
        status=ProductStatus.NEW,
        created_at=now,
        updated_at=now,
        created_by="fixture",
        updated_by="fixture",
    ))


@pytest.fixture
def managed_file_env(tmp_path):
    database = _engine_database(tmp_path, "managed-files-engine")
    product_id = "00000000-0000-0000-0000-000000000601"
    _seed_product(database, product_id, "SP-R008-001", "Stage 6 Plate")
    storage = LocalDevStorage(tmp_path / "managed-storage")
    repository = ManagedFileRepository(database)
    service = ManagedFileService(repository, storage)
    return {
        "engine": database,
        "product_id": __import__("uuid").UUID(product_id),
        "repository": repository,
        "storage": storage,
        "service": service,
        "root": tmp_path,
    }


@pytest.fixture
def store_forward_env(tmp_path):
    database = _engine_database(tmp_path, "store-forward-engine")
    product_id = "00000000-0000-0000-0000-000000000609"
    _seed_product(database, product_id, "SP-R009-001", "R009 Store Forward")
    local_root = tmp_path / "local-ingest"
    archive_root = tmp_path / "archive-target"
    local = LocalDevStorage(local_root)
    archive_root.mkdir()
    archive = FilesystemStorage(archive_root, create_root=False)
    managed_repository = ManagedFileRepository(database)
    queue_repository = StoreForwardRepository(database)
    configuration = StorageConfiguration(
        configuration_id=uuid4(), local_ingest_root=str(local_root),
        archive_target_root=str(archive_root), grace_period_hours=24,
        retry_schedule_seconds=(60, 300, 900, 1800, 3600),
        warning_free_bytes=300, critical_free_bytes=200,
        upload_refusal_free_bytes=100,
    )
    queue_repository.create_configuration(configuration)
    transfer = StoreForwardService(
        queue_repository, managed_repository, local,
        archive_factory=lambda _: archive,
        capacity_probe=lambda _: (10_000, 1_000, 9_000),
    )
    managed = ManagedFileService(
        managed_repository, local, archive_coordinator=transfer
    )
    return {
        "engine": database, "database": tmp_path / "store-forward-engine",
        "product_id": __import__("uuid").UUID(product_id),
        "managed_repository": managed_repository,
        "queue_repository": queue_repository,
        "configuration": configuration,
        "local": local, "archive": archive,
        "local_root": local_root, "archive_root": archive_root,
        "transfer": transfer, "managed": managed, "root": tmp_path,
    }
