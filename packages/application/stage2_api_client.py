"""Authenticated Stage 2 HTTP client for API-only Desktop access."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from packages.application.lan_transport import lan_urlopen


class Stage2ApiError(RuntimeError):
    """A safe, user-presentable central-server error."""


class Stage2ApiClient:
    def __init__(self, base_url: str, *, access_token: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout = timeout

    def _request(self, method: str, path: str, *, query: dict[str, object] | None = None,
                 payload: dict[str, object] | None = None) -> Any:
        url = f"{self.base_url}/stage2{path}"
        if query:
            encoded = urlencode({key: value for key, value in query.items() if value is not None})
            if encoded:
                url = f"{url}?{encoded}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            with lan_urlopen(Request(url, data=body, headers=headers, method=method), timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", {})
                message = detail.get("message") if isinstance(detail, dict) else str(detail)
            except (UnicodeDecodeError, json.JSONDecodeError):
                message = None
            raise Stage2ApiError(message or f"Server trung tâm trả về lỗi HTTP {exc.code}.") from exc
        except URLError as exc:
            raise Stage2ApiError("Không thể kết nối tới server trung tâm.") from exc

    def list_customers(self, *, search: str | None = None, active: bool | None = None) -> dict[str, Any]:
        return self._request("GET", "/api/v1/customers", query={"search": search, "active": active})

    def create_customer(self, *, name: str, customer_code: str | None = None,
                        short_name: str | None = None, phone: str | None = None) -> dict[str, Any]:
        return self._request("POST", "/api/v1/customers", payload={
            "name": name, "customer_code": customer_code or None,
            "short_name": short_name or None, "phone": phone or None,
        })

    def list_purchase_orders(self, *, customer_id: str | None = None, status: str | None = None) -> dict[str, Any]:
        return self._request("GET", "/api/v1/purchase-orders", query={"customer_id": customer_id, "status": status})

    def create_purchase_order(self, *, po_number: str, customer_id: str, po_date: str,
                              requested_delivery_date: str | None = None, notes: str | None = None) -> dict[str, Any]:
        return self._request("POST", "/api/v1/purchase-orders", payload={
            "po_number": po_number, "customer_id": customer_id, "po_date": po_date,
            "requested_delivery_date": requested_delivery_date or None, "notes": notes or None,
        })

    def list_products(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/products?page_size=200"
        request = Request(url, headers={"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"})
        try:
            with lan_urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            raise Stage2ApiError("Không thể tải Product Master từ server trung tâm.") from exc

    def list_purchase_order_lines(self, po_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/purchase-orders/{po_id}/lines")

    def create_purchase_order_line(self, *, po_id: str, product_id: str, line_number: int,
                                   ordered_quantity: str, unit: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/purchase-orders/{po_id}/lines", payload={
            "product_id": product_id, "line_number": line_number,
            "ordered_quantity": ordered_quantity, "unit": unit,
        })

    def list_delivery_schedules(self, line_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/purchase-order-lines/{line_id}/delivery-schedules")

    def create_delivery_schedule(self, *, line_id: str, ordered_quantity: str, planned_date: str,
                                 planned_quantity: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/purchase-order-lines/{line_id}/delivery-schedules", query={"ordered_quantity": ordered_quantity}, payload={
            "planned_date": planned_date, "planned_quantity": planned_quantity,
        })

    def list_production_runs(self, *, line_id: str | None = None) -> dict[str, Any]:
        return self._request("GET", "/api/v1/production-runs", query={"po_line_id": line_id})

    def create_production_run(self, *, line_id: str, product_id: str, ordered_quantity: str,
                              planned_quantity: str, planned_start: str, planned_finish: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/production-runs", payload={
            "po_line_id": line_id, "product_id": product_id, "ordered_quantity": ordered_quantity,
            "planned_quantity": planned_quantity, "planned_start": planned_start,
            "planned_finish": planned_finish,
        })


__all__ = ["Stage2ApiClient", "Stage2ApiError"]
