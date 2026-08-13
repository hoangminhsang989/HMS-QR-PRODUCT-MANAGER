from datetime import datetime, timezone
from decimal import Decimal

import pytest

from packages.domain.product import Product, ProductStatus, ProductValidationError
from packages.domain.product_code import ProductCodeService


def test_product_validates_fields_and_uses_utc_actor_metadata():
    product = Product.create(product_code="sp-2026-000001", company="HMS", part_name="Bracket",
                             quantity="12.5", unit="pcs", actor="user-01", status="new")
    assert product.product_code == "SP-2026-000001"
    assert product.quantity == Decimal("12.5")
    assert product.status is ProductStatus.NEW
    assert product.created_at.tzinfo is not None and product.created_at.utcoffset().total_seconds() == 0
    assert product.created_by == product.updated_by == "user-01"
    with pytest.raises(ProductValidationError):
        Product.create(product_code="SP-1", company="", part_name="x", quantity=1, unit="pcs", actor="u")
    with pytest.raises(ProductValidationError):
        Product.create(product_code="SP-1", company="HMS", part_name="x", quantity=0, unit="pcs", actor="u")


def test_product_code_generation_is_centralized():
    service = ProductCodeService()
    assert service.generate(1, today=datetime(2026, 1, 1).date()) == "SP-2026-000001"
    with pytest.raises(ValueError):
        service.normalize("bad code")
