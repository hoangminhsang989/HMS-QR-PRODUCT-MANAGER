"""Mobile web app: reachable page, runtime-configured origin, opt-in CORS.

The mobile page used to live inside ``apps/mobile/web.py`` as one Python string
with ``const api = '/tracking'`` baked in, which pinned it to same-origin. It now
lives in ``web/index.html`` and is served by both the LAN server and Vercel, so
these tests pin the two properties that make that split safe: the page loads
without a session (it carries the login form), and cross-origin access is off
unless an operator explicitly allows an origin.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import tempfile
from dataclasses import replace
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


def test_the_pages_inline_script_actually_parses():
    """A syntax error in the inline script kills every function on the page.

    Adding ``await`` to a function that was not ``async`` took the whole page
    down: the browser discards the entire ``<script>`` block, so ``submitLogin``,
    ``openPartPicker`` and ``selectPartFromList`` all became ``undefined`` while
    the HTML still rendered normally. Nothing in the suite noticed, because the
    guards below read the file as text and a broken script is still valid text.

    Checked by parsing the block with ``ast``-equivalent tooling for JavaScript:
    ``node --check``. Skipped when node is unavailable, so the suite still runs
    on a machine without it.
    """
    import re
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node is not installed")

    html = Path("web/index.html").read_text(encoding="utf-8")
    match = re.search(r"<script>(.*?)</script>", html, re.S)
    assert match, "the page has no inline script"
    script = match.group(1)

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    try:
        result = subprocess.run(["node", "--check", path],
                                capture_output=True, text=True)
    finally:
        Path(path).unlink(missing_ok=True)

    assert result.returncode == 0, (
        f"the page's inline script does not parse, so none of its functions "
        f"exist at runtime:\n{result.stderr[:600]}"
    )


def test_the_catalog_reports_qr_status_so_the_page_knows_when_to_issue():
    """The picker must not hand out a code that answers 404.

    ``scan_by_tracking_code`` refuses any row whose ``qr_status`` is not ACTIVE,
    while the catalog used to return a payload for every tracking item. An
    un-issued item therefore looked scannable in the picker and then failed with
    "QR not found or revoked" - a dead end for the operator, and the same class
    of defect as the catalog reading the wrong customer field.

    The catalog lists every item (the picker exists so an operator can work on a
    part that has no label yet), so the page needs ``qr_status`` to know whether
    to ask for a QR to be issued before the code will scan. Checked structurally
    with ``ast``: the field must be selected from the query and carried into the
    response, because a substring test would pass on a comment that merely
    mentions it.
    """
    import ast

    source = Path("apps/server/app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    selects = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "query"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and "order_tracking_items" in str(node.args[0].value)
    ]
    assert selects, "the catalog's tracking-item query was not found"
    sql = " ".join(str(selects[0].args[0].value).upper().split())
    assert "QR_STATUS" in sql, (
        "the catalog must select qr_status so the page can tell an un-issued "
        "QR from a live one"
    )

    # Scoped to qr_catalog: the module carries qr_status in other responses
    # (the tracking-item view), so a module-wide key check would pass even if
    # the catalog dropped it.
    catalog_fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "qr_catalog"
    )
    keys = {
        key.value
        for node in ast.walk(catalog_fn)
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert "qr_status" in keys, (
        "the catalog response must carry qr_status through to the page"
    )

    page = Path("web/index.html").read_text(encoding="utf-8")
    assert "qr_status" in page, (
        "the picker must consult qr_status before handing out a payload"
    )
    assert "/qr'" in page.replace('"', "'") or "/qr\"" in page, (
        "the picker must be able to ask the server to issue a QR"
    )


def test_cors_origins_split_on_newlines_as_well_as_commas(monkeypatch):
    """The launcher hands the allowlist over as one origin per line.

    ``CHAY_WEB.bat`` reads ``cors-origins.txt`` into a single environment
    variable, and one origin per line is how anyone would write that file.
    Splitting on commas alone would leave a two-line file as one entry
    containing an embedded newline - which matches no origin, so the first
    frontend is locked out with a CORS error that says nothing about why.
    """
    import apps.server.app as app_module

    monkeypatch.setenv("HMS_QR_CORS_ORIGINS",
                       "https://first.vercel.app\nhttps://second.vercel.app\n")
    origins = app_module.cors_origins_from_environment()
    assert origins == ("https://first.vercel.app", "https://second.vercel.app")

    monkeypatch.setenv("HMS_QR_CORS_ORIGINS", "https://a.vercel.app,https://b.vercel.app")
    assert app_module.cors_origins_from_environment() == (
        "https://a.vercel.app", "https://b.vercel.app",
    )

    monkeypatch.setenv("HMS_QR_CORS_ORIGINS", "")
    assert app_module.cors_origins_from_environment() == ()


def test_the_launcher_keeps_every_origin_line():
    """A bare ``set`` inside the loop leaves only the last line behind.

    That is what the launcher did, so adding a second frontend silently
    disabled the first. Verified by running the real loop shape rather than by
    looking for the assignment, for the same reason the catalog guard uses ast:
    a substring check is satisfied by code that no longer does the job.
    """
    launcher = Path("CHAY_WEB.bat").read_text(encoding="utf-8")
    block = launcher[launcher.index("cors-origins.txt"):]
    block = block[: block.index("\n)")]
    assert "EnableDelayedExpansion" in launcher, (
        "the launcher needs delayed expansion to accumulate across loop iterations"
    )
    assert "!HMS_QR_CORS_ORIGINS!" in block, (
        "the launcher overwrites the origin list on each line instead of appending"
    )


def _page_fetch_paths() -> list[tuple[str, str]]:
    """Return ``(variable, full_path)`` for every fetch the page issues.

    The path keeps the whole concatenation, with each interpolated identifier
    replaced by a placeholder, so ``fetch(api + '/api/v1/operators/' + userId +
    '/preference')`` yields ``/api/v1/operators/{}/preference`` rather than just
    the leading literal. Taking only the first literal would let a renamed
    trailing segment - ``/preference`` becoming ``/prefs`` - through unnoticed,
    which is the same silent-404 class as the base mistakes.

    A segment drawn from a lookup table (``routes[workflowType]``) expands to
    one path per value the table can hold, so a typo inside the table is caught
    too rather than hidden behind a wildcard.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")
    tables = _lookup_tables(page)
    found: list[tuple[str, str]] = []
    for expression in _fetch_first_arguments(page):
        for variable in FETCH_BASES:
            if expression.startswith(variable):
                for path in _concatenated_paths(expression[len(variable):], tables):
                    found.append((variable, path))
                break
    return found


def _lookup_tables(source: str) -> dict[str, list[str]]:
    """Every ``const name = { KEY: 'value', ... }`` table in the page."""
    tables: dict[str, list[str]] = {}
    for match in re.finditer(r"const\s+(\w+)\s*=\s*\{([^}]*)\}", source):
        values = re.findall(r"['\"]([^'\"]+)['\"]", match.group(2))
        if values:
            tables[match.group(1)] = values
    return tables


def _fetch_first_arguments(source: str) -> list[str]:
    """The first argument of every ``fetch(...)`` call, as source text.

    Scans for the call's opening parenthesis and walks to the first top-level
    comma or the matching close, tracking nesting and string state. A regex
    cannot do this: ``encodeURIComponent(q)`` contains parentheses, and the
    options object after the URL contains both commas and braces.
    """
    arguments: list[str] = []
    for match in re.finditer(r"fetch\(", source):
        index = match.end()
        start = index
        depth = 1
        quote = ""
        while index < len(source) and depth > 0:
            char = source[index]
            if quote:
                if char == "\\":
                    index += 2
                    continue
                if char == quote:
                    quote = ""
            elif char in "'\"`":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            elif char == "," and depth == 1:
                break
            index += 1
        arguments.append(source[start:index])
    return arguments


def _concatenated_paths(expression: str, tables: dict[str, list[str]]) -> list[str]:
    """Flatten a JS ``+`` concatenation into paths with placeholders."""
    results = [""]
    for part in expression.split("+"):
        part = part.strip()
        if not part:
            continue
        literal = re.match(r"^['\"]([^'\"]*)['\"]$", part)
        if literal:
            results = [prefix + literal.group(1) for prefix in results]
            continue
        member = re.match(r"^(\w+)\[", part)
        if member and member.group(1) in tables:
            # A lookup table: one path per value it can hold.
            results = [prefix + value for prefix in results for value in tables[member.group(1)]]
            continue
        # An identifier, a member access, or a call: a single path segment or a
        # query value. Either way it is not a literal to check.
        results = [prefix + "{}" for prefix in results]
    return results

def _fetch_first_arguments(source: str) -> list[str]:
    """The first argument of every ``fetch(...)`` call, as source text.

    Scans for the call's opening parenthesis and walks to the first top-level
    comma or the matching close, tracking nesting and string state. A regex
    cannot do this: ``encodeURIComponent(q)`` contains parentheses, and the
    options object after the URL contains both commas and braces.
    """
    arguments: list[str] = []
    for match in re.finditer(r"fetch\(", source):
        index = match.end()
        start = index
        depth = 1
        quote = ""
        while index < len(source) and depth > 0:
            char = source[index]
            if quote:
                if char == "\\":
                    index += 2
                    continue
                if char == quote:
                    quote = ""
            elif char in "'\"`":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            elif char == "," and depth == 1:
                break
            index += 1
        arguments.append(source[start:index])
    return arguments


def _concatenated_path(expression: str) -> str:
    """Flatten a JS ``+`` concatenation into one path with placeholders."""
    pieces: list[str] = []
    for part in expression.split("+"):
        part = part.strip()
        if not part:
            continue
        literal = re.match(r"^['\"]([^'\"]*)['\"]$", part)
        if literal:
            pieces.append(literal.group(1))
        else:
            # An identifier, a member access, or a call: a single path segment
            # or a query value. Either way it is not a literal to check.
            pieces.append("{}")
    return "".join(pieces)

def _concatenated_path(expression: str) -> str:
    """Flatten a JS ``+`` concatenation into one path with placeholders."""
    pieces: list[str] = []
    for part in expression.split("+"):
        part = part.strip()
        if not part:
            continue
        literal = re.match(r"^['\"]([^'\"]*)['\"]$", part)
        if literal:
            pieces.append(literal.group(1))
        else:
            # An identifier, a member access, or a call: a single path segment
            # or a query value. Either way it is not a literal to check.
            pieces.append("{}")
    return "".join(pieces)

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


def _resolves(variable: str, path: str, registered: list[str]) -> bool:
    """Does this fetch reach a route the server actually registered?"""
    full = FETCH_BASES[variable] + path.split("?", 1)[0]
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


def _isolated_app(tmp_path, monkeypatch):
    """A full app on its own engine database, so data cannot leak between tests."""
    import apps.server.app as app_module
    from config.environments import load_config
    from packages.application.server_auth import ServerAuthService
    from packages.persistence.database import create_database_runtime
    from packages.persistence.sqlalchemy_repository import Stage2Repository

    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", "bootstrap-password")
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "edge-case-signing-secret")

    config = load_config()
    config = replace(config, database_url=f"sqlite:///{(tmp_path / 'edge.sqlite').as_posix()}")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    ServerAuthService(runtime).bootstrap_admin()

    app = app_module.build_api(app_config=config, database_runtime=runtime)
    app.mount("/tracking", app_module.build_tracking_api(app_config=config, database_runtime=runtime))
    app.mount("/admin-api", app_module.build_admin_api(config, runtime))
    app.mount("/stage2", app_module.build_stage2_api(app_config=config, database_runtime=runtime))
    return app, runtime


def _login(client):
    response = client.post("/admin-api/api/v1/auth/login",
                           json={"username": "admin", "password": "bootstrap-password"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_a_partial_product_cannot_issue_a_qr_but_never_breaks_the_catalog(tmp_path, monkeypatch):
    """A product may legitimately have no part_name yet - an import that has not
    been completed. What must not happen is the two failure modes this guards:

    the QR issue endpoint returning a 500 instead of naming the problem, and the
    catalog taking the whole picker down because of that one row.
    """
    app, runtime = _isolated_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            headers = _login(client)

            customer = client.post("/stage2/api/v1/customers", headers=headers, json={
                "customer_code": "C-EDGE", "name": "Công ty Biên",
            }).json()
            po = client.post("/stage2/api/v1/purchase-orders", headers=headers, json={
                "po_number": "PO-EDGE", "customer_id": customer["internal_id"],
                "po_date": "2026-10-19", "status": "CONFIRMED",
            }).json()

            # Blank part_name is accepted on purpose: test_api.py and
            # test_domain.py both assert it, because a product can arrive from an
            # import before its name is known.
            product = client.post("/api/v1/products", headers={**headers, "X-Actor": "test"}, json={
                "part_name": "", "quantity": "10", "unit": "cái",
            })
            assert product.status_code == 201, product.text
            assert product.json()["part_name"] == ""
            assert product.json()["product_code"], "a null product_code is auto-generated"

            line = client.post(f"/stage2/api/v1/purchase-orders/{po['internal_id']}/lines",
                               headers=headers, json={
                                   "product_id": product.json()["internal_id"], "line_number": 1,
                                   "ordered_quantity": "10", "unit": "cái",
                               }).json()
            item = client.post("/tracking/api/v1/tracking-items", headers=headers, json={
                "purchase_order_id": po["internal_id"],
                "purchase_order_line_id": line["internal_id"],
                "product_id": product.json()["internal_id"],
                "customer_id": customer["internal_id"],
                "quantity": "10", "unit": "cái", "delivery_date": "2026-11-30",
            }).json()
            item_id = item["internal_id"]

            # The QR contract needs a non-empty product name, so this is a
            # validation failure the operator can act on - not a server fault.
            # (The catalog's side of this is covered by the guards above and by
            # the live-server check; the route is registered on the module-level
            # app rather than inside build_api, so it cannot be reached from an
            # isolated one.)
            issue = client.post(f"/tracking/api/v1/tracking-items/{item_id}/qr", headers=headers)
            assert issue.status_code == 422, issue.text
            assert issue.json()["error"]["code"] == "TRACKING_VALIDATION_ERROR"

            # Completing the product is the recovery path, and it must work.
            patched = client.patch(f"/api/v1/products/{product.json()['internal_id']}",
                                   headers={**headers, "X-Actor": "test"},
                                   json={"part_name": "Trục S45C", "expected_updated_at": product.json()["updated_at"]})
            assert patched.status_code == 200, patched.text

            after = client.post(f"/tracking/api/v1/tracking-items/{item_id}/qr", headers=headers)
            assert after.status_code == 200, after.text
            payload = json.loads(after.json()["payload"])
            assert payload["product_name"] == "Trục S45C"
            assert payload["customer_name"] == "Công ty Biên"
    finally:
        runtime.dispose()


def test_a_machining_report_names_its_own_failure():
    """submitReport is the second write that pre-fills its quantity from the
    item and sends the input's .value as a string. An emptied field therefore
    reaches the server as "" and is rejected as a 422 - and the page's message
    was fixed, so the operator was told the report failed without being told
    why. This is the same defect bd0da42 fixed in sendWorkflow.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")
    report = page[page.index("async function submitReport"):]
    report = report[:report.index("\n    async function ", 10)]

    assert "isNaN(Number(qty))" in report, (
        "the quantity is sent without being checked, so clearing the field "
        "reaches the server as an empty string and comes back as a 422 that "
        "names no field"
    )
    assert "const message = e.error?.message" in report, (
        "the report failure still discards the server's own diagnosis, so a "
        "rejected field is reported as a generic failure"
    )
    assert "Array.isArray(e.detail)" in report, (
        "a 422 from request validation answers as {detail:[...]}, which the "
        "page cannot read, so the field error is lost"
    )


def test_a_malformed_qr_is_not_reported_as_a_missing_one():
    """The scan input invites a code to be typed by hand, so a malformed
    payload is the likeliest failure - and it is not the same problem as a code
    that resolves to nothing. The server answers "invalid QR payload" and
    "QR payload must contain exactly the canonical four fields" as 422s, and
    "QR not found or revoked" as a 404. All three were reported as "Khong tim
    thay du lieu cho ma QR nay", which sends the operator to check the label
    when what is wrong is what they typed.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")
    scan = page[page.index("async function resolveScan"):]
    scan = scan[:scan.index("\n    async function ", 10)]

    assert "const message = e.error?.message" in scan, (
        "the scan still discards the server's own diagnosis, so a malformed "
        "payload is reported as a missing one"
    )
    assert "Array.isArray(e.detail)" in scan, (
        "a 422 from request validation answers as {detail:[...]}, which the "
        "page cannot read, so the field error is lost"
    )
    assert "Kh\u00f4ng t\u00ecm th\u1ea5y d\u1eef li\u1ec7u cho m\u00e3 QR n\u00e0y.'" in scan, (
        "the fallback for a response with no readable message is gone"
    )


def test_the_operator_and_process_pickers_do_not_fail_silently():
    """The NGUOI DUNG and CONG DOAN pills each open a picker. Both fetched their
    list and returned on any non-ok response without a word, so a tap that could
    not load its list did nothing at all - no picker, no message. The picker in
    the part list already had this fixed; these two were the same defect left
    behind, and neither had a try/catch, so a dead network rejected a promise
    nobody was listening to.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")

    for name, label in (("changeUser", "nhan su"), ("changeProcess", "cong doan")):
        start = page.index(f"async function {name}(")
        end = page.index("\n    async function ", start + 10)
        body = page[start:end]

        assert "if (!r.ok) return;" not in body, (
            f"{name} still returns silently on a failed load, so tapping the "
            "pill does nothing and says nothing"
        )
        assert "notify(" in body, (
            f"the {label} list failure is not surfaced, so the operator "
            "cannot tell a dead server from an empty list"
        )
        assert "} catch(e) {" in body, (
            f"{name} has no catch, so a dead network rejects a promise "
            "nobody is listening to"
        )


def test_an_empty_quantity_is_caught_before_the_round_trip():
    """The quantity field is pre-filled from the item, but it is a plain number
    input behind an onclick, so nothing stops the operator clearing it. An empty
    value reaches the server as "" and is rejected as a 422 that names no field,
    so the operator is told the event failed without being told what to fix.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")
    send = page[page.index("async function sendWorkflow"):]
    send = send[:send.index("\n    async function ", 10)]

    assert "isNaN(Number(qty))" in send, (
        "the quantity is sent without being checked, so clearing the field "
        "reaches the server as an empty string and comes back as a 422 that "
        "names no field"
    )
    assert "Vui l\u00f2ng nh\u1eadp s\u1ed1 l\u01b0\u1ee3ng l\u1edbn h\u01a1n 0." in send, (
        "the empty quantity is not named to the operator, so the only message "
        "they see is that the event failed"
    )


def test_the_page_reads_the_servers_second_error_envelope():
    """The server answers failures in two shapes. _error() wraps as
    {error:{message}}, while HTTPException and FastAPI's own request validation
    answer as {detail:...} - a dict for HTTPException, a list of field errors for
    a rejected body. The page read only the first shape, so every rejected field
    fell through to a message that names nothing the operator can fix.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")
    send = page[page.index("async function sendWorkflow"):]
    send = send[:send.index("\n    async function ", 10)]

    assert "Array.isArray(e.detail)" in send, (
        "a 422 from request validation answers as {detail:[...]}, which the "
        "page cannot read, so a rejected field is reported as a generic failure"
    )
    assert "e.detail?.message" in send, (
        "an HTTPException answers as {detail:{message}}, which the page cannot "
        "read, so the server's own diagnosis is discarded"
    )


def test_the_page_sends_the_operator_name_so_an_issued_qr_can_be_traced():
    """The picker issues a QR on the operator's behalf, so the audit row has to
    name that operator.

    The server already reads an ``X-Actor`` header and already stores it in
    ``tracking_audit_events.actor``; without this header it falls back to the
    literal string ``"development-user"``. A code issued from the picker would
    then carry no name, and the audit trail could not answer who issued it -
    which is exactly the traceability the factory asked for.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")

    wrapper = page.index("window.fetch = function (input, init)")
    body = page[wrapper:page.index("return nativeFetch(", wrapper)]

    assert "headers.set('X-Actor'" in body, (
        "the fetch wrapper never names the operator, so every issued QR is "
        "recorded as development-user"
    )
    assert "readAccount()" in body, (
        "the operator name must come from the signed-in account, not a constant"
    )
    assert "account && account.username" in body, (
        "an unauthenticated call must not invent an operator name"
    )
    assert "!headers.has('X-Actor')" in body, (
        "an explicit X-Actor from a call site must not be overwritten"
    )


def test_the_history_shows_who_issued_the_qr(tmp_path, monkeypatch):
    """``tracking_audit_events`` was written on every QR issue but never read
    back, so the history endpoint reported an item going straight to QC with no
    record of who issued its code. The audit rows now belong in the history.
    """
    app, runtime = _isolated_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            headers = _login(client)
            customer = client.post("/stage2/api/v1/customers", headers=headers, json={
                "customer_code": "C-AUDIT", "name": "Công ty Biên",
            }).json()
            product = client.post("/api/v1/products", headers=headers, json={
                "part_name": "Trục S45C", "quantity": "10", "unit": "cái",
            }).json()
            po = client.post("/stage2/api/v1/purchase-orders", headers=headers, json={
                "po_number": "PO-AUDIT", "customer_id": customer["internal_id"],
                "po_date": "2026-10-20", "status": "CONFIRMED",
            }).json()
            line = client.post(f"/stage2/api/v1/purchase-orders/{po['internal_id']}/lines",
                               headers=headers, json={
                                   "product_id": product["internal_id"], "line_number": 1,
                                   "ordered_quantity": "10", "unit": "cái",
                               }).json()
            item = client.post("/tracking/api/v1/tracking-items", headers=headers, json={
                "purchase_order_id": po["internal_id"],
                "purchase_order_line_id": line["internal_id"],
                "product_id": product["internal_id"],
                "customer_id": customer["internal_id"],
                "quantity": "10", "unit": "cái", "delivery_date": "2026-11-30",
            }).json()
            item_id = item["internal_id"]

            # Without the header the server keeps its documented fallback.
            blind = client.post(f"/tracking/api/v1/tracking-items/{item_id}/qr", headers=headers)
            assert blind.status_code == 200, blind.text
            history = client.get(f"/tracking/api/v1/tracking-items/{item_id}/history",
                                 headers=headers).json()["items"]
            issued = [row for row in history if row.get("source") == "AUDIT"]
            assert len(issued) == 1, f"the audit row is missing from the history: {history}"
            assert issued[0]["event_type"] == "QR_ISSUED"
            assert issued[0]["actor_display_name_snapshot"] == "development-user"
            assert issued[0]["actor_user_id"] == "development-user"

            # With it, the row names the operator who actually did it.
            reissue = client.post(
                f"/tracking/api/v1/tracking-items/{item_id}/qr/reissue",
                headers={**headers, "X-Actor": "nguyen.van.a"},
            )
            assert reissue.status_code == 200, reissue.text
            history = client.get(f"/tracking/api/v1/tracking-items/{item_id}/history",
                                 headers=headers).json()["items"]
            reissued = [row for row in history
                        if row.get("source") == "AUDIT" and row["event_type"] == "QR_REISSUED"]
            assert len(reissued) == 1, f"the reissue audit row is missing: {history}"
            assert reissued[0]["actor_display_name_snapshot"] == "nguyen.van.a"
            assert reissued[0]["actor_user_id"] == "nguyen.van.a"

            # The audit rows must not displace the workflow and machining rows
            # that were already there, and the merged list stays time-ordered.
            stamps = [row["server_timestamp"] for row in history]
            assert stamps == sorted(stamps), "history lost its time ordering"
            assert all(isinstance(stamp, str) and "T" in stamp for stamp in stamps), (
                "audit timestamps must be ISO strings like every other row"
            )
    finally:
        runtime.dispose()


def test_cors_allows_the_actor_header_the_page_now_sends(monkeypatch):
    """``X-Actor`` is not a CORS-safelisted header, so a browser preflights it.

    If it is not allowed, every mutating call from the production page fails
    before it reaches the server - which would take the picker's QR issue with
    it.
    """
    import apps.server.app as app_module

    monkeypatch.setenv("HMS_QR_CORS_ORIGINS", "https://hms-qr.vercel.app")
    api = app_module.build_api(app_config=app_module.SERVER_APP_CONFIG,
                               database_runtime=app_module.SERVER_DATABASE_RUNTIME)
    with TestClient(api) as test_client:
        allowed = test_client.options(
            "/tracking/api/v1/operators",
            headers={
                "Origin": "https://hms-qr.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization, x-actor",
            },
        )
        assert allowed.status_code == 200
        granted = allowed.headers["access-control-allow-headers"]
        assert "X-Actor" in granted, f"the actor header is not granted: {granted}"


def test_the_history_labels_the_audit_events_in_vietnamese():
    """The audit rows only became visible in the history recently, and an
    unlabelled one renders its raw English event_type to the operator.

    The three types are the only ones ``save_item`` ever writes to
    ``tracking_audit_events`` - QR_ISSUED and QR_REISSUED from the QR endpoints,
    DELIVERY_DATE_CHANGED from the delivery-date endpoint - so this list is the
    complete set, not a sample.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")

    # The loadHistory map is the one that starts with ATTEMPT; the workflow map
    # starts with QC_CHECKED and must not be edited by mistake.
    start = page.index("ATTEMPT: '")
    block = page[start:page.index("};", start)]

    for event_type in ("QR_ISSUED", "QR_REISSUED", "DELIVERY_DATE_CHANGED"):
        assert f"{event_type}: '" in block, (
            f"{event_type} has no Vietnamese label, so the history shows the raw "
            f"English event_type to the operator"
        )

    # A label must not be left as the event_type itself, which would look
    # translated while saying nothing.
    for line in block.splitlines():
        stripped = line.strip()
        for event_type in ("QR_ISSUED", "QR_REISSUED", "DELIVERY_DATE_CHANGED"):
            if stripped.startswith(f"{event_type}:"):
                label = stripped.split("'")[1]
                assert label != event_type, f"{event_type} is labelled with itself"
                assert label.strip(), f"{event_type} has an empty label"


def test_the_audit_row_keeps_the_old_and_new_value():
    """A DELIVERY_DATE_CHANGED audit row carries the old and the new date, and
    they are the only record of what the date used to be. Reading the row back
    without them would silently erase that.
    """
    source = (SOURCE_ROOT / "packages/persistence/tracking_repository.py").read_text(
        encoding="utf-8"
    )
    block = source[source.index("def _audit_event"):]
    block = block[:block.index("def _report")]

    assert '"old_value": row["old_value"]' in block, (
        "the audit row drops old_value, erasing what a date change replaced"
    )
    assert '"new_value": row["new_value"]' in block, (
        "the audit row drops new_value, erasing what a date change became"
    )


def test_the_scan_warns_when_the_label_no_longer_matches():
    """A label printed before a part's details were edited still resolves, because
    the scan looks the item up by tracking_code. The server notices the printed
    name, customer or product code no longer match and reports that as
    ``qr_identity_consistent`` - and until now nothing read the flag, so the
    operator was shown a part with no sign its label was stale.

    Working from a stale label is a correctness risk, not a cosmetic one, so the
    page has to say so.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")

    assert "id='qr-mismatch'" in page, (
        "there is no element to carry the warning"
    )

    # The flag is only present on a scan response, so the read must live in
    # resolveScan and must treat a missing flag as consistent rather than
    # warning on every unrelated render.
    resolve = page[page.index("async function resolveScan"):]
    resolve = resolve[:resolve.index("async function ", resolve.index("async function ") + 1)]
    assert "qr_identity_consistent" in resolve, (
        "resolveScan ignores qr_identity_consistent, so a stale label looks fine"
    )
    assert "!== false" in resolve, (
        "the comparison must be against false, so a response without the flag "
        "does not raise a warning"
    )

    # A pick builds its payload from the server, so it is consistent by
    # construction; without clearing it, a warning raised by an earlier scan
    # would sit on screen through the next part.
    pick = page[page.index("async function selectPartFromList"):]
    pick = pick[:pick.index("function ", pick.index("function ") + 1)]
    assert "qr-mismatch" in pick, (
        "selectPartFromList does not clear the warning, so a stale warning "
        "survives into the next part"
    )


def test_the_qr_issue_names_the_operator_not_the_login():
    """Issuing a QR recorded the signed-in account, while every workflow event
    records the operator picked from the list. On a shared device that is two
    different names for one person inside a single history, and with nobody
    picked yet the issue was filed under the login without a word.

    The picker is the only write in the tracking flow that never asked who was
    working, so it is the one that has to follow the convention the rest of the
    page already follows.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")

    wrapper = page[page.index("window.fetch = function"):]
    wrapper = wrapper[:wrapper.index("function renderConnection")]

    assert "localStorage.getItem('hms-user')" in wrapper, (
        "the wrapper never looks at the picked operator, so the QR issue "
        "still records the login"
    )
    assert "operator ||" in wrapper, (
        "the operator is not preferred over the login, so a picked operator "
        "is still ignored"
    )
    # The fallback has to survive a device where nobody has been picked yet,
    # otherwise the header disappears and the server reverts to
    # "development-user" - the defect this whole chain was built to remove.
    assert "account && account.username" in wrapper, (
        "dropping the login fallback would leave the header unset when no "
        "operator is picked"
    )


def test_a_failed_qr_issue_is_not_reported_as_a_failed_scan():
    """Issuing a QR swallowed its own failure. The catalog's payload only scans
    once the item's QR is ACTIVE, so after a failed issue the page kept that
    preview and the next scan answered "QR not found" - blaming the code for a
    failed write, and sending the operator looking for a problem in the wrong
    place.

    The picker had the same shape: a catalog that could not be loaded left an
    empty list with no explanation, which reads as "nothing to pick" rather
    than "the server could not be reached".
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")

    pick = page[page.index("async function selectPartFromList"):]
    pick = pick[:pick.index("function ", pick.index("function ") + 1)]

    assert "} catch (e) {}" not in pick, (
        "the QR issue still swallows its failure, so a failed write is "
        "reported as a failed scan"
    )
    assert "return notify(" in pick, (
        "the issue failure is not surfaced, so the operator is told the QR "
        "is missing rather than that it could not be issued"
    )

    opener = page[page.index("async function openPartPicker"):]
    opener = opener[:opener.index("function ", opener.index("function ") + 1)]

    assert "} catch(e) {}" not in opener, (
        "a catalog that fails to load leaves the picker empty and silent, "
        "which reads as 'nothing to pick'"
    )
    assert "notify(" in opener, (
        "the catalog failure is not surfaced, so the operator cannot tell a "
        "dead server from an empty list"
    )


def test_the_catalog_reads_the_customer_name_from_the_customer_record():
    """The catalog and the issued QR must agree on what a payload says.

    ``/api/v1/qr-catalog`` built its payload from ``products.company`` while
    ``TrackingService.qr_payload`` - the endpoint that actually issues and
    validates QR codes - reads ``customers.name``. Two different values for the
    same field means a payload rendered in the picker decodes to something
    ``scan()`` then reports as inconsistent.
    """
    source = (SOURCE_ROOT / "apps" / "server" / "app.py").read_text(encoding="utf-8")
    catalog = source[source.index("def qr_catalog"):]
    catalog = catalog[: catalog.index("\n@")] if "\n@" in catalog else catalog
    assert 'customer["name"]' in catalog, (
        "the catalog no longer reads the customer record's name"
    )
    assert 'QrPayload(product["part_name"], product["company"]' not in catalog, (
        "the catalog still builds its payload from products.company, which "
        "disagrees with the QR the tracking service issues"
    )
    assert "SELECT internal_id, name FROM customers" in catalog


def _qr_catalog_function() -> ast.FunctionDef:
    source = (SOURCE_ROOT / "apps" / "server" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "qr_catalog":
            return node
    raise AssertionError("qr_catalog not found in apps/server/app.py")


def test_a_product_without_a_company_cannot_take_the_catalog_down():
    """``company`` is optional on a product, and an empty one used to 500 the route.

    ``QrPayloadService.encode`` rejects an empty field, and the catalog called it
    unguarded inside its loop, so one product with no company made the whole
    endpoint return 500 - the part picker dies entirely, not just for that row.

    This is checked structurally rather than by substring: a guard that only looks
    for the text "except TrackingError" is satisfied by an orphaned except clause
    that no longer guards anything, which is exactly what a careless edit leaves
    behind.
    """
    function = _qr_catalog_function()

    guarded = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name not in ("QrPayload", "data_uri"):
            continue
        # Walk up through the AST parents to see whether a try statement covers it.
        for parent in ast.walk(function):
            if not isinstance(parent, ast.Try):
                continue
            covers = any(
                child is node or node in ast.walk(child)
                for child in parent.body
            )
            if not covers:
                continue
            catches = [
                handler for handler in parent.handlers
                if any(
                    isinstance(item, ast.Name) and item.id == "TrackingError"
                    for handler_name in ([handler.type] if handler.type else [])
                    for item in ast.walk(handler_name)
                )
            ]
            guarded.append((name, bool(catches)))

    assert guarded, "no QrPayload or data_uri call found inside qr_catalog"
    for name, catches in guarded:
        assert catches, (
            f"the {name} call in qr_catalog is not wrapped in a try that catches "
            "TrackingError, so one unencodable row fails the whole request"
        )


def test_the_catalog_button_does_not_advertise_a_made_up_count():
    """The picker button used to carry a hardcoded "76".

    The number had nothing to do with the catalog, so the operator was told there
    were 76 details whether the database held none or three hundred. The label is
    now written from the total the server reports.
    """
    page = MOBILE_PAGE.read_text(encoding="utf-8")
    assert "Danh Sách 76" not in page, "the picker button still hardcodes a count"
    assert "id='part-picker-btn'" in page, "the picker button has no id to update"
    assert "Danh Sách ' + total + ' Chi Tiết" in page, (
        "the picker button label is not written from the server's total"
    )


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


LAUNCHER = SOURCE_ROOT / "CHAY_WEB.bat"


def _launcher() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_launcher_supplies_the_token_signing_secret():
    """The page signs in, and login() refuses to issue a token without a secret.

    ``ServerAuthService.login`` raises "Server authentication is not configured"
    when ``HMS_QR_AUTH_SECRET`` is empty, in every environment - the production
    guard only adds a length check. A launcher that omits it therefore ships an
    app whose login can never succeed, which is exactly what CHAY_WEB.bat did.
    """
    launcher = _launcher()
    assert "HMS_QR_AUTH_SECRET" in launcher
    assert "auth-secret.txt" in launcher


def test_launcher_secret_is_persisted_not_regenerated():
    """A secret regenerated on each start invalidates every issued token.

    The launcher writes the secret to disk once and reuses it, so a restart
    does not sign operators out mid-shift.
    """
    launcher = _launcher()
    assert r'if not exist "%DATA_ROOT%\auth-secret.txt"' in launcher
    assert r'set /p HMS_QR_AUTH_SECRET=<"%DATA_ROOT%\auth-secret.txt"' in launcher


def test_launcher_supplies_bootstrap_admin_credentials():
    """bootstrap_admin() reads the username and password from the environment.

    With neither set it raises "Server has no administrator account", and the
    mobile page has no other way to create the first account - the admin API
    that creates accounts is itself behind that login.
    """
    launcher = _launcher()
    assert "HMS_QR_BOOTSTRAP_ADMIN_USERNAME" in launcher
    assert "HMS_QR_BOOTSTRAP_ADMIN_PASSWORD" in launcher
    assert "admin-password.txt" in launcher


def _squash(text: str) -> str:
    """Drop whitespace and quotes so every quoting style collapses to one form.

    Alembic was invoked three different ways across the repo - a shell string in
    the batch launcher, a YAML startCommand, and a subprocess argument list in
    tool.py. Matching the literal "alembic upgrade head" catches only the first
    two, which is how a re-introduced list-form call slipped past this guard.
    """
    return re.sub(r"[\s\"']+", "", text)


def test_no_runtime_path_invokes_alembic():
    """Alembic is gone from the runtime, so any caller of it now fails outright.

    The engine cutover deleted alembic.ini and emptied migrations/versions, but
    four callers were left invoking it: the test launcher, the tool's Start
    Server button, the Dockerfile CMD and the render.yaml startCommand. Each of
    them fails with "No 'script_location' key found in configuration", which for
    the tool means the operator can never start the production server from the
    GUI at all.
    """
    repo_root = Path(__file__).resolve().parents[2]
    callers = [
        repo_root / "TEST_HMS_QR_SERVER.bat",
        repo_root / "CHAY_WEB.bat",
        repo_root / "apps" / "server" / "tool.py",
        repo_root / "Dockerfile",
        repo_root / "render.yaml",
    ]
    for caller in callers:
        squashed = _squash(caller.read_text(encoding="utf-8"))
        for pattern in ("alembicupgradehead", "-malembic", "-m,alembic"):
            assert pattern not in squashed, (
                f"{caller.name} still invokes alembic, which fails without alembic.ini"
            )


def test_every_migration_caller_applies_the_engine_migrations():
    """Removing Alembic is only half the job - the schema still has to be built.

    A caller that simply drops its migration step leaves a fresh database empty
    and production refuses to start on it, so each of these must apply the engine
    migrations instead. For tool.py the check is that the start path actually
    calls the helper, not merely that the helper exists somewhere in the file -
    a dead helper next to a replaced call site passes a plain substring check.
    """
    repo_root = Path(__file__).resolve().parents[2]
    for caller in (
        repo_root / "TEST_HMS_QR_SERVER.bat",
        repo_root / "Dockerfile",
        repo_root / "render.yaml",
    ):
        assert "create_schema()" in caller.read_text(encoding="utf-8"), (
            f"{caller.name} no longer applies the engine migrations"
        )
    tool = (repo_root / "apps" / "server" / "tool.py").read_text(encoding="utf-8")
    assert "def _apply_engine_migrations" in tool
    assert "self._apply_engine_migrations()" in tool


def test_the_engine_migration_script_satisfies_the_production_schema_check(tmp_path):
    """The script the callers run must leave a database production will accept.

    require_database_schema_current rejects a production runtime whose applied
    versions fall short of the shipped head, so running the script has to move a
    fresh database past that check rather than merely creating tables.
    """
    script = (
        "from config.environments import load_config;"
        "from packages.persistence.database import create_database_runtime, require_database_schema_current;"
        "from packages.persistence.sqlalchemy_repository import Stage2Repository;"
        "runtime=create_database_runtime(load_config());"
        "Stage2Repository(runtime).create_schema();"
        "require_database_schema_current(runtime);"
        "print('SCHEMA_CURRENT');"
        "runtime.dispose()"
    )
    repo_root = Path(__file__).resolve().parents[2]
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repo_root)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["HMS_QR_ENV"] = "staging"
    environment["HMS_QR_DATABASE_URL"] = f"sqlite:///{(tmp_path / 'schema-check.sqlite').as_posix()}"
    environment["HMS_QR_STORAGE_ROOT"] = str(storage_root)
    environment["HMS_QR_AUTH_SECRET"] = "engine-migration-verification-secret-2026"
    environment["HMS_QR_BOOTSTRAP_ADMIN_USERNAME"] = "schema-check-admin"
    environment["HMS_QR_BOOTSTRAP_ADMIN_PASSWORD"] = "schema-check-password-123"
    result = subprocess.run(
        ["py", "-3.14", "-c", script],
        cwd=str(repo_root), env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-600:]
    assert "SCHEMA_CURRENT" in result.stdout


def test_launcher_password_is_persisted_and_operator_changeable():
    """The password is generated once, shown once, and kept where it can be replaced.

    Regenerating it silently on every start would lock the operator out; the
    launcher therefore writes it to a file the operator can delete to choose a
    new one.
    """
    launcher = _launcher()
    assert r'if not exist "%DATA_ROOT%\admin-password.txt"' in launcher
    assert r'set /p ADMIN_PASSWORD=<"%DATA_ROOT%\admin-password.txt"' in launcher
    assert "FIRST_RUN" in launcher


def test_lan_server_serves_every_asset_the_page_references(client):
    """The page is served at /tracking/mobile but registers /sw.js and links
    /manifest.json at the root.

    On the LAN those absolute paths only resolve if the server mounts them
    there. A missing one fails silently - the QR scanner never loads, or offline
    support quietly never installs - with nothing in the page itself looking
    wrong. This is the same class of miss as the Vercel start_url and the
    precache path, both of which shipped broken.
    """
    page = client.get("/tracking/mobile").text
    referenced = set(re.findall(r"""['"](/[^'"]+\.(?:js|json|png|svg|ico))['"]""", page))
    assert referenced, "the page references no absolute assets at all"
    for path in sorted(referenced):
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_lan_service_worker_precaches_only_paths_that_resolve(client):
    """cache.addAll aborts the whole install if any asset 404s.

    One dead path in the precache list silently removes offline support for the
    entire app, which is exactly what /static/manifest.json did on Vercel.
    """
    worker = client.get("/sw.js").text
    precached = [
        line.strip().strip("',\"")
        for line in worker.split("\n")
        if line.strip().startswith("'/")
    ]
    assert precached, "the service worker precaches nothing"
    for path in precached:
        if not path.startswith("/") or path == "/static/":
            continue
        response = client.get(path)
        assert response.status_code == 200, f"precaching {path} would 404"


def test_lan_manifest_points_at_the_lan_route_and_its_icons_resolve(client):
    """The LAN copy of the manifest must send the phone back to /tracking/mobile.

    Vercel serves the page at the root, so its copy uses start_url "/". The LAN
    copy is a different file with a different job, and the two must not drift.
    """
    manifest = client.get("/manifest.json").json()
    assert manifest["start_url"] == "/tracking/mobile"
    assert manifest["scope"] == "/"
    for icon in manifest["icons"]:
        response = client.get(icon["src"])
        assert response.status_code == 200, f"icon {icon['src']} returned {response.status_code}"


def test_an_expired_token_is_refused_with_the_message_the_page_shows(tmp_path, monkeypatch):
    """A session that expires mid-shift must come back as a refusal the page acts on.

    The page's fetch wrapper clears the token and reopens the login form on any
    401, so this is the mid-shift re-login path. If the server answered anything
    else - a 500, or a success with an empty body - the operator would be left
    holding a dead session with no prompt to renew it.
    """
    from datetime import timedelta

    from packages.application import server_auth
    from packages.application.server_auth import AuthenticationError, ServerAuthService, UserRole
    from packages.persistence.database import DatabaseRuntime
    from packages.sqlengine import Database
    from packages.sqlengine.migrations import load_migration_modules, run_migrations
    from config.environments import AppConfig, Environment

    database = Database(tmp_path / "expiry-engine")
    try:
        run_migrations(
            database,
            load_migration_modules(SOURCE_ROOT / "migrations" / "engine"),
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        runtime = DatabaseRuntime(
            AppConfig(Environment.PROD, "sqlite:///expiry.sqlite", "nas"),
            database,
            tmp_path / "expiry-engine",
        )
        secret = "expiry-acceptance-token-secret-value"
        monkeypatch.setenv("HMS_QR_AUTH_SECRET", secret)
        auth = ServerAuthService(runtime, token_secret=secret)
        auth.create_account("expiry-editor", "expiry-password", UserRole.EDITOR.value)
        token = auth.login("expiry-editor", "expiry-password")["access_token"]

        assert auth.authenticate(token)["username"] == "expiry-editor"

        # Move the clock past the eight-hour lifetime; the same token must now
        # be refused with the message the page surfaces to the operator.
        real_now = server_auth._now
        monkeypatch.setattr(server_auth, "_now", lambda: real_now() + timedelta(hours=9))
        with pytest.raises(AuthenticationError) as excinfo:
            auth.authenticate(token)
        assert "hết hạn" in str(excinfo.value)
    finally:
        database.close()


def _statuses_the_server_can_write() -> set[str]:
    """Every value that can land in ``order_tracking_items.status``.

    Two kinds of writer exist. Python assigns a ``TrackingStatus`` member
    (``OrderTrackingItem.create``, ``submit_report``, ``_project_status``), and
    the Excel adapters hardcode a literal inside a raw INSERT. Both are read
    here, and the literals are kept only when they name a real ``TrackingStatus``
    member, so a neighbouring ``'ACTIVE'`` or ``'QR_ISSUED'`` cannot sneak in.
    """
    from packages.domain.tracking import TrackingStatus

    members = {member.name for member in TrackingStatus}
    written: set[str] = set()
    for path in (SOURCE_ROOT / "packages").rglob("*.py"):
        written.update(
            name for name in re.findall(r"TrackingStatus\.(\w+)", path.read_text(encoding="utf-8"))
            if name in members
        )
    for path in (SOURCE_ROOT / "packages" / "excel").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "INSERT INTO order_tracking_items" not in text:
            continue
        for match in re.finditer(r"INSERT INTO order_tracking_items", text):
            window = text[match.start():match.start() + 900]
            written.update(
                name for name in re.findall(r"'(\w+)'", window) if name in members
            )
    return written


def test_the_stepper_covers_every_status_the_server_can_write():
    """The stepper branched on a vocabulary the server never writes.

    ``updateStepper`` tested for ``APPROVED``, ``IN_PROGRESS``,
    ``SHORTAGE_REPORTED`` and ``QC_NG_RETURNED_TO_MACHINING``. None of those is
    ever written to ``order_tracking_items.status`` - the first two are not
    statuses at all, and the last two are ``WorkflowEventType`` values the page
    sends to the server, not statuses it reads back.

    The statuses the server really writes - ``WAITING_QC``, ``REWORK``,
    ``SHORTAGE``, ``QC_NG``, ``PACKING``, ``PARTIALLY_DELIVERED`` - matched no
    branch and fell through to the default of step 2. An item waiting for QC,
    failed at QC, being packed, or partly delivered all displayed "Gia cong",
    and the alert styling never appeared for the two statuses that mean the
    item went wrong.
    """
    written = _statuses_the_server_can_write()
    assert written, "parsing found no writers - the guard itself is broken"

    page = MOBILE_PAGE.read_text(encoding="utf-8")
    start = page.index("function updateStepper")
    stepper = page[start:page.index("\n    function ", start)]

    missing = sorted(name for name in written if f"status === '{name}'" not in stepper)
    assert not missing, f"stepper khong map status that su: {missing}"

    # event types are not statuses and must not drive the stepper
    for event_type in ("SHORTAGE_REPORTED", "QC_NG_RETURNED_TO_MACHINING"):
        assert f"status === '{event_type}'" not in stepper, (
            f"{event_type} la WorkflowEventType, khong phai TrackingStatus"
        )


def test_an_item_imported_from_the_factory_sheet_can_be_read_back(tmp_path):
    """The factory Excel import wrote a status the domain did not name.

    ``import_factory_items_to_db`` writes ``'IN_PRODUCTION'`` into
    ``order_tracking_items.status``, and both the portal and the export report
    count that value - but ``TrackingStatus`` never named it, calling the same
    state ``IN_PROCESS`` instead. Reading the row back goes through
    ``TrackingRepository._item``, which does ``TrackingStatus(row["status"])``,
    so every read of such an item raised ``ValueError``. The import reported
    success and the item was then invisible to the picker, the list and the
    scan, while the portal still counted it.
    """
    from config.environments import load_config
    from dataclasses import replace as dc_replace
    from packages.excel.factory_adapter import import_factory_items_to_db
    from packages.persistence.database import create_database_runtime, engine_path
    from packages.persistence.sqlalchemy_repository import Stage2Repository
    from packages.persistence.tracking_repository import TrackingRepository
    from packages.sqlengine import connect

    db_file = tmp_path / "factory.sqlite"
    config = dc_replace(load_config(), database_url=f"sqlite:///{db_file.as_posix()}")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()

    result = import_factory_items_to_db(
        [{
            "row_index": 1,
            "company": "SHL",
            "part_name": "Ban le truc",
            "quantity": "10",
            "unit": "EA",
            "price": None,
            "material": "AL6061",
            "requester": "",
            "surface_treatment": "",
            "outsourced": False,
            "size": "50 x 20",
            "notes": "",
            "delivery_schedule": "2026-11-01",
            "sheet_name": "DAY",
        }],
        str(db_file),
    )
    assert result["imported_tracking_items"] == 1

    repository = TrackingRepository(connect(engine_path(f"sqlite:///{db_file.as_posix()}")))

    # the import claimed success, so the row must be readable
    items = repository.list_items()
    assert len(items) == 1
    assert items[0].status.value == "IN_PRODUCTION"

    # and reachable by the two lookups the page and the scan use
    assert repository.get_item(items[0].internal_id).internal_id == items[0].internal_id
    code = items[0].tracking_code
    assert repository.scan_by_tracking_code(code)["tracking_code"] == code
