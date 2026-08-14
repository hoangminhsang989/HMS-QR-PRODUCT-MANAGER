from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.sqlalchemy_models import Base, ProductORM
from packages.persistence.storage_models import ManagedFileORM, ProductFileRelationORM
from packages.persistence.store_forward_models import ArchiveTransferJobORM, StorageConfigurationORM
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.domain.store_forward import StorageConfiguration
from packages.storage import FilesystemStorage, LocalDevStorage
from packages.storage.managed_files import ManagedFileService
from packages.storage.store_forward import StoreForwardService
from uuid import uuid4


@pytest.fixture
def managed_file_env(tmp_path):
    database = tmp_path / "managed-files.sqlite"
    engine = create_engine(f"sqlite:///{database.as_posix()}", future=True)
    Base.metadata.create_all(engine)
    product_id = "00000000-0000-0000-0000-000000000601"
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(ProductORM.__table__.insert().values(
            internal_id=product_id,
            product_code="SP-R008-001",
            company="HMS",
            part_name="Stage 6 Plate",
            quantity=1,
            unit="pcs",
            material="SUS304",
            requester=None,
            surface_treatment=None,
            outsourced=False,
            size="10x20",
            notes=None,
            delivery_schedule=None,
            status="NEW",
            created_at=now,
            updated_at=now,
            created_by="fixture",
            updated_by="fixture",
        ))
    storage = LocalDevStorage(tmp_path / "managed-storage")
    repository = ManagedFileRepository(engine)
    service = ManagedFileService(repository, storage)
    return {
        "engine": engine,
        "product_id": __import__("uuid").UUID(product_id),
        "repository": repository,
        "storage": storage,
        "service": service,
        "root": tmp_path,
    }


@pytest.fixture
def store_forward_env(tmp_path):
    database = tmp_path / "store-forward.sqlite"
    engine = create_engine(f"sqlite:///{database.as_posix()}", future=True)
    Base.metadata.create_all(engine)
    product_id = "00000000-0000-0000-0000-000000000609"
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(ProductORM.__table__.insert().values(
            internal_id=product_id, product_code="SP-R009-001", company="HMS",
            part_name="R009 Store Forward", quantity=1, unit="pcs", material="SUS304",
            requester=None, surface_treatment=None, outsourced=False, size="10x20",
            notes=None, delivery_schedule=None, status="NEW", created_at=now,
            updated_at=now, created_by="fixture", updated_by="fixture",
        ))
    local_root = tmp_path / "local-ingest"
    archive_root = tmp_path / "archive-target"
    local = LocalDevStorage(local_root)
    archive_root.mkdir()
    archive = FilesystemStorage(archive_root, create_root=False)
    managed_repository = ManagedFileRepository(engine)
    queue_repository = StoreForwardRepository(engine)
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
        "engine": engine, "database": database,
        "product_id": __import__("uuid").UUID(product_id),
        "managed_repository": managed_repository,
        "queue_repository": queue_repository,
        "configuration": configuration,
        "local": local, "archive": archive,
        "local_root": local_root, "archive_root": archive_root,
        "transfer": transfer, "managed": managed, "root": tmp_path,
    }
