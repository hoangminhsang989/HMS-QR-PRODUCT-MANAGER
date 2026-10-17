"""HTTP client for managed product files; Desktop never opens server storage."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from packages.application.lan_transport import lan_urlopen
from uuid import UUID


class FileApiError(RuntimeError):
    """A safe, user-presentable failure returned by the central file server."""


class FileApiClient:
    def __init__(self, base_url: str, *, access_token: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("HMS_QR_SERVER_URL must start with http:// or https://.")
        if not access_token:
            raise ValueError("A LAN access token is required for managed files.")
        self.access_token = access_token
        self.timeout = timeout

    def _request(self, method: str, path: str, *, query: dict[str, object] | None = None,
                 content: bytes | None = None, json_body: dict[str, object] | None = None) -> Any:
        url = f"{self.base_url}/files{path}"
        if query:
            encoded = urlencode({key: value for key, value in query.items() if value is not None})
            if encoded:
                url = f"{url}?{encoded}"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}
        body = content
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(json_body).encode("utf-8")
        elif content is not None:
            headers["Content-Type"] = "application/octet-stream"
        try:
            with lan_urlopen(Request(url, data=body, headers=headers, method=method), timeout=self.timeout) as response:
                data = response.read()
                content_type = response.headers.get_content_type() if getattr(response, "headers", None) else "application/json"
                return data if "application/json" not in content_type else json.loads(data.decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", {})
                message = detail.get("message") if isinstance(detail, dict) else str(detail)
            except (UnicodeDecodeError, json.JSONDecodeError):
                message = None
            raise FileApiError(message or f"Server returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise FileApiError("Không thể kết nối tới server tệp trung tâm.") from exc

    def list_images(self, product_id: UUID) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/v1/products/{product_id}/images")["items"]

    def list_attachments(self, product_id: UUID) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/v1/products/{product_id}/attachments")["items"]

    def upload_image(self, product_id: UUID, filename: str, mime_type: str, content: bytes, *, make_primary: bool) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/products/{product_id}/images", content=content, query={
            "filename": filename, "declared_mime": mime_type, "make_primary": str(make_primary).lower(),
        })

    def upload_attachment(self, product_id: UUID, filename: str, mime_type: str, content: bytes) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/products/{product_id}/attachments", content=content, query={
            "filename": filename, "declared_mime": mime_type, "category": "OTHER",
        })

    def download(self, file_id: UUID) -> bytes:
        return self._request("GET", f"/api/v1/files/{file_id}")

    def set_primary(self, product_id: UUID, file_id: UUID) -> None:
        self._request("POST", f"/api/v1/products/{product_id}/images/{file_id}/primary")

    def archive(self, file_id: UUID) -> None:
        self._request("DELETE", f"/api/v1/files/{file_id}")


__all__ = ["FileApiClient", "FileApiError"]
