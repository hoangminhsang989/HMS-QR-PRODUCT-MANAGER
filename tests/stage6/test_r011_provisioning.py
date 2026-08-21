from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

import packages.deployment.provisioning as provisioning_module
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
    _role_security_policy,
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
    ],
)
def test_invalid_child_role_is_rejected(tmp_path, security_context, roles):
    _, _, service_sid = security_context
    with pytest.raises(ProvisioningContractError):
        build_provisioning_plan(tmp_path / "root", service_sid=service_sid, roles=roles)


@pytest.mark.parametrize("role", REQUIRED_LATER)
def test_deferred_public_role_request_is_rejected_with_classification(
    tmp_path, security_context, role
):
    _, _, service_sid = security_context

    with pytest.raises(ProvisioningContractError) as exc_info:
        build_provisioning_plan(tmp_path / "root", service_sid=service_sid, roles=(role,))

    assert str(exc_info.value) == (
        f"role '{role}' has classification REQUIRED_LATER; only REQUIRED_NOW roles "
        "may be requested in the current provisioning stage"
    )


@pytest.mark.parametrize(
    ("roles", "role", "classification"),
    [
        (("releases", "data"), "data", "REQUIRED_LATER"),
        (("runtime", "secrets"), "secrets", "REQUIRED_LATER"),
        (("staging", "rollback"), "rollback", "REQUIRED_LATER"),
        (("temp",), "temp", "NOT_REQUIRED"),
        (("unknown-role",), "unknown-role", "UNKNOWN"),
    ],
)
def test_non_current_public_role_request_fails_closed(
    tmp_path, security_context, roles, role, classification
):
    _, _, service_sid = security_context

    with pytest.raises(ProvisioningContractError) as exc_info:
        build_provisioning_plan(tmp_path / "root", service_sid=service_sid, roles=roles)

    assert str(exc_info.value) == (
        f"role '{role}' has classification {classification}; only REQUIRED_NOW roles "
        "may be requested in the current provisioning stage"
    )


@pytest.mark.parametrize("role", REQUIRED_LATER)
def test_cli_deferred_public_role_request_is_rejected_before_provisioning(
    tmp_path, security_context, monkeypatch, role
):
    _, _, service_sid = security_context
    create_calls: list[object] = []

    class NoMutationBackend:
        def resolve_account_sid(self, account):
            return service_sid

        def create_secure_directory(self, *args, **kwargs):
            create_calls.append((args, kwargs))
            raise AssertionError("CLI must reject the role before any directory creation")

    monkeypatch.setattr(provisioning_module, "WindowsSecurityBackend", NoMutationBackend)

    with pytest.raises(ProvisioningContractError) as exc_info:
        provisioning_module.main(
            ["--target-root", str(tmp_path / "root"), "--roles", role, "--apply"]
        )

    assert str(exc_info.value) == (
        f"role '{role}' has classification REQUIRED_LATER; only REQUIRED_NOW roles "
        "may be requested in the current provisioning stage"
    )
    assert create_calls == []


@pytest.mark.parametrize(
    ("roles", "role", "classification"),
    [
        (("releases", "data"), "data", "REQUIRED_LATER"),
        (("temp",), "temp", "NOT_REQUIRED"),
        (("unknown-role",), "unknown-role", "UNKNOWN"),
    ],
)
def test_cli_non_current_role_request_fails_closed_before_provisioning(
    tmp_path, security_context, monkeypatch, roles, role, classification
):
    _, _, service_sid = security_context
    create_calls: list[object] = []

    class NoMutationBackend:
        def resolve_account_sid(self, account):
            return service_sid

        def create_secure_directory(self, *args, **kwargs):
            create_calls.append((args, kwargs))
            raise AssertionError("CLI must reject the role before any directory creation")

    monkeypatch.setattr(provisioning_module, "WindowsSecurityBackend", NoMutationBackend)

    with pytest.raises(ProvisioningContractError) as exc_info:
        provisioning_module.main(
            ["--target-root", str(tmp_path / "root"), "--roles", *roles, "--apply"]
        )

    assert str(exc_info.value) == (
        f"role '{role}' has classification {classification}; only REQUIRED_NOW roles "
        "may be requested in the current provisioning stage"
    )
    assert create_calls == []


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


def test_namespace_preflight_reports_absent_deferred_roles(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)

    result = provision(plan, dry_run=True, backend=backend)

    assert result.root_namespace_status == "PASS"
    assert result.deferred_roles_present == []
    assert result.deferred_roles_absent == list(REQUIRED_LATER)
    assert {
        (entry["classification"], entry["status"])
        for entry in result.root_entries_inspected
    } == {("REQUESTED_ROLE", "PLANNED_CREATE")}


def test_namespace_enumeration_failure_does_not_claim_deferred_absence(
    tmp_path, security_context, monkeypatch
):
    backend, plan = _plan(tmp_path, security_context)
    original_iterdir = Path.iterdir

    def fail_target_enumeration(path):
        if path == plan.target_root:
            raise PermissionError("simulated namespace enumeration denial")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fail_target_enumeration)

    result = provision(plan, dry_run=True, backend=backend)

    assert result.overall_status == "FAILED"
    assert result.root_namespace_status == "FAIL"
    assert result.deferred_roles_absent == []
    assert result.deferred_roles_present == []
    assert result.root_entries_inspected == []
    assert result.mutation_count == 0


def test_exact_deferred_role_is_accepted_from_authoritative_role_policy(
    tmp_path, security_context
):
    backend, plan = _plan(tmp_path, security_context)
    deferred_policy = _role_security_policy(
        "data",
        service_sid=plan.service_sid,
        administrator_sid=plan.administrator_sid,
        owner_sid=plan.root_policy.owner_sid,
    )
    deferred = plan.target_root / "data"
    backend.create_secure_directory(deferred, deferred_policy)

    result = provision(plan, dry_run=True, backend=backend)

    assert result.overall_status == "DRY_RUN"
    assert result.root_namespace_status == "PASS"
    assert result.deferred_roles_present == ["data"]
    assert "data" not in result.deferred_roles_absent
    assert {
        "path": str(deferred),
        "classification": "DEFERRED_ROLE",
        "status": "DEFERRED_PRESENT_EXACT",
    } in result.root_entries_inspected


def test_deferred_file_collision_blocks_first_requested_mutation(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)
    deferred = plan.target_root / "data"
    deferred.write_text("do not replace", encoding="utf-8")

    result = provision(plan, dry_run=False, backend=backend)

    assert result.overall_status == "FAILED"
    assert result.root_namespace_status == "FAIL"
    assert result.mutation_count == 0
    assert not (plan.target_root / "releases").exists()
    assert result.incompatible_root_entries == ["data"]
    assert result.collision_information == [
        {"path": str(deferred), "reason": "not a directory"}
    ]
    assert deferred.read_text(encoding="utf-8") == "do not replace"


def test_deferred_junction_is_rejected_before_any_requested_mutation(
    tmp_path, security_context
):
    backend, plan = _plan(tmp_path, security_context)
    target = tmp_path / "deferred-target"
    target.mkdir()
    deferred = plan.target_root / "logs"
    completed = subprocess.run(
        ["cmd", "/d", "/c", "mklink", "/J", str(deferred), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    try:
        result = provision(plan, dry_run=False, backend=backend)
        assert result.overall_status == "FAILED"
        assert result.reparse_rejection == str(deferred)
        assert result.mutation_count == 0
        assert not (plan.target_root / "releases").exists()
        assert result.incompatible_root_entries == ["logs"]
    finally:
        deferred.rmdir()


def test_deferred_security_mismatch_fails_closed(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)
    deferred = plan.target_root / "data"
    backend.create_secure_directory(deferred, plan.role_policies["releases"])

    result = provision(plan, dry_run=True, backend=backend)

    assert result.overall_status == "FAILED"
    assert result.root_namespace_status == "FAIL"
    assert result.mutation_count == 0
    assert result.incompatible_root_entries == ["data"]
    assert result.collision_information == [
        {"path": str(deferred), "reason": "security policy mismatch"}
    ]


@pytest.mark.parametrize(
    "failure",
    [
        OSError("simulated requested-role inspection failure"),
        ProvisioningContractError("simulated hostile ACL contract failure"),
    ],
    ids=["os-error", "acl-contract-error"],
)
def test_requested_inspection_failure_keeps_deferred_entry_classified(
    tmp_path, security_context, failure
):
    backend, plan = _plan(tmp_path, security_context)
    requested = plan.target_root / "releases"
    backend.create_secure_directory(requested, plan.role_policies["releases"])
    deferred_policy = _role_security_policy(
        "data",
        service_sid=plan.service_sid,
        administrator_sid=plan.administrator_sid,
        owner_sid=plan.root_policy.owner_sid,
    )
    deferred = plan.target_root / "data"
    backend.create_secure_directory(deferred, deferred_policy)

    class FailRequestedInspection(WindowsSecurityBackend):
        def inspect_security(self, path):
            if path == requested:
                raise failure
            return super().inspect_security(path)

    result = provision(plan, dry_run=False, backend=FailRequestedInspection())

    assert result.overall_status == "FAILED"
    assert result.mutation_count == 0
    assert result.incompatible_root_entries == ["releases"]
    assert "data" in result.deferred_roles_present
    assert "data" not in result.deferred_roles_absent
    assert {
        "path": str(deferred),
        "classification": "DEFERRED_ROLE",
        "status": "DEFERRED_PRESENT_EXACT",
    } in result.root_entries_inspected


@pytest.mark.parametrize(
    ("name", "classification", "status", "reason"),
    [
        ("temp", "NOT_ALLOWED_ROLE", "NOT_ALLOWED_ROLE_PRESENT", "not allowed root role"),
        ("unexpected", "UNKNOWN_ENTRY", "UNKNOWN_ENTRY_PRESENT", "unexpected root entry"),
    ],
)
def test_unapproved_or_unknown_root_entry_fails_closed(
    tmp_path, security_context, name, classification, status, reason
):
    backend, plan = _plan(tmp_path, security_context)
    entry = plan.target_root / name
    entry.mkdir()

    result = provision(plan, dry_run=False, backend=backend)

    assert result.overall_status == "FAILED"
    assert result.root_namespace_status == "FAIL"
    assert result.mutation_count == 0
    assert not (plan.target_root / "releases").exists()
    assert result.collision_information == [{"path": str(entry), "reason": reason}]
    assert {
        "path": str(entry),
        "classification": classification,
        "status": status,
    } in result.root_entries_inspected


def test_dry_run_and_apply_share_the_same_namespace_preflight(tmp_path, security_context):
    backend, plan = _plan(tmp_path, security_context)
    (plan.target_root / "temp").mkdir()

    dry_run = provision(plan, dry_run=True, backend=backend)
    apply = provision(plan, dry_run=False, backend=backend)

    assert dry_run.overall_status == apply.overall_status == "FAILED"
    assert dry_run.root_namespace_status == apply.root_namespace_status == "FAIL"
    assert dry_run.root_entries_inspected == apply.root_entries_inspected
    assert dry_run.collision_information == apply.collision_information
    assert dry_run.mutation_count == apply.mutation_count == 0


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
