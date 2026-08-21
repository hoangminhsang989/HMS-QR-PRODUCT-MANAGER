from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from packages.deployment.provisioning import (
    BROAD_PRINCIPAL_SIDS,
    FILE_ALL_ACCESS,
    FILE_READ_EXECUTE_CHILD,
    NOT_REQUIRED,
    ProvisioningContractError,
    REQUIRED_LATER,
    REQUIRED_NOW,
    ROLE_SPECS,
    WindowsSecurityBackend,
    build_provisioning_plan,
    directory_model,
    provision,
)


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows ACL qualification")


@pytest.fixture
def security_context():
    backend = WindowsSecurityBackend()
    account = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}"
    return backend, backend.resolve_account_sid(account), backend.resolve_account_sid(
        r"HMS-PC\HMSQRService"
    )


def _plan(tmp_path: Path, security_context, *, roles=REQUIRED_NOW):
    backend, current_sid, service_sid = security_context
    root = tmp_path / "provisioning-root"
    plan = build_provisioning_plan(
        root,
        service_sid=service_sid,
        administrator_sid=current_sid,
        owner_sid=current_sid,
        roles=roles,
    )
    backend.create_secure_directory(root, plan.root_policy)
    return backend, plan


def test_directory_model_is_minimum_product_first_set():
    assert directory_model() == {
        "REQUIRED_NOW": ["releases", "runtime", "staging"],
        "REQUIRED_LATER": [
            "data",
            "ingest",
            "logs",
            "backups",
            "secrets",
            "rollback",
        ],
        "NOT_REQUIRED": ["temp"],
    }
    assert set(REQUIRED_NOW + REQUIRED_LATER + NOT_REQUIRED) == set(ROLE_SPECS)
    assert {ROLE_SPECS[role].authority_root for role in REQUIRED_NOW} == {
        "APP_INSTALL_ROOT",
        "ISOLATED_PRODUCTION_PYTHON_RUNTIME",
        "DEPLOYMENT_STAGING_ROOT",
    }


def test_clean_first_run_and_second_run_idempotence(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)
    first = provision(plan, dry_run=False, backend=backend)
    assert first.overall_status == "APPLIED"
    assert first.created_roles == list(REQUIRED_NOW)
    assert first.mutation_count == len(REQUIRED_NOW)
    assert sorted(path.name for path in plan.target_root.iterdir()) == sorted(REQUIRED_NOW)

    second = provision(plan, dry_run=False, backend=backend)
    assert second.overall_status == "ALREADY_CORRECT"
    assert second.already_correct_roles == list(REQUIRED_NOW)
    assert second.created_roles == []
    assert second.mutation_count == 0


def test_expected_acl_semantics_are_exact_and_not_broad(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)
    assert provision(plan, dry_run=False, backend=backend).overall_status == "APPLIED"
    for role in REQUIRED_NOW:
        snapshot = backend.inspect_security(plan.target_root / role)
        assert snapshot.matches(plan.role_policies[role])
        assert snapshot.protected
        assert not ({ace.sid for ace in snapshot.aces} & BROAD_PRINCIPAL_SIDS)
        recovery = {ace.sid: ace.access_mask for ace in snapshot.aces}
        assert recovery["S-1-5-18"] == FILE_ALL_ACCESS
        assert recovery[plan.administrator_sid] == FILE_ALL_ACCESS
        if role in {"releases", "runtime"}:
            assert recovery[plan.service_sid] == FILE_READ_EXECUTE_CHILD
        else:
            assert plan.service_sid not in recovery


def test_collision_with_file_fails_closed_without_mutation(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)
    collision = plan.target_root / "releases"
    collision.write_text("do not replace", encoding="utf-8")
    result = provision(plan, dry_run=False, backend=backend)
    assert result.overall_status == "FAILED"
    assert result.mutation_count == 0
    assert result.collision_information == [
        {"path": str(collision), "reason": "not a directory"}
    ]
    assert collision.read_text(encoding="utf-8") == "do not replace"


def test_disposable_junction_target_is_rejected(tmp_path, security_context):
    backend, current_sid, service_sid = security_context
    real_root = tmp_path / "real-root"
    real_plan = build_provisioning_plan(
        real_root,
        service_sid=service_sid,
        administrator_sid=current_sid,
        owner_sid=current_sid,
    )
    backend.create_secure_directory(real_root, real_plan.root_policy)
    junction = tmp_path / "junction-root"
    completed = subprocess.run(
        ["cmd", "/d", "/c", "mklink", "/J", str(junction), str(real_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    try:
        plan = build_provisioning_plan(
            junction,
            service_sid=service_sid,
            administrator_sid=current_sid,
            owner_sid=current_sid,
        )
        result = provision(plan, dry_run=False, backend=backend)
        assert result.overall_status == "FAILED"
        assert result.reparse_rejection == str(junction)
        assert result.mutation_count == 0
        assert list(real_root.iterdir()) == []
    finally:
        junction.rmdir()


def test_partial_failure_is_preserved_and_rerun_converges(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)

    class FailOnRuntime(WindowsSecurityBackend):
        def create_secure_directory(self, path, policy):
            if path.name == "runtime":
                raise OSError("simulated bounded runtime-role failure")
            return super().create_secure_directory(path, policy)

    failing = FailOnRuntime()
    first = provision(plan, dry_run=False, backend=failing)
    assert first.overall_status == "PARTIAL_FAILURE"
    assert first.created_roles == ["releases"]
    assert first.failed_role == "runtime"
    assert first.partial_state_status == "PRESERVED_CREATED_ROLES"
    assert (plan.target_root / "releases").is_dir()
    assert not (plan.target_root / "runtime").exists()

    resumed = provision(plan, dry_run=False, backend=backend)
    assert resumed.overall_status == "APPLIED"
    assert resumed.already_correct_roles == ["releases"]
    assert resumed.created_roles == ["runtime", "staging"]
    assert resumed.mutation_count == 2
    assert sorted(path.name for path in plan.target_root.iterdir()) == sorted(REQUIRED_NOW)


@pytest.mark.parametrize(
    "roles",
    [
        ("releases", "releases"),
        ("..",),
        ("nested/role",),
        (r"C:\absolute",),
        ("unknown",),
        ("temp",),
    ],
)
def test_invalid_or_unapproved_child_role_is_rejected(tmp_path, security_context, roles):
    _, _, service_sid = security_context
    with pytest.raises(ProvisioningContractError):
        build_provisioning_plan(tmp_path / "root", service_sid=service_sid, roles=roles)


def test_dry_run_reports_plan_and_performs_zero_mutation(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)
    before = list(plan.target_root.iterdir())
    result = provision(plan, dry_run=True, backend=backend)
    after = list(plan.target_root.iterdir())
    assert result.overall_status == "DRY_RUN"
    assert result.security_changes_required == list(REQUIRED_NOW)
    assert result.mutation_count == 0
    assert result.created_roles == []
    assert before == after == []
    serialized = result.to_dict()
    assert serialized["planned_role_count"] == 3
    assert json.dumps(serialized, sort_keys=True)


def test_unexpected_root_security_fails_closed(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)
    _, current_sid, service_sid = security_context
    mismatched_service_sid = service_sid.rsplit("-", 1)[0] + "-424242"
    mismatched = build_provisioning_plan(
        plan.target_root,
        service_sid=mismatched_service_sid,
        administrator_sid=current_sid,
        owner_sid=current_sid,
    )
    result = provision(mismatched, dry_run=True, backend=backend)
    assert result.overall_status == "FAILED"
    assert result.failed_role is None
    assert result.mutation_count == 0
    assert "owner/DACL" in result.errors[0]


def test_real_service_identity_is_resolved_read_only(security_context):
    _, _, service_sid = security_context
    assert service_sid.startswith("S-1-5-21-")
