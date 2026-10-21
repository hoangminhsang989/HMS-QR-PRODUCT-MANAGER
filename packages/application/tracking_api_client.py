"""HTTP client for central Tracking operations used by LAN Desktop clients."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from packages.application.lan_transport import lan_urlopen
from uuid import UUID


class TrackingApiError(RuntimeError):
    """A safe, user-presentable failure returned by the central tracking server."""


class TrackingApiClient:
    def __init__(self, base_url: str, *, access_token: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Địa chỉ HMS QR Server phải bắt đầu bằng http:// hoặc https://.")
        if not access_token:
            raise ValueError("Cần có token truy cập LAN để theo dõi.")
        self.access_token = access_token
        self.timeout = timeout

    def _request(self, method: str, path: str, *, query: dict[str, object] | None = None,
                 payload: dict[str, object] | None = None) -> Any:
        url = f"{self.base_url}/tracking{path}"
        if query:
            encoded = urlencode({key: value for key, value in query.items() if value is not None})
            if encoded:
                url = f"{url}?{encoded}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, default=str).encode("utf-8")
        try:
            with lan_urlopen(Request(url, data=body, headers=headers, method=method), timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", {})
                message = detail.get("message") if isinstance(detail, dict) else str(detail)
            except (UnicodeDecodeError, json.JSONDecodeError):
                message = None
            raise TrackingApiError(message or f"Server trung tâm trả về lỗi HTTP {exc.code}.") from exc
        except URLError as exc:
            raise TrackingApiError("Không thể kết nối tới server theo dõi trung tâm.") from exc

    def list_tracking(self, *, search: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/tracking-items", query={"search": search, "status": status})["items"]

    def issue_qr(self, identifier: UUID | str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/tracking-items/{identifier}/qr")

    def workflow_summary(self, item_id: UUID | str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/tracking-items/{item_id}/workflow-summary")

    def history(self, item_id: UUID | str) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/v1/tracking-items/{item_id}/history")["items"]

    def submit_workflow(self, item_id: UUID | str, event_type: str, **payload: object) -> dict[str, Any]:
        routes = {"QC_CHECKED": "qc-events", "SHORTAGE_REPORTED": "qc-events", "QC_NG_RETURNED_TO_MACHINING": "qc-events", "PACKED": "packing-events", "DELIVERED": "delivery-events", "GENERAL_REPORT": "reports"}
        return self._request("POST", f"/api/v1/tracking-items/{item_id}/{routes[event_type]}", payload={"event_type": event_type, **payload})


__all__ = ["TrackingApiClient", "TrackingApiError"]
