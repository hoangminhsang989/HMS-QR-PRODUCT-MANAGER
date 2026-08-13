from config.environments import load_config
from packages.application.product_service import ProductService
from packages.persistence.sqlite_product_repository import SQLiteProductRepository
from .product_master_window import run


if __name__ == "__main__":
    config = load_config()
    run(ProductService(SQLiteProductRepository(config.database_url.removeprefix("sqlite:///"))))
