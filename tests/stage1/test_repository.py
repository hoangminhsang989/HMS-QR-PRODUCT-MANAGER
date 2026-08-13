from pathlib import Path

from packages.domain.product import ProductStatus
from packages.domain.repository import DuplicateProductCode, ProductNotFound
from packages.persistence.sqlite_product_repository import SQLiteProductRepository
from packages.application.product_service import ProductService


def test_sqlite_repository_crud_search_filter(tmp_path: Path):
    service = ProductService(SQLiteProductRepository(tmp_path / "db" / "stage1.sqlite"))
    first = service.create_product(actor="tester", company="HMS", part_name="Bracket", quantity=2, unit="pcs", material="Steel")
    second = service.create_product(actor="tester", company="ACME", part_name="Cover", quantity=3, unit="pcs", status=ProductStatus.HOLD)
    assert service.get_product(first.product_code).internal_id == first.internal_id
    assert service.list_products(search="brack").total == 1
    assert service.list_products(status=ProductStatus.HOLD).items == (second,)
    assert service.update_product(first.internal_id, actor="editor", status=ProductStatus.IN_PROGRESS).updated_by == "editor"
    try:
        service.create_product(actor="tester", product_code=first.product_code, company="x", part_name="y", quantity=1, unit="pcs")
    except DuplicateProductCode:
        pass
    else:
        raise AssertionError("duplicate code did not fail")
    try:
        service.get_product("missing")
    except ProductNotFound:
        pass
    else:
        raise AssertionError("not found did not fail")
