"""HTTP implementation of the Product Master application boundary for Desktop."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from packages.domain.product import Product, ProductStatus
from packages.domain.repository import ProductPage


class ProductApiError(RuntimeError):
    """A safe, user-presentable failure returned by the central server."""


class ProductApiClient:
    """ProductService-compatible client; Desktop never opens the central database."""

    def __init__(self, base_url: str, *, access_token: str | None = None, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("HMS_QR_SERVER_URL must start with http:// or https://.")
        self.timeout = timeout
        self.access_token = access_token
        self._versions: dict[str, datetime] = {}

    def login(self, username: str, password: str) -> dict[str, str]:
        result = self._request("POST", "/admin-api/api/v1/auth/login", payload={"username": username, "password": password})
        self.access_token = str(result["access_token"])
        return {key: str(value) for key, value in result.items()}

    def verify_server_readiness(self) -> None:
        """Fail Desktop startup before credentials are sent to an unready central server."""
        try:
            result = self._request("GET", "/health/readiness/database")
        except ProductApiError as exc:
            raise ProductApiError("Server trung tâm chưa sẵn sàng. Kiểm tra kết nối LAN và database/schema trên Server rồi thử lại.") from exc
        state = result.get("state", result.get("status", "")) if isinstance(result, dict) else ""
        if str(state).upper() not in {"READY", "SẴN SÀNG"}:
            raise ProductApiError("Server trung tâm chưa xác nhận database sẵn sàng. Liên hệ quản trị Server.")

    @staticmethod
    def _json_value(value: object) -> object:
        if isinstance(value, (date, datetime, Decimal, UUID, ProductStatus)):
            return str(value)
        return value

    @staticmethod
    def _product(payload: dict[str, Any]) -> Product:
        delivery = payload.get("delivery_schedule")
        return Product(
            internal_id=UUID(payload["internal_id"]),
            product_code=payload["product_code"],
            company=payload["company"],
            part_name=payload["part_name"],
            quantity=Decimal(str(payload["quantity"])),
            unit=payload["unit"],
            material=payload.get("material"),
            requester=payload.get("requester"),
            surface_treatment=payload.get("surface_treatment"),
            outsourced=bool(payload["outsourced"]),
            size=payload.get("size"),
            notes=payload.get("notes"),
            delivery_schedule=date.fromisoformat(delivery) if delivery else None,
            status=ProductStatus(payload["status"]),
            created_at=datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00")),
            created_by=payload["created_by"],
            updated_by=payload["updated_by"],
            outsourced_company=payload.get("outsourced_company"),
        )

    def _request(self, method: str, path: str, *, actor: str | None = None,
                 query: dict[str, object] | None = None, payload: dict[str, object] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            encoded = urlencode({key: self._json_value(value) for key, value in query.items() if value is not None})
            if encoded:
                url = f"{url}?{encoded}"
        headers = {"Accept": "application/json"}
        body = None
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        elif actor:
            headers["X-Actor"] = actor
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, default=self._json_value).encode("utf-8")
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                response = json.loads(exc.read().decode("utf-8"))
                error = response.get("error") or response.get("detail") or {}
                message = error.get("message") if isinstance(error, dict) else str(error)
            except (UnicodeDecodeError, json.JSONDecodeError):
                message = None
            raise ProductApiError(message or f"Server returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise ProductApiError("Không thể kết nối tới server trung tâm.") from exc

    def _remember(self, product: Product) -> Product:
        self._versions[str(product.internal_id)] = product.updated_at
        return product

    def create_product(self, *, actor: str, product_code: str | None = None, **data: object) -> Product:
        payload = {"product_code": product_code, **data}
        return self._remember(self._product(self._request("POST", "/api/v1/products", actor=actor, payload=payload)))

    def get_product(self, identifier: UUID | str) -> Product:
        return self._remember(self._product(self._request("GET", f"/api/v1/products/{identifier}")))

    def update_product(self, identifier: UUID | str, *, actor: str, expected_updated_at: datetime | None = None, **changes: object) -> Product:
        version = expected_updated_at or self._versions.get(str(identifier))
        if version is None:
            raise ProductApiError("Hãy làm mới sản phẩm trước khi cập nhật để tránh ghi đè dữ liệu máy khác.")
        changes["expected_updated_at"] = version
        return self._remember(self._product(self._request("PATCH", f"/api/v1/products/{identifier}", actor=actor, payload=changes)))

    def list_products(self, *, page: int = 1, page_size: int = 50, search: str | None = None,
                      status: ProductStatus | str | None = None, sort_by: str = "updated_at",
                      descending: bool = True, delivery_start: date | None = None,
                      delivery_end: date | None = None) -> ProductPage:
        result = self._request("GET", "/api/v1/products", query={
            "page": page, "page_size": page_size, "search": search, "status": status,
            "sort_by": sort_by, "descending": descending,
            "delivery_start": delivery_start, "delivery_end": delivery_end,
        })
        items = [self._remember(self._product(item)) for item in result["items"]]
        return ProductPage(
            items=items,
            total=int(result["total"]), page=int(result["page"]), page_size=int(result["page_size"]),
        )


__all__ = ["ProductApiClient", "ProductApiError"]
