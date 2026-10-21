from __future__ import annotations

import json
from dataclasses import dataclass

from packages.domain.tracking import TrackingError


QR_PAYLOAD_FIELDS = (
    "product_name",
    "customer_name",
    "product_code",
    "tracking_code",
)


@dataclass(frozen=True, slots=True)
class QrPayload:
    product_name: str
    customer_name: str
    product_code: str
    tracking_code: str

    def as_dict(self) -> dict[str, str]:
        return {field: getattr(self, field) for field in QR_PAYLOAD_FIELDS}


class QrPayloadService:
    """Canonical QR contract: UTF-8 JSON containing exactly four business fields."""

    def encode(self, payload: QrPayload) -> str:
        values = payload.as_dict()
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise TrackingError("Các trường trong mã QR không được để trống.")
        return json.dumps(values, ensure_ascii=False, separators=(",", ":"))

    def decode(self, encoded: str) -> QrPayload:
        try:
            values = json.loads(encoded)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TrackingError("Mã QR không hợp lệ.") from exc
        if not isinstance(values, dict) or tuple(values) != QR_PAYLOAD_FIELDS:
            raise TrackingError("Mã QR phải chứa đúng bốn trường quy định.")
        payload = QrPayload(**values)
        self.encode(payload)
        return payload
