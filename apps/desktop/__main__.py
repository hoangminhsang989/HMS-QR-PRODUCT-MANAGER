from config.environments import load_config
from packages.application.product_service import ProductService
from packages.persistence.sqlite_product_repository import SQLiteProductRepository
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.storage.managed_files import ManagedFileService
from packages.storage.service import FilesystemStorage
from packages.storage.store_forward import StoreForwardService
from sqlalchemy import create_engine
from .product_master_window import run


if __name__ == "__main__":
    config = load_config()
    product_service = ProductService(SQLiteProductRepository(config.database_url.removeprefix("sqlite:///")))
    engine = create_engine(config.database_url, future=True)
    managed_repository = ManagedFileRepository(engine)
    queue_repository = StoreForwardRepository(engine)
    local_storage = FilesystemStorage(config.storage_root, create_root=False)
    transfer_service = StoreForwardService(queue_repository, managed_repository, local_storage)
    managed_service = ManagedFileService(
        managed_repository, local_storage, archive_coordinator=transfer_service
    )
    run(product_service, managed_service=managed_service, transfer_service=transfer_service)
