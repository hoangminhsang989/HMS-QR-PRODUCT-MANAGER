"""The QR payment feature is gone. These guards keep it gone.

LO asked for the VietQR payment code to be removed. It was self-contained: a
``payments`` table, two API routes, a portal tab with a QR image, and a URL
builder on ``LicenseService``. Nothing survives it - the license system it fed
was removed separately, because nothing in the product ever consumed it (see
``test_no_license_system.py``).

Each guard below names the thing that must not come back, and each was verified
RED by re-introducing the code it forbids.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SOURCE_ROOT = Path(__file__).resolve().parents[2]

# Files that may mention the removed feature because their own assertions record
# that it was removed. Everything else must be silent.
ALLOWED_TO_MENTION = {
    "tests/stage6/test_no_qr_payment.py",
    "tests/stage6/test_no_license_system.py",
    "tests/stage6/test_portal_page_structure.py",
}

FORBIDDEN_TOKENS = (
    "vietqr",
    "HMS_QR_VIETQR_BANK_ID",
    "HMS_QR_VIETQR_ACCOUNT_NUMBER",
    "HMS_QR_VIETQR_ACCOUNT_NAME",
    "createPayment",
    "tab-payment",
    "payment-amount",
    "payment-email",
    "payment-tier",
    "payment-result",
    "payment-qr-img",
    "payment-info",
    "/api/v1/payments/",
)


def _tracked_source_files():
    """Every file git tracks, relative to SOURCE_ROOT.

    This walked the tree with ``rglob`` and skipped a denylist of extensions,
    despite its name and its docstring. ``installer/`` holds nine binaries
    totalling 331 MB - a 160 MB PySide6 wheel, a 73 MB one, a 42 MB one and a
    29 MB Python installer executable - none of them gitignored and none in the
    denylist, so three guards read hundreds of megabytes of wheel as UTF-8 text
    and raised ``MemoryError``. It failed once, then three times, as
    ``installer/`` grew.

    Asking git bounds the scan to the 3.2 MB of sources it claims to scan, and
    makes the name true. The suffix skip list is kept for the reason it was
    written - a ``.pyc`` is not source - but it is no longer load-bearing, which
    is the point: a denylist fails on the first extension nobody listed.
    """

    listed = subprocess.run(
        ["git", "ls-files"],
        cwd=SOURCE_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for relative in sorted(listed.splitlines()):
        if relative.startswith(".git/") or "__pycache__" in relative:
            continue
        path = SOURCE_ROOT / relative
        if not path.is_file():
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".ico", ".pdf", ".xlsx", ".db", ".pyc"}:
            continue
        yield relative, path


class TestContracts:
    def test_payment_payloads_are_gone(self):
        import packages.contracts.api as contracts

        for name in ("PaymentCreatePayload", "PaymentWebhookPayload"):
            assert not hasattr(contracts, name), f"{name} came back"




class TestRoutes:
    @pytest.fixture()
    def client(self):
        import apps.server.app as app_module

        with TestClient(app_module.app) as test_client:
            yield test_client

    def test_no_payment_route_is_registered(self, client):
        paths = {route.path for route in client.app.routes}
        payment_paths = {path for path in paths if "payment" in path.lower()}
        assert payment_paths == set(), f"payment routes still registered: {payment_paths}"

    def test_payment_endpoints_answer_404(self, client):
        for path in ("/api/v1/payments/create", "/api/v1/payments/webhook"):
            assert client.post(path, json={}).status_code == 404




class TestPortal:
    def test_portal_has_no_payment_tab(self):
        source = (SOURCE_ROOT / "apps" / "server" / "portal.py").read_text(encoding="utf-8")
        assert "tab-payment" not in source
        assert "createPayment" not in source




class TestSchema:
    def test_engine_schema_has_no_payments_table(self, tmp_path):
        from tests.stage6.conftest import _engine_database

        database = _engine_database(tmp_path, "no-payments-table.db")
        assert "payments" not in set(database.schema.tables)


    def test_no_migration_creates_a_payment_or_license_table(self):
        root = SOURCE_ROOT / "migrations" / "engine"
        for path in root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "CREATE TABLE payments" not in source, f"{path.name} still creates payments"
            assert "license_keys" not in source, f"{path.name} still creates license_keys"
            assert "vietqr" not in source.lower(), f"{path.name} still builds a VietQR payload"

class TestNoSourceMentionsTheRemovedFeature:
    def test_no_tracked_source_mentions_the_removed_tokens(self):
        offenders = []
        for relative, path in _tracked_source_files():
            if relative in ALLOWED_TO_MENTION:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()
            for token in FORBIDDEN_TOKENS:
                if token.lower() in lowered:
                    offenders.append(f"{relative}: {token}")
        assert offenders == [], "removed QR payment code is still referenced:\n" + "\n".join(
            offenders
        )

    def test_no_source_builds_a_vietqr_image_url(self):
        pattern = re.compile(r"img\.vietqr\.io")
        offenders = [
            relative
            for relative, path in _tracked_source_files()
            if relative not in ALLOWED_TO_MENTION
            and pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
        ]
        assert offenders == [], f"VietQR image URL still built in: {offenders}"
