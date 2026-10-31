from __future__ import annotations
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
SOURCE_ROOT = Path(__file__).resolve().parents[2]
LAN_PAGE = SOURCE_ROOT / "web" / "lan.html"
@pytest.fixture()
def client():
    import apps.server.app as app_module

    with TestClient(app_module.app) as test_client:
        yield test_client


def test_lan_page_served_from_the_server(client):
    response = client.get("/tracking/mobile/lan")
    assert response.status_code == 200
    assert "conn-modal" not in response.text
    assert "ĐỊA CHỈ MÁY CHỦ" not in response.text


def test_lan_page_is_byte_identical_to_disk(client):
    response = client.get("/tracking/mobile/lan")
    assert response.content == LAN_PAGE.read_bytes()


def test_lan_page_resolves_api_to_same_origin(client):
    page = LAN_PAGE.read_text(encoding="utf-8")
    assert "serverOrigin + '/tracking'" in page
    assert "location.origin" in page
    assert "hms-server-origin" not in page
