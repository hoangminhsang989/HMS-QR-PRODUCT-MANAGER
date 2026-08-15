from config.environments import Environment, load_config
from packages.application.product_service import ProductService
from packages.persistence.sqlite_product_repository import SQLiteProductRepository
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.persistence.database import create_database_runtime, sqlite_path
from packages.storage.managed_files import ManagedFileService
from packages.storage.service import FilesystemStorage
from packages.storage.store_forward import StoreForwardService
from .product_master_window import run


if __name__ == "__main__":
    config = load_config()
    if config.environment is not Environment.DEV:
        raise RuntimeError(
            "Desktop STAGING/PROD requires the reviewed Machine A server API endpoint."
        )
    product_service = ProductService(SQLiteProductRepository(sqlite_path(config.database_url)))
    runtime = create_database_runtime(config)
    managed_repository = ManagedFileRepository(runtime)
    queue_repository = StoreForwardRepository(runtime)
    local_storage = FilesystemStorage(config.storage_root, create_root=False)
    transfer_service = StoreForwardService(queue_repository, managed_repository, local_storage)
    managed_service = ManagedFileService(
        managed_repository, local_storage, archive_coordinator=transfer_service
    )
    run(product_service, managed_service=managed_service, transfer_service=transfer_service)
