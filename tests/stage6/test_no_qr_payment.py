"""The QR payment feature is gone. These guards keep it gone.

LO asked for the VietQR payment code to be removed. It was self-contained: a
``payments`` table, two API routes, a portal tab with a QR image, and a URL
builder on ``LicenseService``. What survives is the license system itself -
``license_keys``, validate and activate - because the portal's
"KICH HOAT BAN QUYEN" tab still needs a key to activate.

Each guard below names the thing that must not come back, and each was verified
RED by re-introducing the code it forbids.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SOURCE_ROOT = Path(__file__).resolve().parents[2]

# Files that may mention the removed feature because their docstring or their
# own assertions record that it was removed. Everything else must be silent.
ALLOWED_TO_MENTION = {
    "tests/stage6/test_no_qr_payment.py",
    "tests/stage6/test_portal_page_structure.py",
    "packages/application/license_service.py",
    "tests/stage6/test_license_service.py",
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
    """Every source file under the repo, relative to SOURCE_ROOT.

    Bytecode caches are skipped: a stale ``.pyc`` from before the removal still
    holds the old strings, and it is not source.
    """
    for path in sorted(SOURCE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(SOURCE_ROOT).as_posix()
        if relative.startswith((".git/", ".opencode/")):
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".ico", ".pdf", ".xlsx", ".db", ".pyc"}:
            continue
        yield relative, path


class TestServiceSurface:
    def test_license_service_has_no_payment_api(self):
        from packages.application.license_service import LicenseService

        for name in ("create_payment", "confirm_payment", "_build_vietqr_url"):
            assert not hasattr(LicenseService, name), f"{name} came back"

    def test_license_service_module_defines_no_payment_error(self):
        import packages.application.license_service as module

        assert not hasattr(module, "PaymentError")

    def test_license_service_reads_no_vietqr_environment(self):
        source = (SOURCE_ROOT / "packages" / "application" / "license_service.py").read_text(
            encoding="utf-8"
        )
        for name in ("bank_id", "account_number", "account_name", "template"):
            assert name not in source, f"VietQR config {name} is still read"

    def test_license_service_still_issues_keys_without_a_payment(self, tmp_path):
        """Removing payments must not remove the ability to issue a license key."""

        from tests.stage6.conftest import _engine_database
        from packages.application.license_service import LicenseService

        service = LicenseService(_engine_database(tmp_path, "no-payment.db"))
        key = service.generate_license_key(
            payment_id=None, customer_email="admin@example.com"
        )
        assert key.startswith("HMSQR-")


class TestContracts:
    def test_payment_payloads_are_gone(self):
        import packages.contracts.api as contracts

        for name in ("PaymentCreatePayload", "PaymentWebhookPayload"):
            assert not hasattr(contracts, name), f"{name} came back"

    def test_license_payloads_survive(self):
        import packages.contracts.api as contracts

        assert hasattr(contracts, "LicenseValidatePayload")
        assert hasattr(contracts, "LicenseActivatePayload")


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

    def test_license_endpoints_survive(self, client):
        paths = {route.path for route in client.app.routes}
        assert "/api/v1/license/validate" in paths
        assert "/api/v1/license/activate" in paths


class TestPortal:
    def test_portal_has_no_payment_tab(self):
        source = (SOURCE_ROOT / "apps" / "server" / "portal.py").read_text(encoding="utf-8")
        assert "tab-payment" not in source
        assert "createPayment" not in source

    def test_portal_license_tab_survives(self):
        source = (SOURCE_ROOT / "apps" / "server" / "portal.py").read_text(encoding="utf-8")
        assert "tab-license" in source
        assert "activateLicense" in source
        assert "/api/v1/license/activate" in source


class TestSchema:
    def test_engine_schema_has_no_payments_table(self, tmp_path):
        from tests.stage6.conftest import _engine_database

        database = _engine_database(tmp_path, "no-payments-table.db")
        assert "payments" not in set(database.schema.tables)
        assert "license_keys" in set(database.schema.tables)

    def test_migration_0008_creates_only_license_keys(self):
        source = (
            SOURCE_ROOT / "migrations" / "engine" / "0008_license_keys.py"
        ).read_text(encoding="utf-8")
        assert "CREATE TABLE license_keys" in source
        assert "CREATE TABLE payments" not in source
        assert "vietqr" not in source.lower()

    def test_no_migration_still_creates_a_payments_table(self):
        root = SOURCE_ROOT / "migrations" / "engine"
        for path in root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "CREATE TABLE payments" not in source, f"{path.name} still creates payments"
            assert "vietqr" not in source.lower(), f"{path.name} still builds a VietQR payload"

    def test_migration_0008_still_creates_license_keys_columns(self, tmp_path):
        from packages.sqlengine import Database
        from packages.sqlengine.migrations import load_migration_modules, run_migrations

        migrations = load_migration_modules(SOURCE_ROOT / "migrations" / "engine")
        database = Database(tmp_path / "m8-engine")
        try:
            run_migrations(database, migrations, now=lambda: "2026-01-01T00:00:00+00:00")
            columns = {column.name for column in database.schema.table("license_keys").columns}
            assert columns == {
                "key_id",
                "license_key",
                "product_tier",
                "status",
                "created_at",
                "activated_at",
                "expires_at",
                "customer_email",
                "payment_id",
                "hwid",
            }
        finally:
            database.close()


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
