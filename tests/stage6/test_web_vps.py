from __future__ import annotations
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

SOURCE_ROOT = Path(__file__).resolve().parents[2]
VPS_PAGE = SOURCE_ROOT / "web" / "vps.html"


@pytest.fixture()
def client():
    import apps.server.app as app_module

    with TestClient(app_module.app) as test_client:
        yield test_client


def test_vps_page_served(client):
    response = client.get("/tracking/mobile/vps")
    assert response.status_code == 200
    assert response.content == VPS_PAGE.read_bytes()


def test_vps_page_keeps_the_manual_origin_screen(client):
    response = client.get("/tracking/mobile/vps")
    assert "conn-modal" in response.text
    assert "hms-server-origin" in response.text


def test_both_pages_share_the_same_api_calls(client):
    """The two builds differ only in the entry point, never in the API.

    A phone that moves between the LAN and the relay must not discover that a
    feature works on one build and 404s on the other. Both pages therefore call
    the same paths through the same ``serverOrigin`` variable.
    """
    lan = (SOURCE_ROOT / "web" / "lan.html").read_text(encoding="utf-8")
    vps = VPS_PAGE.read_text(encoding="utf-8")
    assert "serverOrigin + '/tracking'" in lan
    assert "serverOrigin + '/tracking'" in vps
    assert "serverOrigin + '/files'" in lan
    assert "serverOrigin + '/files'" in vps
