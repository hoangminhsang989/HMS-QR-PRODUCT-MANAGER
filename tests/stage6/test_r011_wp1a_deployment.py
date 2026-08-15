import json
import subprocess
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest

from packages.deployment.artifact import ArtifactBuildError, build_release, verify_release
from packages.deployment.configuration import ConfigValidationError, production_config_template, validate_production_config
from packages.deployment.evidence import make_evidence, redact
from packages.deployment.inventory import InventoryValidationError, ReadOnlyInventoryCollector, validate_inventory
from packages.deployment.layout import ROOT_SPECS, validate_layout
from packages.deployment.lifecycle import LocalDeploymentBackend, install_release, rollback_release, uninstall, update_release
from packages.deployment.plans import DeploymentPlan, FirewallPlan, NetworkPlan, PostgreSQLPlan, ServiceRestartPolicy, TLSPlan, inventory_identity, postgresql_existing_decision
from packages.deployment.preflight import PreflightResult, dry_run, run_preflight
from packages.deployment.mutation import Mutation, MutationManifest

ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path("F:/PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST/r011-wp1a")

def _fixture_release(tmp_path, release_id="release"):
    source = tmp_path / f"source-{release_id}"; source.mkdir(); (source / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True); subprocess.run(["git", "add", "."], cwd=source, check=True); subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], cwd=source, check=True)
    return source, build_release(source, tmp_path / "releases", release_id=release_id, build_timestamp="2026-01-01T00:00:00+00:00", files=["pyproject.toml"])

def _valid_config():
    cfg = production_config_template(); cfg["port"] = 8080; cfg["bind_address"] = "inventory-selected-interface"; cfg["release_id"] = "release"; cfg["archive"]["identity"] = "archive-policy-v1"; return cfg

def _valid_inventory():
    doc = ReadOnlyInventoryCollector().collect()
    doc.update({"os": {"state": "KNOWN", "items": [{"architecture": "AMD64"}]}, "volumes": {"state": "KNOWN", "items": [{"free_bytes": 10_000, "filesystem": "synthetic-fs"}]}, "listeners": {"state": "KNOWN", "items": []}, "services": {"state": "KNOWN", "items": []}, "postgresql": {"state": "NOT_PRESENT", "items": []}})
    return doc

def _valid_plan(inventory, manifest):
    firewall = FirewallPlan("synthetic-prestate-hash", "hms-rule", "accepted-lan-scope")
    tls = TLSPlan("REVERSE_PROXY", "approved-source", "ref:tls/cert", "ref:service-identity", "api-listener", "operator-rotation")
    network = NetworkPlan("selected-interface", "inventory-selected-interface", 8080, "accepted-lan-scope", firewall, tls)
    pg = PostgreSQLPlan("INSTALL")
    roots = {name: f"resolved/{name.lower()}" for name in ROOT_SPECS}
    return DeploymentPlan(inventory_identity(inventory), manifest["release_id"], manifest["git_head"], roots, "project-owned-runtime", "approved-wrapper", "ref:service-identity", "hms-qr-service", pg, network, "ref:service-private", True, ("activate-previous-release",), ({"id": "m1"},), "ADMIN_REQUIRED_LATER", "NOT_EXPECTED", 1000)

def test_layout_and_restart_are_bounded():
    validate_layout(); assert len(ROOT_SPECS) == 8
    assert ServiceRestartPolicy().max_rapid_failures > 0

def test_artifact_build_verify_and_tamper(tmp_path):
    source, artifact = _fixture_release(tmp_path, "test-release")
    manifest = verify_release(artifact)
    assert manifest["files"][0]["path"] == "pyproject.toml"
    p = artifact / "payload" / "pyproject.toml"
    p.write_bytes(p.read_bytes() + b"x")
    with pytest.raises(ArtifactBuildError): verify_release(artifact)

def test_artifact_rejects_missing_and_extra(tmp_path):
    source, a = _fixture_release(tmp_path)
    (a / "payload" / "extra.txt").write_text("x")
    with pytest.raises(ArtifactBuildError): verify_release(a)

def test_artifact_identity_schema_and_manifest_negatives(tmp_path):
    _, a = _fixture_release(tmp_path)
    manifest_path = a / "manifest.json"; original = manifest_path.read_text(encoding="utf-8"); manifest = json.loads(original)
    with pytest.raises(ArtifactBuildError): verify_release(a, expected_head="0" * 40)
    with pytest.raises(ArtifactBuildError): verify_release(a, expected_tree="0" * 40)
    with pytest.raises(ArtifactBuildError): verify_release(a, expected_alembic_head="wrong")
    manifest["manifest_schema"] = "unsupported"; manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ArtifactBuildError): verify_release(a)
    manifest_path.write_text("{")
    with pytest.raises(ArtifactBuildError): verify_release(a)

def test_artifact_missing_wrong_hash_wrong_size_and_identity(tmp_path):
    _, a = _fixture_release(tmp_path); mf = a / "manifest.json"; original = json.loads(mf.read_text())
    for field, value in (("sha256", "0" * 64), ("size", original["files"][0]["size"] + 1)):
        changed = deepcopy(original); changed["files"][0][field] = value; mf.write_text(json.dumps(changed))
        with pytest.raises(ArtifactBuildError): verify_release(a)
    changed = deepcopy(original); changed["artifact_identity"]["file_inventory"] = "0" * 64; mf.write_text(json.dumps(changed))
    with pytest.raises(ArtifactBuildError): verify_release(a)
    mf.write_text(json.dumps(original)); (a / "payload" / "pyproject.toml").unlink()
    with pytest.raises(ArtifactBuildError): verify_release(a)

def test_manifest_is_deterministic_with_fixed_build_identity(tmp_path):
    source, a = _fixture_release(tmp_path, "stable")
    b = build_release(source, tmp_path / "second", release_id="stable", build_timestamp="2026-01-01T00:00:00+00:00", files=["pyproject.toml"])
    assert (a / "manifest.json").read_bytes() == (b / "manifest.json").read_bytes()

def test_certified_build_rejects_dirty_source_and_repo_output(tmp_path):
    source, _ = _fixture_release(tmp_path)
    (source / "pyproject.toml").write_text("dirty")
    with pytest.raises(ArtifactBuildError): build_release(source, tmp_path / "other", release_id="dirty", files=["pyproject.toml"])
    subprocess.run(["git", "restore", "pyproject.toml"], cwd=source, check=True)
    with pytest.raises(ArtifactBuildError): build_release(source, source / "output", release_id="inside", files=["pyproject.toml"])

def test_config_rejects_placeholder_and_plaintext():
    cfg = _valid_config()
    cfg["tls"] = {"mode": "PLAINTEXT", "certificate_ref": "ref:tls/cert"}
    with pytest.raises(ConfigValidationError): validate_production_config(cfg)
    cfg["tls"] = {"mode": "REVERSE_PROXY_TERMINATED", "certificate_ref": "ref:tls/cert"}
    assert validate_production_config(cfg)["schema_version"]

def test_inventory_read_only_and_unknown_semantics():
    seen = []
    def runner(command): seen.append(command); return {"state": "NOT_PRESENT"} if command == "postgresql" else {"state": "UNKNOWN"}
    doc = ReadOnlyInventoryCollector(runner).collect()
    assert "postgresql" in seen and doc["postgresql"]["state"] == "NOT_PRESENT"
    assert not set(seen) & {"New-Item", "sc create", "service start"}

def test_powershell_collector_is_local_read_only_and_stdout_only():
    script = (ROOT / "scripts/r011_collect_inventory_readonly.ps1").read_text(encoding="utf-8")
    forbidden = ("New-Item", "Remove-Item", "Set-Item", "Set-ItemProperty", "New-NetFirewallRule", "Set-NetFirewallRule", "Remove-NetFirewallRule", "Enter-PSSession", "Invoke-Command", "Restart-Computer", "Stop-Service", "Start-Service")
    assert not any(token in script for token in forbidden)
    assert "ConvertTo-Json" in script and "param()" in script

def test_inventory_rejects_malformed_and_secret():
    with pytest.raises(InventoryValidationError): validate_inventory({})
    doc = ReadOnlyInventoryCollector().collect(); doc["services"] = {"password": "x"}
    with pytest.raises(InventoryValidationError): validate_inventory(doc)

def test_inventory_synthetic_fixture_matrix_is_schema_safe():
    fixture = json.loads((ROOT / "tests/fixtures/r011_inventory_cases.json").read_text(encoding="utf-8"))
    assert fixture["source"] == "synthetic-only" and len(fixture["cases"]) >= 13
    for case in fixture["cases"]:
        doc = ReadOnlyInventoryCollector().collect()
        doc[case["section"]] = {k: v for k, v in case.items() if k not in {"name", "section"}}
        assert validate_inventory(doc)

def test_existing_postgres_decisions():
    assert postgresql_existing_decision("ABSENT") == "INSTALL"
    assert postgresql_existing_decision("COMPATIBLE_CANDIDATE", discovered_major=17) == "ADOPT"
    assert postgresql_existing_decision("COMPATIBLE_CANDIDATE", discovered_major=16) == "BLOCK"
    assert postgresql_existing_decision("INCOMPATIBLE", discovered_major=16) == "SIDE_BY_SIDE"
    assert postgresql_existing_decision("AMBIGUOUS") == "BLOCK"

def test_inventory_cross_field_contradiction_rejected():
    doc = ReadOnlyInventoryCollector().collect(); doc["listeners"] = {"state": "NOT_PRESENT", "items": ["synthetic"]}
    with pytest.raises(InventoryValidationError): validate_inventory(doc)

def test_dry_run_and_mutation_manifest_never_execute(tmp_path):
    _, artifact = _fixture_release(tmp_path); release = verify_release(artifact); inventory = _valid_inventory(); plan = _valid_plan(inventory, release)
    mutation = Mutation("m1", "RELEASE", True, "artifact-valid", "stage-release", "hash", "remove-stage", False, "NONE", "APP_INSTALL_ROOT", "R011-WP2")
    manifest = MutationManifest(mutations=(mutation,)).to_dict(); assert manifest["machine_execution_allowed"] is False
    result = dry_run(str(artifact), _valid_config(), inventory, plan)
    assert result["machine_mutation_count"] == 0 and result["executed"] is False

def test_preflight_negative_matrix_fails_closed(tmp_path):
    _, artifact = _fixture_release(tmp_path); release = verify_release(artifact); base = _valid_inventory(); base_plan = _valid_plan(base, release)
    cases = []
    inv = deepcopy(base); inv["os"]["items"][0]["architecture"] = "unsupported"; cases.append((inv, None))
    inv = deepcopy(base); inv["volumes"]["items"][0]["free_bytes"] = 0; cases.append((inv, None))
    inv = deepcopy(base); inv["listeners"]["items"] = [{"port": 8080}]; cases.append((inv, None))
    inv = deepcopy(base); inv["volumes"]["items"][0]["filesystem"] = ""; cases.append((inv, None))
    inv = deepcopy(base); inv["services"]["items"] = [{"name": "hms-qr-service"}]; cases.append((inv, None))
    cases += [(base, replace(base_plan, postgresql=replace(base_plan.postgresql, decision="BLOCK"))), (base, replace(base_plan, python_runtime="<unresolved>")), (base, replace(base_plan, secret_store_ref="unresolved")), (base, replace(base_plan, backup_prerequisite=False)), (base, replace(base_plan, network=replace(base_plan.network, tls=replace(base_plan.network.tls, certificate_ref="unresolved")))), (base, replace(base_plan, rollback_actions=()))]
    for inventory, explicit_plan in cases:
        plan = explicit_plan or replace(base_plan, inventory_sha256=inventory_identity(inventory))
        result = run_preflight(str(artifact), _valid_config(), inventory, plan)
        assert result.passed is False and result.machine_mutation_count == 0
    (artifact / "payload" / "pyproject.toml").write_bytes(b"tampered")
    result = run_preflight(str(artifact), _valid_config(), base, base_plan)
    assert not result.passed and result.checks["artifact"] == "FAIL" and result.machine_mutation_count == 0

def test_plan_binding_and_valid_preflight(tmp_path):
    _, artifact = _fixture_release(tmp_path); release = verify_release(artifact); inventory = _valid_inventory(); plan = _valid_plan(inventory, release)
    assert run_preflight(str(artifact), _valid_config(), inventory, plan).passed
    with pytest.raises(ValueError):
        from packages.deployment.plans import validate_plan
        validate_plan(replace(plan, inventory_sha256="0" * 64), inventory, release)

def test_install_update_activation_and_rollback_transactions(tmp_path):
    _, first = _fixture_release(tmp_path, "release-1"); _, second = _fixture_release(tmp_path, "release-2")
    backend = LocalDeploymentBackend(tmp_path / "backend"); preflight = PreflightResult(True)
    assert install_release(backend, first, preflight)["active_release"] == "release-1"
    assert update_release(backend, second, preflight, health_ready=False)["active_release"] == "release-1"
    state = update_release(backend, second, preflight); assert state["active_release"] == "release-2" and state["retained_releases"] == ["release-1"]
    with pytest.raises(ValueError): rollback_release(backend)
    assert rollback_release(backend, config_compatible=True, schema_compatible=True)["active_release"] == "release-1"

def test_uninstall_preserves_persistent_data(tmp_path):
    b = LocalDeploymentBackend(tmp_path)
    for name in ("APP_DATA_ROOT", "APP_LOG_ROOT", "LOCAL_INGEST_ROOT", "SECRET_STORE", "POSTGRESQL_DATA_ROOT"):
        b.path(name).joinpath("marker").write_text(name)
    b.path("APP_INSTALL_ROOT").joinpath("release").mkdir()
    uninstall(b)
    assert all((b.path(n) / "marker").exists() for n in ("APP_DATA_ROOT", "APP_LOG_ROOT", "LOCAL_INGEST_ROOT", "SECRET_STORE", "POSTGRESQL_DATA_ROOT"))

def test_evidence_redacts_markers():
    doc = make_evidence(authority="test", wp="WP1A", timestamp="now", baseline={}, target_machine_inventory_hash="synthetic-hash", release_identity={}, pre_state={}, planned_mutations=[], executed_mutations=[], post_state={}, verification={}, rollback_events=[], service_state={}, database_state={}, network_state={}, secret_scan_result="PASS", verdict="DRY_RUN", secret_value="UNIQUE-MARKER", note="postgresql://user:pass@host/db")
    blob = json.dumps(doc); assert "UNIQUE-MARKER" not in blob and "user:pass" not in blob
