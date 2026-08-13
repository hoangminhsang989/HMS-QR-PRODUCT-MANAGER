from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from packages.generated_assets import require_test_output_path
from packages.qr.payload import QrPayload, QrPayloadService

@dataclass(frozen=True, slots=True)
class LabelData:
    product_name: str
    customer_name: str
    product_code: str
    tracking_code: str
    material: str | None
    quantity: str
    unit: str
    size: str | None
    surface_treatment: str | None
    delivery_date: str
    order_code: str
    customer_po_number: str
    notes: str | None


@dataclass(frozen=True, slots=True)
class LabelTemplate:
    name: str = "TEM TIÊU CHUẨN"
    visible_fields: tuple[str, ...] = (
        "product_name", "customer_name", "product_code", "tracking_code",
        "material", "quantity", "unit", "size", "surface_treatment",
        "delivery_date", "order_code", "customer_po_number", "notes",
    )


class LabelDataService:
    def __init__(self, repository):
        self.repository = repository

    def load(self, identifier) -> LabelData:
        return LabelData(**self.repository.label_data(identifier))


class LabelTemplateRenderer:
    LABELS = {
        "product_name": "Tên sản phẩm", "customer_name": "Khách hàng",
        "product_code": "Mã sản phẩm", "tracking_code": "Mã theo dõi",
        "material": "Vật liệu", "quantity": "Số lượng", "unit": "Đơn vị",
        "size": "Kích thước / Size", "surface_treatment": "Xử lý bề mặt",
        "delivery_date": "Ngày giao hàng", "order_code": "Mã đơn",
        "customer_po_number": "PO", "notes": "Ghi chú",
    }

    def render(self, data: LabelData, qr_payload: QrPayload, qr_image_uri: str, template: LabelTemplate | None = None) -> str:
        if not qr_image_uri.startswith("data:image/png;base64,"):
            raise ValueError("label QR component must be a PNG data URI")
        selected = template or LabelTemplate()
        rows = "".join(
            f"<dt>{escape(self.LABELS[field])}</dt><dd>{escape(str(getattr(data, field) or ''))}</dd>"
            for field in selected.visible_fields
        )
        encoded = escape(QrPayloadService().encode(qr_payload), quote=True)
        image = escape(qr_image_uri, quote=True)
        return f"<!doctype html><html lang='vi'><meta charset='utf-8'><title>{escape(selected.name)}</title><body><h1>{escape(selected.name)}</h1><img class='qr' alt='QR' src='{image}' data-qr-payload='{encoded}'><dl>{rows}</dl></body></html>"


class LabelPrintExportService:
    def export_html(self, rendered_label: str, path: str | Path) -> Path:
        target = require_test_output_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered_label, encoding="utf-8")
        return target


LabelExportService = LabelPrintExportService
