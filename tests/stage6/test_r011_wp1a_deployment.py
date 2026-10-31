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

def _fixture_release(tmp_path, release_id="release"):
    source = tmp_path / f"source-{release_id}"; source.mkdir(); (source / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True); subprocess.run(["git", "add", "."], cwd=source, check=True); subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], cwd=source, check=True)
    return source, build_release(source, tmp_path / "releases", release_id=release_id, build_timestamp="2026-01-01T00:00:00+00:00", files=["pyproject.toml"])

def _valid_config():
    cfg = production_config_template(); cfg["port"] = 8080; cfg["bind_address"] = "inventory-selected-interface"; cfg["release_id"] = "release"; cfg["archive"]["identity"] = "archive-policy-v1"
    cfg["app_data_root"] = "Z:/synthetic-machine/app-data"; cfg["app_log_root"] = "Z:/synthetic-machine/app-logs"; cfg["local_ingest_root"] = "Z:/synthetic-machine/local-ingest"; return cfg

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
    with pytest.raises(ArtifactBuildError): verify_release(a, expected_engine_migration_head="wrong")
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

def test_release_ships_every_path_the_application_reads_from_the_repo(tmp_path):
    """The default selection must cover what the shipped code reads off disk.

    `build_release` assembles its payload from the Git tree, so anything the
    selection leaves out is absent from the artifact no matter how clean the
    tree is. It used to cover `apps/`, `packages/`, `config/` and `migrations/`
    but not `web/`, while `apps/mobile/web.py` reads `web/index.html`,
    `web/lan.html` and `web/vps.html` off SOURCE_ROOT at request time - so a
    certified release deployed a server whose entire mobile tier answered 503.
    Nothing caught it, because no test built a real release and then asked the
    application what it needed.

    The requirement is therefore derived from the code rather than listed by
    hand: every literal joined onto SOURCE_ROOT under `apps/` must be inside the
    default selection. A new runtime dependency on a file outside it fails here
    instead of on a factory machine.
    """

    import re

    from packages.deployment.artifact import _tree_entries

    read_at_runtime = set()
    pattern = re.compile(r'SOURCE_ROOT\s*/\s*"([^"]+)"(?:\s*/\s*"([^"]+)")*')
    for path in sorted((ROOT / "apps").rglob("*.py")):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            components = [c for c in match.groups() if c]
            if components:
                read_at_runtime.add("/".join(components))
    assert read_at_runtime, "no SOURCE_ROOT reads found under apps/ - the scan is broken"

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    entries = _tree_entries(ROOT, head)
    selected = {
        p for p in entries
        if p.startswith(("apps/", "packages/", "config/", "migrations/", "web/"))
        or p in {"pyproject.toml", "scripts/r011_collect_inventory_readonly.ps1"}
    }

    missing = sorted(
        p for p in read_at_runtime
        if p not in selected and not any(s.startswith(p + "/") for s in selected)
    )
    assert not missing, (
        "the default release selection omits paths the application reads from "
        "the repository at runtime, so a deployed release cannot serve them: "
        + ", ".join(missing)
    )

def test_release_artifact_actually_contains_the_mobile_builds(tmp_path):
    """End to end: build a real artifact from this repository and look inside."""

    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        pytest.skip("the worktree is dirty, so a certified build is not possible")
    dest = build_release(
        ROOT,
        tmp_path / "releases",
        release_id="payload-probe",
        build_timestamp="2026-01-01T00:00:00+00:00",
    )
    manifest = verify_release(dest)
    shipped = {entry["path"] for entry in manifest["files"]}
    for required in (
        "web/index.html",
        "web/lan.html",
        "web/vps.html",
        "apps/mobile/web.py",
        "apps/static/jsqr.min.js",
    ):
        assert required in shipped, f"the release artifact does not contain {required}"
    assert manifest["git_head"] == subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

def test_a_fresh_clone_is_clean_and_can_build_a_certified_release(tmp_path):
    """The only proof that matters: clone HEAD and build from the clone.

    Every other guard here reads the working tree, which is exactly the blind
    spot that let two different defects ship the same 503 symptom - the mobile
    builds existed only in the working tree, and then existed in the tree but
    not in the release selection.

    A clone is also the only place the checkout rules are exercised. Git for
    Windows sets core.autocrlf=true at the system level, so a clone is the one
    situation where the bytes a checkout produces may differ from the bytes the
    repository stores. .gitattributes pins the text files to LF for that reason,
    and the images are marked binary because each PNG carries a single CRLF
    byte pair in its compressed data - marking those as text made Git rewrite
    that pair, which left every clone reporting six permanently modified files
    and made build_release refuse to build from a clone at all.

    So this asserts both halves: the checkout is byte-identical to the tree, and
    a certified release can be produced from it.
    """

    clone = tmp_path / "clone"
    run = subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1", str(ROOT), str(clone)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert run.returncode == 0, f"clone failed: {run.stderr}"

    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=clone, capture_output=True, text=True
    ).stdout.strip()
    assert not dirty, (
        "a fresh clone is not byte-identical to the committed tree, so no "
        f"certified build is possible from it:\n{dirty}"
    )

    dest = build_release(
        clone,
        tmp_path / "releases",
        release_id="from-clone",
        build_timestamp="2026-01-01T00:00:00+00:00",
    )
    manifest = verify_release(dest)
    shipped = {entry["path"] for entry in manifest["files"]}
    for required in ("web/index.html", "web/lan.html", "web/vps.html"):
        assert required in shipped, f"a release built from a clone lacks {required}"

    # The images must survive the checkout untouched, bytes and all.
    for image in (
        "web/static/icon-192.png",
        "web/static/icon-512.png",
        "web/static/favicon.png",
        "apps/static/icon-192.png",
        "apps/static/icon-512.png",
        "apps/static/favicon.png",
    ):
        blob = subprocess.run(
            ["git", "cat-file", "blob", f"HEAD:{image}"], cwd=clone, capture_output=True
        ).stdout
        assert (clone / image).read_bytes() == blob, (
            f"{image} was rewritten by the checkout - it is being treated as text"
        )


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
