from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.sqlalchemy_models import Base, ProductORM
from packages.persistence.storage_models import ManagedFileORM, ProductFileRelationORM
from packages.storage import LocalDevStorage
from packages.storage.managed_files import ManagedFileService


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
