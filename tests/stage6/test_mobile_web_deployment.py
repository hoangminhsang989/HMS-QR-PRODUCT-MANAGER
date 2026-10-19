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
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SOURCE_ROOT = Path(__file__).resolve().parents[2]
MOBILE_PAGE = SOURCE_ROOT / "web" / "index.html"

# Which base each fetch variable resolves to. ``serverOrigin`` is the app root,
# so ``/api/v1/qr-catalog`` and ``/api/v1/scan-image`` live there, NOT under
# ``/tracking`` - getting that wrong returns 404 and silently kills the part
# picker and the camera scan.
FETCH_BASES = {
    "api": "/tracking",
    "filesApi": "/files",
    "serverOrigin": "",
}


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


def _page_fetch_paths() -> list[tuple[str, str]]:
    """Return ``(variable, literal_path)`` for every fetch the page issues."""

    page = MOBILE_PAGE.read_text(encoding="utf-8")
    found: list[tuple[str, str]] = []
    for variable in FETCH_BASES:
        pattern = rf"fetch\(\s*{variable}\s*\+\s*['\"]([^'\"]+)['\"]"
        found.extend((variable, path) for path in re.findall(pattern, page))
        template = rf"fetch\(\s*`\$\{{{variable}\}}([^`]*)`"
        found.extend((variable, path) for path in re.findall(template, page))
    return found


def _registered_paths(app, prefix: str = "") -> list[str]:
    """Every route path, including those inside mounted sub-applications.

    ``app.mount("/tracking", tracking_api)`` hides the tracking routes one level
    down, and their paths are relative to the mount, so a flat scan of
    ``app.routes`` only ever sees ``/tracking`` and the children as
    ``/api/v1/...``. Both halves are needed to resolve a full URL.
    """

    found: list[str] = []
    for route in getattr(app, "routes", []):
        path = getattr(route, "path", "")
        if path:
            found.append(prefix + path)
        children = getattr(route, "routes", None)
        if children:
            found.extend(_registered_paths(route, prefix + path))
    return found


def _matches(path: str, registered: list[str]) -> bool:
    """Does ``path`` match a registered route, with path params filled in?"""

    for route in registered:
        pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", route) + "$"
        if re.match(pattern, path):
            return True
    return False


def _resolves(variable: str, literal: str, registered: list[str]) -> bool:
    """Does this fetch reach a route the server actually registered?"""

    base = FETCH_BASES[variable]
    path = literal.split("?", 1)[0]
    full = base + path
    if path.endswith("/"):
        # The caller appends an identifier, and sometimes further segments
        # (``/api/v1/operators/' + userId + '/preference'``), so the literal is
        # a prefix rather than a whole path.
        return any(route.startswith(full) for route in registered)
    return _matches(full, registered)


def test_every_api_path_the_page_calls_is_a_real_route(client):
    """A mistyped base turns a working feature into a silent 404.

    ``/api/v1/qr-catalog`` and ``/api/v1/scan-image`` are mounted at the app
    root, so prefixing them with ``/tracking`` 404s. Nothing else in the suite
    notices: the page still loads, the fetch just never resolves.
    """

    registered = _registered_paths(client.app)
    assert registered, "no routes discovered"

    unresolved = [
        f"{variable} + '{literal}' -> {FETCH_BASES[variable] + literal.split('?', 1)[0]}"
        for variable, literal in _page_fetch_paths()
        if not _resolves(variable, literal, registered)
    ]
    assert not unresolved, "page calls paths that are not routes:\n  " + "\n  ".join(unresolved)


def test_page_does_not_fetch_an_absolute_api_path(client):
    """An absolute ``fetch('/api/...')`` would ignore the configured origin.

    That is what the page did before the origin became configurable, and it is
    what breaks the Vercel deployment: the browser would resolve it against the
    Vercel host, which has no such route.
    """

    page = MOBILE_PAGE.read_text(encoding="utf-8")
    absolute = re.findall(r"fetch\(\s*['\"](/api/[^'\"]*)['\"]", page)
    assert not absolute, f"absolute API fetches ignore the configured origin: {absolute}"


def test_lan_server_serves_the_page_byte_identically_to_vercel(client):
    """Vercel serves the raw file; the LAN server must not translate newlines.

    Reading the page through ``read_text`` applies universal-newline
    translation, so the phone would get LF while Vercel serves the CRLF file.
    Browsers do not care, but the two deployments then differ for no reason
    anyone can see, and the difference hides real drift.
    """

    response = client.get("/tracking/mobile")
    assert response.status_code == 200
    assert response.content == MOBILE_PAGE.read_bytes()


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
