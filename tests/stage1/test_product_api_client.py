from datetime import date
from decimal import Decimal
import io
from urllib.error import URLError

import pytest

from packages.application.product_api_client import ProductApiClient, ProductApiError
from packages.application.file_api_client import FileApiClient
from packages.application.tracking_api_client import TrackingApiClient


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.body


def test_product_api_client_serializes_product_workflow(monkeypatch):
    seen = []
    product = {
        "internal_id": "00000000-0000-0000-0000-000000000001", "product_code": "P-001",
        "company": "HMS", "part_name": "Plate", "quantity": "4.50", "unit": "pcs",
        "material": None, "requester": None, "surface_treatment": None, "outsourced": False,
        "outsourced_company": None, "size": None, "notes": None, "delivery_schedule": "2026-09-19",
        "status": "NEW", "created_at": "2026-09-19T00:00:00Z", "updated_at": "2026-09-19T00:00:00Z",
        "created_by": "desktop-user", "updated_by": "desktop-user",
    }

    def fake_urlopen(request, timeout):
        seen.append((request, timeout))
        return _Response(__import__("json").dumps({"items": [product], "total": 1, "page": 1, "page_size": 200}).encode())

    monkeypatch.setattr("packages.application.product_api_client.lan_urlopen", fake_urlopen)
    page = ProductApiClient("http://server:8000").list_products(
        page_size=200, status="NEW", delivery_start=date(2026, 9, 1), delivery_end=date(2026, 10, 1),
    )
    request, timeout = seen[0]
    assert request.full_url == "http://server:8000/api/v1/products?page=1&page_size=200&status=NEW&sort_by=updated_at&descending=True&delivery_start=2026-09-01&delivery_end=2026-10-01"
    assert timeout == 15.0
    assert page.items[0].quantity == Decimal("4.50")
    assert page.items[0].delivery_schedule == date(2026, 9, 19)


def test_product_api_client_reports_connection_failures(monkeypatch):
    monkeypatch.setattr(
        "packages.application.product_api_client.lan_urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
    )
    with pytest.raises(ProductApiError, match="Không thể kết nối"):
        ProductApiClient("https://server.example").get_product("P-001")


def test_product_api_client_sends_loaded_version_when_updating(monkeypatch):
    seen = []
    product = {
        "internal_id": "00000000-0000-0000-0000-000000000001", "product_code": "P-001",
        "company": "HMS", "part_name": "Plate", "quantity": "4.50", "unit": "pcs",
        "material": None, "requester": None, "surface_treatment": None, "outsourced": False,
        "outsourced_company": None, "size": None, "notes": None, "delivery_schedule": None,
        "status": "NEW", "created_at": "2026-09-19T00:00:00Z", "updated_at": "2026-09-19T00:00:00Z",
        "created_by": "desktop-user", "updated_by": "desktop-user",
    }

    def fake_urlopen(request, timeout):
        seen.append(request)
        return _Response(__import__("json").dumps(product).encode())

    monkeypatch.setattr("packages.application.product_api_client.lan_urlopen", fake_urlopen)
    client = ProductApiClient("http://server:8000")
    client.get_product(product["internal_id"])
    client.update_product(product["internal_id"], actor="desktop-user", status="IN_PROGRESS")
    assert __import__("json").loads(seen[1].data)["expected_updated_at"] == "2026-09-19 00:00:00+00:00"


def test_product_api_client_login_uses_admin_auth_endpoint(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout):
        seen.append(request)
        return _Response(b'{"access_token":"signed-token","role":"EDITOR","username":"lan-user"}')

    monkeypatch.setattr("packages.application.product_api_client.lan_urlopen", fake_urlopen)
    client = ProductApiClient("http://server:8000")
    assert client.login("lan-user", "") ["access_token"] == "signed-token"
    assert seen[0].full_url == "http://server:8000/admin-api/api/v1/auth/login"
    assert seen[0].get_header("Authorization") is None


def test_product_api_client_requires_database_readiness_before_desktop_login(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout):
        seen.append(request)
        return _Response(b'{"state":"READY"}')

    monkeypatch.setattr("packages.application.product_api_client.lan_urlopen", fake_urlopen)
    client = ProductApiClient("http://server:8000")
    client.verify_server_readiness()
    assert seen[0].full_url == "http://server:8000/health/readiness/database"


def test_product_api_client_readiness_hides_connection_detail(monkeypatch):
    monkeypatch.setattr(
        "packages.application.product_api_client.lan_urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("internal host detail")),
    )
    with pytest.raises(ProductApiError, match="Server trung tâm chưa sẵn sàng") as error:
        ProductApiClient("https://server.example").verify_server_readiness()
    assert "internal host detail" not in str(error.value)


def test_file_api_client_sends_bearer_token_and_uploads_bytes(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout):
        seen.append((request, timeout))
        return _Response(b'{"items": []}')

    monkeypatch.setattr("packages.application.file_api_client.lan_urlopen", fake_urlopen)
    client = FileApiClient("http://server:8000", access_token="signed-token")
    assert client.list_images("00000000-0000-0000-0000-000000000001") == []
    assert seen[0][0].full_url == "http://server:8000/files/api/v1/products/00000000-0000-0000-0000-000000000001/images"
    assert seen[0][0].get_header("Authorization") == "Bearer signed-token"
    client.upload_attachment("00000000-0000-0000-0000-000000000001", "note.txt", "text/plain", b"note")
    assert seen[1][0].data == b"note"
    assert "filename=note.txt" in seen[1][0].full_url


def test_tracking_api_client_uses_bearer_token_for_central_list(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout):
        seen.append(request)
        return _Response(b'{"items": []}')

    monkeypatch.setattr("packages.application.tracking_api_client.lan_urlopen", fake_urlopen)
    assert TrackingApiClient("http://server:8000", access_token="signed-token").list_tracking(status="NEW") == []
    assert seen[0].full_url == "http://server:8000/tracking/api/v1/tracking-items?status=NEW"
    assert seen[0].get_header("Authorization") == "Bearer signed-token"
