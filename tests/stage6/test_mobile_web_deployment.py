"""Mobile web app: reachable page, runtime-configured origin, opt-in CORS.

The mobile page used to live inside ``apps/mobile/web.py`` as one Python string
with ``const api = '/tracking'`` baked in, which pinned it to same-origin. It now
lives in ``web/index.html`` and is served by both the LAN server and Vercel, so
these tests pin the two properties that make that split safe: the page loads
without a session (it carries the login form), and cross-origin access is off
unless an operator explicitly allows an origin.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SOURCE_ROOT = Path(__file__).resolve().parents[2]
MOBILE_PAGE = SOURCE_ROOT / "web" / "index.html"


@pytest.fixture()
def client():
    import apps.server.app as app_module

    with TestClient(app_module.app) as test_client:
        yield test_client


def test_mobile_page_loads_without_a_session(client):
    """The page must be reachable unauthenticated: it holds the login form."""

    response = client.get("/tracking/mobile")
    assert response.status_code == 200
    assert "conn-modal" in response.text
    assert "login-modal" in response.text


def test_mobile_page_resolves_its_server_origin_at_runtime(client):
    response = client.get("/tracking/mobile")
    assert "const api = '/tracking';" not in response.text
    assert "hms-server-origin" in response.text
    assert "fetch('/api" not in response.text
    assert "fetch('/files" not in response.text


def test_tracking_api_still_requires_a_token(client):
    response = client.get("/tracking/api/v1/operators")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_cors_is_off_unless_an_origin_is_configured(client):
    """A LAN-only deployment must stay same-origin, exactly as before."""

    response = client.get("/tracking/api/v1/operators", headers={"Origin": "https://example.test"})
    assert response.status_code == 401
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_only_the_configured_origin(monkeypatch):
    import apps.server.app as app_module

    monkeypatch.setenv("HMS_QR_CORS_ORIGINS", "https://hms-qr.vercel.app")
    api = app_module.build_api(app_config=app_module.SERVER_APP_CONFIG, database_runtime=app_module.SERVER_DATABASE_RUNTIME)
    with TestClient(api) as test_client:
        allowed = test_client.options(
            "/tracking/api/v1/operators",
            headers={
                "Origin": "https://hms-qr.vercel.app",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "https://hms-qr.vercel.app"
        assert "Authorization" in allowed.headers["access-control-allow-headers"]

        refused = test_client.options(
            "/tracking/api/v1/operators",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in refused.headers


def test_login_endpoint_is_reachable_cross_origin(monkeypatch):
    import apps.server.app as app_module

    monkeypatch.setenv("HMS_QR_CORS_ORIGINS", "https://hms-qr.vercel.app")
    api = app_module.build_api(app_config=app_module.SERVER_APP_CONFIG, database_runtime=app_module.SERVER_DATABASE_RUNTIME)
    admin = app_module.build_admin_api(app_module.SERVER_APP_CONFIG, app_module.SERVER_DATABASE_RUNTIME)
    api.mount("/admin-api", admin)
    with TestClient(api) as test_client:
        response = test_client.post(
            "/admin-api/api/v1/auth/login",
            json={"username": "admin", "password": "definitely-not-the-password"},
            headers={"Origin": "https://hms-qr.vercel.app"},
        )
        assert response.status_code == 401
        assert response.headers["access-control-allow-origin"] == "https://hms-qr.vercel.app"


def test_vercel_deployment_assets_exist():
    """Vercel serves web/ at the root, so /static and /manifest must resolve there."""

    for relative in ("index.html", "manifest.json", "sw.js", "static/jsqr.min.js", "static/icon-192.png", "static/icon-512.png", "static/favicon.png"):
        assert (SOURCE_ROOT / "web" / relative).is_file(), f"missing web/{relative}"


def test_vercel_config_is_valid_and_caches_assets_immutably():
    config = json.loads((SOURCE_ROOT / "web" / "vercel.json").read_text(encoding="utf-8"))
    sources = {entry["source"] for entry in config["headers"]}
    assert "/static/(.*)" in sources
    assert "/sw.js" in sources
    static_rules = next(entry for entry in config["headers"] if entry["source"] == "/static/(.*)")
    assert static_rules["headers"][0]["value"] == "public, max-age=31536000, immutable"


def test_manifest_start_url_matches_the_served_route():
    """Vercel serves web/ at the root, so the page is at /, not /tracking/mobile.

    The LAN server keeps its own apps/static/manifest.json with
    start_url /tracking/mobile; this one is the Vercel copy.
    """

    manifest = json.loads((SOURCE_ROOT / "web" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    lan_manifest = json.loads((SOURCE_ROOT / "apps" / "static" / "manifest.json").read_text(encoding="utf-8"))
    assert lan_manifest["start_url"] == "/tracking/mobile"


def test_service_worker_precaches_paths_that_actually_exist_on_vercel():
    """cache.addAll aborts the whole install if any asset 404s.

    On Vercel the manifest is at /manifest.json, so precaching
    /static/manifest.json would silently kill offline support.
    """

    worker = (SOURCE_ROOT / "web" / "sw.js").read_text(encoding="utf-8")
    assert "'/manifest.json'" in worker
    assert "'/static/manifest.json'" not in worker
    assert "cache.add(asset).catch(" in worker
    assert "cache.addAll(" not in worker
