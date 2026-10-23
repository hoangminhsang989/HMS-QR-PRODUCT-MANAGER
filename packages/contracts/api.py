"""Stable API schemas and serialization helpers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.domain.product import Product, ProductStatus


class ProductPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_code: str | None = Field(default=None, max_length=64)
    company: str = Field(default="", max_length=255)
    part_name: str = Field(max_length=255)
    quantity: Decimal = Field(ge=0)
    unit: str = Field(min_length=1, max_length=32)
    material: str | None = Field(default=None, max_length=255)
    requester: str | None = Field(default=None, max_length=255)
    surface_treatment: str | None = Field(default=None, max_length=255)
    outsourced: bool = False
    outsourced_company: str | None = Field(default=None, max_length=255)
    size: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    delivery_schedule: date | None = None
    status: ProductStatus = ProductStatus.NEW


class ProductPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_code: str | None = Field(default=None, max_length=64)
    company: str | None = Field(default=None, max_length=255)
    part_name: str | None = Field(default=None, max_length=255)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    material: str | None = Field(default=None, max_length=255)
    requester: str | None = Field(default=None, max_length=255)
    surface_treatment: str | None = Field(default=None, max_length=255)
    outsourced: bool | None = None
    outsourced_company: str | None = Field(default=None, max_length=255)
    size: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    delivery_schedule: date | None = None
    status: ProductStatus | None = None
    expected_updated_at: datetime | None = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    internal_id: UUID
    product_code: str
    company: str
    part_name: str
    quantity: Decimal
    unit: str
    material: str | None
    requester: str | None
    surface_treatment: str | None
    outsourced: bool
    outsourced_company: str | None
    size: str | None
    notes: str | None
    delivery_schedule: date | None
    status: ProductStatus
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


class ProductPageResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


def to_response(product: Product) -> ProductResponse:
    return ProductResponse.model_validate(product)
