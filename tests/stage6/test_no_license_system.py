"""The license feature is gone. These guards keep it gone.

LO asked for the QR payment code to be removed. What was left behind was a
license system with no consumer: nothing in the product ever called
``/api/v1/license/validate``, so no behaviour anywhere depended on a license,
and the only caller of ``activate_license`` was a portal form that could never
receive a key once the payment path was gone. A shell that looks like a feature
is worse than no feature - it reads as enforced when nothing enforces it.

Each guard below names the thing that must not come back, and each was verified
RED by re-introducing the code it forbids.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2]

ALLOWED_TO_MENTION = {
    "tests/stage6/test_no_license_system.py",
    "tests/stage6/test_no_qr_payment.py",
    "tests/stage6/test_portal_page_structure.py",
}

FORBIDDEN_TOKENS = (
    "license_keys",
    "LicenseService",
    "LicenseError",
    "SERVER_LICENSE_SERVICE",
    "generate_license_key",
    "validate_license",
    "activate_license",
    "LicenseValidatePayload",
    "LicenseActivatePayload",
    "/api/v1/license/",
    "activateLicense",
    "tab-license",
    "KICH HOAT BAN QUYEN",
)


def _source_files():
    for path in sorted(SOURCE_ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(SOURCE_ROOT).as_posix()
        if relative.startswith((".git/", ".opencode/")):
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".ico", ".pdf", ".xlsx", ".db", ".pyc", ".min.js"}:
            continue
        yield relative, path


class TestModuleSurface:
    def test_the_license_service_module_is_gone(self):
        assert not (SOURCE_ROOT / "packages" / "application" / "license_service.py").exists()

    def test_no_migration_creates_a_license_table(self):
        root = SOURCE_ROOT / "migrations" / "engine"
        for path in root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "license_keys" not in source, f"{path.name} still creates license_keys"

    def test_the_application_package_exports_no_license_service(self):
        import packages.application as application

        assert not hasattr(application, "LicenseService")
        assert "LicenseService" not in getattr(application, "__all__", [])

    def test_the_contracts_have_no_license_payloads(self):
        import packages.contracts.api as contracts

        for name in ("LicenseValidatePayload", "LicenseActivatePayload"):
            assert not hasattr(contracts, name), f"{name} came back"

    def test_the_app_module_has_no_license_service(self):
        import apps.server.app as app_module

        assert not hasattr(app_module, "SERVER_LICENSE_SERVICE")


class TestRoutes:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import apps.server.app as app_module

        with TestClient(app_module.app) as test_client:
            yield test_client

    def test_no_license_route_is_registered(self, client):
        paths = {route.path for route in client.app.routes}
        license_paths = {path for path in paths if "license" in path.lower()}
        assert license_paths == set(), f"license routes still registered: {license_paths}"

    def test_license_endpoints_answer_404(self, client):
        for path in ("/api/v1/license/validate", "/api/v1/license/activate"):
            assert client.post(path, json={}).status_code == 404


class TestPortal:
    def test_the_portal_has_no_license_tab(self):
        source = (SOURCE_ROOT / "apps" / "server" / "portal.py").read_text(encoding="utf-8")
        assert "tab-license" not in source
        assert "activateLicense" not in source

    def test_the_portal_tab_set_is_the_four_functional_tabs(self):
        source = (SOURCE_ROOT / "apps" / "server" / "portal.py").read_text(encoding="utf-8")
        targets = set()
        for attribute in re.findall(r"onclick=\"([^\"]*)\"", source):
            match = re.match(r"switchTab\('([^']+)'\)$", attribute)
            if match:
                targets.add(match.group(1))
        assert targets == {"tab-live", "tab-qr", "tab-excel", "tab-connect"}


class TestSchema:
    def test_the_engine_schema_has_no_license_table(self, tmp_path):
        from tests.stage6.conftest import _engine_database

        database = _engine_database(tmp_path, "no-license.db")
        tables = set(database.schema.tables)
        assert "license_keys" not in tables
        assert "payments" not in tables

    def test_the_engine_head_is_seven(self, tmp_path):
        """The deployment gate's default head is 7, so the real head must be 7.

        Migration 0008 was added for license/payments without updating
        ``expected_engine_migration_head``, which stayed at "7" - so every
        release built with the default was rejected by its own readiness check
        and nothing caught it. Removing 0008 makes the two agree again.
        """

        from packages.sqlengine import Database
        from packages.sqlengine.migrations import applied_versions, load_migration_modules, run_migrations

        migrations = load_migration_modules(SOURCE_ROOT / "migrations" / "engine")
        database = Database(tmp_path / "head-engine")
        try:
            run_migrations(database, migrations, now=lambda: "2026-01-01T00:00:00+00:00")
            assert applied_versions(database) == {1, 2, 3, 4, 5, 6, 7}
        finally:
            database.close()

    def test_the_deployment_default_head_matches_the_real_head(self):
        """A default that drifts from reality rejects every release, silently.

        Migration 0008 was added for license/payments without updating either
        default, so the real head became 8 while both stayed at "7" - every
        release built with the defaults failed its own readiness check and no
        test compared the two. Removing 0008 makes them agree again.
        """

        import dataclasses
        import inspect

        from packages.deployment.artifact import build_release
        from packages.deployment.plans import PostgreSQLPlan
        from packages.sqlengine.migrations import load_migration_modules

        migrations = load_migration_modules(SOURCE_ROOT / "migrations" / "engine")
        real_head = str(max(version for version, _, _ in migrations))

        artifact_default = inspect.signature(build_release).parameters[
            "expected_engine_migration_head"
        ].default
        plan_default = next(
            field.default
            for field in dataclasses.fields(PostgreSQLPlan)
            if field.name == "engine_migration_head"
        )

        assert artifact_default == real_head, (
            f"artifact.py defaults to head {artifact_default}, real head is {real_head}"
        )
        assert plan_default == real_head, (
            f"plans.py defaults to head {plan_default}, real head is {real_head}"
        )


class TestNoSourceMentionsTheRemovedFeature:
    def test_no_source_mentions_the_removed_tokens(self):
        offenders = []
        for relative, path in _source_files():
            if relative in ALLOWED_TO_MENTION:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in FORBIDDEN_TOKENS:
                if token in text:
                    offenders.append(f"{relative}: {token}")
        assert offenders == [], "the removed license system is still referenced:\n" + "\n".join(
            offenders
        )
