"""Product Master domain model and validation rules."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID, uuid4


class ProductValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class ProductStatus(StrEnum):
    NEW = "NEW"
    WAITING = "WAITING"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_QC = "WAITING_QC"
    QC_PASS = "QC_PASS"
    QC_NG = "QC_NG"
    REWORK = "REWORK"
    PACKED = "PACKED"
    DELIVERED = "DELIVERED"
    HOLD = "HOLD"
    CANCELLED = "CANCELLED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def required_text(value: object, field: str, max_length: int = 255) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductValidationError(field, "Trường này là bắt buộc.")
    result = value.strip()
    if len(result) > max_length:
        raise ProductValidationError(field, f"Tối đa {max_length} ký tự.")
    return result


def optional_text(value: object | None, field: str, max_length: int = 2000) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ProductValidationError(field, "Giá trị phải là văn bản.")
    result = value.strip()
    if len(result) > max_length:
        raise ProductValidationError(field, f"Tối đa {max_length} ký tự.")
    return result or None


def positive_quantity(value: object) -> Decimal:
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ProductValidationError("quantity", "Số lượng phải là số.") from exc
    if not quantity.is_finite() or quantity <= 0:
        raise ProductValidationError("quantity", "Số lượng phải lớn hơn 0.")
    return quantity


def parse_status(value: ProductStatus | str) -> ProductStatus:
    try:
        return value if isinstance(value, ProductStatus) else ProductStatus(str(value).strip().upper())
    except ValueError as exc:
        raise ProductValidationError("status", "Trạng thái không hợp lệ.") from exc


def parse_delivery_date(value: date | datetime | str | None) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ProductValidationError("delivery_schedule", "Ngày giao phải theo YYYY-MM-DD.") from exc


@dataclass(frozen=True, slots=True)
class Product:
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
    size: str | None
    notes: str | None
    delivery_schedule: date | None
    status: ProductStatus
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str

    @classmethod
    def create(cls, *, product_code: str, company: str, part_name: str,
               quantity: object, unit: str, actor: str, material: str | None = None,
               requester: str | None = None, surface_treatment: str | None = None,
               outsourced: bool = False, size: str | None = None,
               notes: str | None = None, delivery_schedule: date | str | None = None,
               status: ProductStatus | str = ProductStatus.NEW,
               internal_id: UUID | None = None, now: datetime | None = None) -> "Product":
        timestamp = now or utc_now()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ProductValidationError("timestamp", "Timestamp phải có múi giờ UTC.")
        timestamp = timestamp.astimezone(timezone.utc)
        return cls(
            internal_id or uuid4(), required_text(product_code, "product_code", 64).upper(),
            required_text(company, "company"), required_text(part_name, "part_name"),
            positive_quantity(quantity), required_text(unit, "unit", 32),
            optional_text(material, "material", 255), optional_text(requester, "requester", 255),
            optional_text(surface_treatment, "surface_treatment", 255), bool(outsourced),
            optional_text(size, "size", 255), optional_text(notes, "notes"),
            parse_delivery_date(delivery_schedule), parse_status(status), timestamp, timestamp,
            required_text(actor, "actor", 128), required_text(actor, "actor", 128),
        )

    def update(self, *, actor: str, now: datetime | None = None, **changes: object) -> "Product":
        allowed = {"company", "part_name", "quantity", "unit", "material", "requester",
                   "surface_treatment", "outsourced", "size", "notes", "delivery_schedule", "status"}
        unknown = set(changes) - allowed
        if unknown:
            raise ProductValidationError("payload", "Không thể sửa: " + ", ".join(sorted(unknown)))
        values = {
            "company": required_text(changes.get("company", self.company), "company"),
            "part_name": required_text(changes.get("part_name", self.part_name), "part_name"),
            "quantity": positive_quantity(changes.get("quantity", self.quantity)),
            "unit": required_text(changes.get("unit", self.unit), "unit", 32),
            "material": optional_text(changes.get("material", self.material), "material", 255),
            "requester": optional_text(changes.get("requester", self.requester), "requester", 255),
            "surface_treatment": optional_text(changes.get("surface_treatment", self.surface_treatment), "surface_treatment", 255),
            "outsourced": bool(changes.get("outsourced", self.outsourced)),
            "size": optional_text(changes.get("size", self.size), "size", 255),
            "notes": optional_text(changes.get("notes", self.notes), "notes"),
            "delivery_schedule": parse_delivery_date(changes.get("delivery_schedule", self.delivery_schedule)),
            "status": parse_status(changes.get("status", self.status)),
            "updated_by": required_text(actor, "actor", 128),
            "updated_at": (now or utc_now()).astimezone(timezone.utc),
        }
        return replace(self, **values)


__all__ = ["Product", "ProductStatus", "ProductValidationError", "parse_status", "utc_now"]
