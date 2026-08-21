from __future__ import annotations

import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
from types import MappingProxyType

import pytest

import packages.deployment.provisioning as provisioning_module
from packages.deployment.provisioning import (
    AceSpec,
    BROAD_PRINCIPAL_SIDS,
    FILE_ALL_ACCESS,
    FILE_GENERIC_READ,
    FILE_READ_EXECUTE_CHILD,
    NOT_REQUIRED,
    ProvisioningContractError,
    ProvisioningPlan,
    REQUIRED_LATER,
    REQUIRED_NOW,
    ROLE_SPECS,
    SecurityPolicy,
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


def _caller_owned_plan(tmp_path: Path, security_context):
    _, current_sid, service_sid = security_context
    source = build_provisioning_plan(
        tmp_path / "provisioning-root",
        service_sid=service_sid,
        administrator_sid=current_sid,
        owner_sid=current_sid,
    )
    roles = list(source.roles)
    policies = dict(source.role_policies)
    plan = ProvisioningPlan(
        target_root=source.target_root,
        roles=roles,
        service_sid=source.service_sid,
        administrator_sid=source.administrator_sid,
        root_policy=source.root_policy,
        role_policies=policies,
    )
    return source, plan, roles, policies


class _NoMutationBackend:
    def __init__(self):
        self.create_calls: list[object] = []

    def create_secure_directory(self, *args, **kwargs):
        self.create_calls.append((args, kwargs))
        raise AssertionError("invalid plans must fail before CreateDirectoryW")

    def __getattr__(self, name):
        raise AssertionError(f"invalid plans must fail before backend.{name}")


def _assert_boundary_rejection(plan: ProvisioningPlan):
    backend = _NoMutationBackend()
    result = provision(plan, dry_run=False, backend=backend)
    assert result.overall_status == "FAILED"
    assert result.mutation_count == 0
    assert result.root_namespace_status == "NOT_RUN"
    assert backend.create_calls == []
    return result


def _production_plan() -> ProvisioningPlan:
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING
    return build_provisioning_plan(
        binding.target_root,
        service_account_name=binding.service_account_name,
        service_sid=binding.service_sid,
        administrator_sid=binding.administrator_sid,
        production_binding=True,
    )


def _forged_production_policies() -> tuple[str, str, str, SecurityPolicy, dict[str, SecurityPolicy]]:
    fake_service_sid = "S-1-5-21-999-888-777-666"
    fake_administrator_sid = "S-1-5-21-999-888-777-667"
    fake_owner_sid = "S-1-5-21-999-888-777-668"
    fake_system_sid = "S-1-5-21-999-888-777-669"
    root_policy = provisioning_module._root_security_policy(
        service_sid=fake_service_sid,
        administrator_sid=fake_administrator_sid,
        owner_sid=fake_owner_sid,
        system_sid=fake_system_sid,
    )
    policies = {
        role: provisioning_module._role_security_policy(
            role,
            service_sid=fake_service_sid,
            administrator_sid=fake_administrator_sid,
            owner_sid=fake_owner_sid,
            system_sid=fake_system_sid,
        )
        for role in REQUIRED_NOW
    }
    return fake_service_sid, fake_administrator_sid, fake_owner_sid, root_policy, policies


def test_certified_production_binding_is_immutable_primitive_authority():
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING

    for field in binding._fields:
        assert type(getattr(binding, field)) is str
        with pytest.raises(AttributeError):
            object.__setattr__(binding, field, "forged")
        assert getattr(binding, field) != "forged"


def test_normal_certified_production_plan_construction_is_possible():
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING
    plan = _production_plan()

    assert plan.production_binding is True
    assert str(plan.target_root) == binding.target_root
    assert plan.service_account_name == binding.service_account_name
    assert plan.service_sid == binding.service_sid
    assert plan.administrator_sid == plan.owner_sid == binding.administrator_sid
    assert plan.root_policy == provisioning_module._certified_root_policy()
    assert dict(plan.role_policies) == {
        role: provisioning_module._certified_role_policy(role) for role in REQUIRED_NOW
    }


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("service_sid", "S-1-5-21-999-888-777-666", "service SID"),
        ("administrator_sid", "S-1-5-21-999-888-777-667", "administrator SID"),
        ("owner_sid", "S-1-5-21-999-888-777-668", "owner SID"),
    ],
)
def test_production_constructor_rejects_uncertified_identity(
    field, replacement, message
):
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING
    kwargs = {
        "service_account_name": binding.service_account_name,
        "service_sid": binding.service_sid,
        "administrator_sid": binding.administrator_sid,
        "owner_sid": binding.owner_sid,
        "production_binding": True,
    }
    kwargs[field] = replacement

    with pytest.raises(ProvisioningContractError, match=message):
        build_provisioning_plan(binding.target_root, **kwargs)


@pytest.mark.parametrize(
    ("service_account_name", "service_sid"),
    [
        (r"HMS-PC\HMSQRService", "S-1-5-21-999-888-777-666"),
        (r"HMS-PC\OtherService", "S-1-5-21-170807328-2858633000-3406472961-1009"),
        (r"HMS-PC\OtherService", "S-1-5-21-999-888-777-666"),
    ],
)
def test_production_constructor_rejects_service_account_name_sid_cross_binding(
    service_account_name, service_sid
):
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING

    with pytest.raises(ProvisioningContractError):
        build_provisioning_plan(
            binding.target_root,
            service_account_name=service_account_name,
            service_sid=service_sid,
            administrator_sid=binding.administrator_sid,
            owner_sid=binding.owner_sid,
            production_binding=True,
        )


def test_coordinated_production_identity_and_policy_forgery_rejects_before_backend():
    plan = _production_plan()
    fake_service, fake_administrator, fake_owner, root_policy, policies = (
        _forged_production_policies()
    )
    object.__setattr__(plan, "service_sid", fake_service)
    object.__setattr__(plan, "administrator_sid", fake_administrator)
    object.__setattr__(plan, "owner_sid", fake_owner)
    object.__setattr__(plan, "root_policy", root_policy)
    object.__setattr__(plan, "role_policies", MappingProxyType(policies))

    result = _assert_boundary_rejection(plan)

    assert "service SID" in result.errors[0]


def test_production_service_account_tamper_rejects_before_backend():
    plan = _production_plan()
    object.__setattr__(plan, "service_account_name", r"HMS-PC\OtherService")

    result = _assert_boundary_rejection(plan)

    assert "service account name" in result.errors[0]


def test_production_binding_flag_tamper_cannot_escape_canonical_root_gate():
    plan = _production_plan()
    object.__setattr__(plan, "production_binding", False)

    result = _assert_boundary_rejection(plan)

    assert "production binding" in result.errors[0]


def test_production_target_tamper_cannot_rebind_certified_identity():
    plan = _production_plan()
    object.__setattr__(plan, "target_root", Path(r"D:\HMS-QR-PROD-OTHER"))

    result = _assert_boundary_rejection(plan)

    assert "production binding" in result.errors[0]


def test_generic_binding_cannot_construct_or_tamper_to_production_root(
    tmp_path, security_context
):
    _, generic_plan, _, _ = _caller_owned_plan(tmp_path, security_context)
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING

    with pytest.raises(ProvisioningContractError, match="production binding"):
        build_provisioning_plan(
            binding.target_root,
            service_sid=generic_plan.service_sid,
            production_binding=False,
        )

    object.__setattr__(generic_plan, "target_root", Path(binding.target_root))
    result = _assert_boundary_rejection(generic_plan)
    assert "production binding" in result.errors[0]


def test_local_drive_alias_to_production_root_is_rejected_at_construction(monkeypatch):
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING
    alias = Path("X:\\")
    monkeypatch.setattr(
        provisioning_module,
        "_resolve_existing_target_root",
        lambda target: Path(binding.target_root) if target == alias else None,
    )

    with pytest.raises(ProvisioningContractError, match="production binding"):
        build_provisioning_plan(
            alias,
            service_sid=binding.service_sid,
            production_binding=False,
        )


def test_local_drive_alias_tamper_rejects_at_boundary_before_backend(
    tmp_path, security_context, monkeypatch
):
    _, generic_plan, _, _ = _caller_owned_plan(tmp_path, security_context)
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING
    alias = Path("X:\\")
    object.__setattr__(generic_plan, "target_root", alias)
    monkeypatch.setattr(
        provisioning_module,
        "_resolve_existing_target_root",
        lambda target: Path(binding.target_root) if target == alias else None,
    )

    result = _assert_boundary_rejection(generic_plan)

    assert "production binding" in result.errors[0]


def test_nonexisting_generic_root_stays_constructible_but_cannot_reach_backend(
    tmp_path, security_context
):
    _, _, service_sid = security_context
    plan = build_provisioning_plan(tmp_path / "not-created", service_sid=service_sid)

    result = _assert_boundary_rejection(plan)

    assert "final-path identity is unavailable" in result.errors[0]


def test_final_path_resolution_error_fails_closed_before_backend(
    tmp_path, security_context, monkeypatch
):
    _, generic_plan, _, _ = _caller_owned_plan(tmp_path, security_context)
    monkeypatch.setattr(
        provisioning_module,
        "_resolve_existing_target_root",
        lambda target: (_ for _ in ()).throw(
            ProvisioningContractError("simulated final-path failure")
        ),
    )

    result = _assert_boundary_rejection(generic_plan)

    assert "simulated final-path failure" in result.errors[0]


def test_parent_reparse_rejects_before_final_resolver_or_backend(
    tmp_path, security_context, monkeypatch
):
    _, plan, _, _ = _caller_owned_plan(tmp_path, security_context)
    reparse_parent = tmp_path / "reported-reparse-parent"
    object.__setattr__(plan, "target_root", reparse_parent / "child-root")
    resolver_calls: list[Path] = []

    monkeypatch.setattr(
        provisioning_module,
        "_target_is_filesystem_reparse_point",
        lambda path: path == reparse_parent,
    )
    monkeypatch.setattr(
        provisioning_module,
        "_resolve_existing_target_root",
        lambda path: resolver_calls.append(path) or None,
    )

    result = _assert_boundary_rejection(plan)

    assert result.reparse_rejection == str(reparse_parent)
    assert result.root_namespace_status == "NOT_RUN"
    assert resolver_calls == []


@pytest.mark.parametrize(("attributes", "expected"), [(WindowsSecurityBackend.FILE_ATTRIBUTE_REPARSE_POINT, True), (0, False)])
def test_reparse_detector_uses_windows_attributes_not_path_is_junction(monkeypatch, attributes, expected):
    monkeypatch.setattr(provisioning_module.os, "lstat", lambda path: type("Stat", (), {"st_file_attributes": attributes})())
    assert provisioning_module._target_is_filesystem_reparse_point(Path("X:\\missing")) is expected


def test_reparse_detector_missing_is_false_and_other_failures_fail_closed(monkeypatch):
    monkeypatch.setattr(provisioning_module.os, "lstat", lambda path: (_ for _ in ()).throw(FileNotFoundError()))
    assert provisioning_module._target_is_filesystem_reparse_point(Path("X:\\missing")) is False
    monkeypatch.setattr(provisioning_module.os, "lstat", lambda path: object())
    with pytest.raises(ProvisioningContractError, match="attribute authority"):
        provisioning_module._target_is_filesystem_reparse_point(Path("X:\\missing"))
    monkeypatch.setattr(provisioning_module.os, "lstat", lambda path: (_ for _ in ()).throw(OSError("denied")))
    with pytest.raises(ProvisioningContractError, match="reparse inspection failed"):
        provisioning_module._target_is_filesystem_reparse_point(Path("X:\\missing"))


def test_boundary_uses_resolved_generic_target_not_later_alias_redirect(
    tmp_path, security_context, monkeypatch
):
    backend, plan = _plan(tmp_path, security_context)
    physical_root = plan.target_root
    redirect_root = tmp_path / "later-alias-redirect"
    alias = Path("X:\\")
    extended_physical_root = Path("\\\\?\\" + str(physical_root))
    alias_resolution_count = 0
    observed_paths: list[Path] = []

    class RecordingBackend(WindowsSecurityBackend):
        def is_reparse_point(self, path):
            observed_paths.append(path)
            return super().is_reparse_point(path)

        def is_directory(self, path):
            observed_paths.append(path)
            return super().is_directory(path)

        def inspect_security(self, path):
            observed_paths.append(path)
            return super().inspect_security(path)

        def create_secure_directory(self, path, policy):
            observed_paths.append(path)
            return super().create_secure_directory(path, policy)

    def resolve_target(target):
        nonlocal alias_resolution_count
        if target == alias:
            alias_resolution_count += 1
            return extended_physical_root if alias_resolution_count == 1 else redirect_root
        if target == physical_root:
            return physical_root
        raise AssertionError(f"unexpected final-path lookup: {target}")

    object.__setattr__(plan, "target_root", alias)
    monkeypatch.setattr(provisioning_module, "_resolve_existing_target_root", resolve_target)

    result = provision(plan, dry_run=False, backend=RecordingBackend())

    assert result.overall_status == "APPLIED"
    assert result.target_root == str(physical_root)
    assert alias_resolution_count == 1
    assert observed_paths
    assert all(not str(path).casefold().startswith("x:") for path in observed_paths)
    assert all(
        physical_root == path
        or physical_root in path.parents
        or path in physical_root.parents
        for path in observed_paths
    )
    assert not redirect_root.exists()


def test_production_binding_true_alias_to_production_root_rejects(monkeypatch):
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING
    alias = Path("X:\\")
    monkeypatch.setattr(
        provisioning_module,
        "_resolve_existing_target_root",
        lambda target: Path(binding.target_root),
    )

    with pytest.raises(ProvisioningContractError, match="production binding"):
        build_provisioning_plan(
            alias,
            service_account_name=binding.service_account_name,
            service_sid=binding.service_sid,
            administrator_sid=binding.administrator_sid,
            owner_sid=binding.owner_sid,
            production_binding=True,
        )


def test_production_system_policy_forgery_rejects_before_backend():
    plan = _production_plan()
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING
    fake_system_sid = "S-1-5-21-999-888-777-669"
    root_policy = provisioning_module._root_security_policy(
        service_sid=binding.service_sid,
        administrator_sid=binding.administrator_sid,
        owner_sid=binding.owner_sid,
        system_sid=fake_system_sid,
    )
    policies = {
        role: provisioning_module._role_security_policy(
            role,
            service_sid=binding.service_sid,
            administrator_sid=binding.administrator_sid,
            owner_sid=binding.owner_sid,
            system_sid=fake_system_sid,
        )
        for role in REQUIRED_NOW
    }
    object.__setattr__(plan, "root_policy", root_policy)
    object.__setattr__(plan, "role_policies", MappingProxyType(policies))

    result = _assert_boundary_rejection(plan)

    assert "root policy" in result.errors[0]


def test_production_apply_host_hook_rejects_before_backend(monkeypatch):
    plan = _production_plan()
    binding = provisioning_module._CERTIFIED_PRODUCTION_BINDING
    monkeypatch.setattr(
        provisioning_module,
        "_resolve_existing_target_root",
        lambda target: Path(binding.target_root),
    )
    monkeypatch.setattr(provisioning_module, "_production_host_name", lambda: "OTHER-HOST")

    result = _assert_boundary_rejection(plan)

    assert "production host" in result.errors[0]


def test_generic_apply_does_not_consult_production_host_hook(
    tmp_path, security_context, monkeypatch
):
    backend, plan = _plan(tmp_path, security_context)
    monkeypatch.setattr(provisioning_module, "_production_host_name", lambda: "OTHER-HOST")

    result = provision(plan, dry_run=False, backend=backend)

    assert result.overall_status == "APPLIED"


def test_cli_rejects_noncertified_name_before_account_resolution(monkeypatch):
    class MustNotConstructBackend:
        def __init__(self):
            raise AssertionError("wrong account name must reject before resolution")

    monkeypatch.setattr(provisioning_module, "WindowsSecurityBackend", MustNotConstructBackend)

    with pytest.raises(ProvisioningContractError, match="service account name"):
        provisioning_module.main(
            [
                "--target-root",
                r"D:\HMS-QR-PROD",
                "--service-account",
                r"HMS-PC\OtherService",
            ]
        )


def test_cli_rejects_wrong_resolved_sid_before_provision(monkeypatch):
    class WrongSidBackend:
        def resolve_account_sid(self, account):
            assert account == provisioning_module._CERTIFIED_PRODUCTION_BINDING.service_account_name
            return "S-1-5-21-999-888-777-666"

    monkeypatch.setattr(provisioning_module, "WindowsSecurityBackend", WrongSidBackend)

    with pytest.raises(ProvisioningContractError, match="service SID"):
        provisioning_module.main(["--target-root", r"D:\HMS-QR-PROD"])


class _HostileSecurityPolicy(SecurityPolicy):
    """A policy subclass that attempts to bypass normal dataclass equality."""

    def __eq__(self, other):
        return True


def _hostile_policy(owner_sid: str) -> SecurityPolicy:
    return _HostileSecurityPolicy(
        owner_sid=owner_sid,
        aces=(AceSpec("S-1-5-21-999-888-777-666", FILE_ALL_ACCESS),),
    )


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


def test_role_specs_is_read_only_and_deferred_classification_is_preserved(
    tmp_path, security_context
):
    with pytest.raises(TypeError):
        ROLE_SPECS["data"] = ROLE_SPECS["releases"]

    assert ROLE_SPECS["data"].classification == "REQUIRED_LATER"
    _, _, service_sid = security_context
    for role in REQUIRED_LATER:
        with pytest.raises(ProvisioningContractError, match="REQUIRED_LATER"):
            build_provisioning_plan(tmp_path / role, service_sid=service_sid, roles=(role,))


@pytest.mark.parametrize("role", tuple(ROLE_SPECS))
@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("name", "forged-role"),
        ("classification", "REQUIRED_NOW"),
        ("purpose", "forged-purpose"),
        ("authority_root", "FORGED_ROOT"),
        ("service_access_mask", FILE_GENERIC_READ),
    ],
)
def test_role_specs_records_reject_object_setattr_for_every_field(
    role, field, replacement
):
    spec = ROLE_SPECS[role]
    original = getattr(spec, field)

    with pytest.raises(AttributeError):
        object.__setattr__(spec, field, replacement)

    assert getattr(spec, field) == original


def test_role_spec_tampering_cannot_admit_deferred_roles_or_weaken_acl_boundary(
    tmp_path, security_context
):
    data_spec = ROLE_SPECS["data"]
    release_spec = ROLE_SPECS["releases"]
    with pytest.raises(AttributeError):
        object.__setattr__(data_spec, "classification", "REQUIRED_NOW")
    with pytest.raises(AttributeError):
        object.__setattr__(release_spec, "service_access_mask", FILE_GENERIC_READ)

    _, _, service_sid = security_context
    with pytest.raises(ProvisioningContractError, match="REQUIRED_LATER"):
        build_provisioning_plan(tmp_path / "data-root", service_sid=service_sid, roles=("data",))

    source, plan, roles, policies = _caller_owned_plan(tmp_path, security_context)
    weakened_aces = (*source.role_policies["releases"].aces[:2], AceSpec(service_sid, FILE_GENERIC_READ))
    policies["releases"] = SecurityPolicy(source.root_policy.owner_sid, weakened_aces)
    with pytest.raises(ProvisioningContractError, match="canonical identity contract"):
        ProvisioningPlan(
            target_root=source.target_root,
            roles=roles,
            service_sid=source.service_sid,
            administrator_sid=source.administrator_sid,
            root_policy=source.root_policy,
            role_policies=policies,
            owner_sid=source.owner_sid,
        )

    object.__setattr__(plan, "role_policies", MappingProxyType(policies))
    result = _assert_boundary_rejection(plan)
    assert "canonical identity contract" in result.errors[0]

    deferred_plan = build_provisioning_plan(
        tmp_path / "deferred-boundary-root", service_sid=service_sid
    )
    deferred_policies = dict(deferred_plan.role_policies)
    deferred_policies["data"] = deferred_plan.role_policies["releases"]
    object.__setattr__(deferred_plan, "roles", deferred_plan.roles + ("data",))
    object.__setattr__(deferred_plan, "role_policies", MappingProxyType(deferred_policies))
    deferred_result = _assert_boundary_rejection(deferred_plan)
    assert "REQUIRED_LATER" in deferred_result.errors[0]


def test_plan_owns_immutable_roles_after_caller_list_mutation(tmp_path, security_context):
    _, plan, roles, _ = _caller_owned_plan(tmp_path, security_context)

    roles.append("data")

    assert plan.roles == REQUIRED_NOW
    assert "data" not in plan.roles


def test_plan_owns_read_only_policies_after_caller_dict_mutation(
    tmp_path, security_context
):
    source, plan, _, policies = _caller_owned_plan(tmp_path, security_context)

    policies["releases"] = source.role_policies["staging"]
    policies.pop("runtime")

    assert isinstance(plan.role_policies, MappingProxyType)
    assert plan.role_policies["releases"] == source.role_policies["releases"]
    assert set(plan.role_policies) == set(REQUIRED_NOW)


def test_plan_retains_only_new_canonical_nested_policy_values(
    tmp_path, security_context
):
    source, plan, _, policies = _caller_owned_plan(tmp_path, security_context)
    caller_root = source.root_policy
    caller_policy = policies["releases"]

    assert plan.root_policy is not caller_root
    assert plan.role_policies["releases"] is not caller_policy
    object.__setattr__(caller_root, "aces", ())
    object.__setattr__(caller_policy, "aces", ())

    assert len(plan.root_policy.aces) == 3
    assert len(plan.role_policies["releases"].aces) == 3


def test_normal_public_plan_container_mutation_is_rejected(tmp_path, security_context):
    _, plan, _, _ = _caller_owned_plan(tmp_path, security_context)

    with pytest.raises(AttributeError):
        plan.roles.append("data")
    with pytest.raises(TypeError):
        plan.role_policies["data"] = plan.role_policies["releases"]
    with pytest.raises(FrozenInstanceError):
        plan.roles = ("releases",)


def test_constructor_rejects_forged_or_unexpected_role_policy(
    tmp_path, security_context
):
    source, _, roles, policies = _caller_owned_plan(tmp_path, security_context)
    policies["releases"] = source.role_policies["staging"]

    with pytest.raises(ProvisioningContractError, match="canonical identity contract"):
        ProvisioningPlan(
            target_root=source.target_root,
            roles=roles,
            service_sid=source.service_sid,
            administrator_sid=source.administrator_sid,
            root_policy=source.root_policy,
            role_policies=policies,
        )

    policies = dict(source.role_policies)
    policies["data"] = source.role_policies["releases"]
    with pytest.raises(ProvisioningContractError, match="match planned roles exactly"):
        ProvisioningPlan(
            target_root=source.target_root,
            roles=roles,
            service_sid=source.service_sid,
            administrator_sid=source.administrator_sid,
            root_policy=source.root_policy,
            role_policies=policies,
        )


def test_hostile_role_policy_subclass_is_rejected_by_constructor_and_boundary(
    tmp_path, security_context
):
    source, plan, roles, policies = _caller_owned_plan(tmp_path, security_context)
    hostile = _hostile_policy(source.root_policy.owner_sid)
    policies["releases"] = hostile

    with pytest.raises(ProvisioningContractError, match="exact SecurityPolicy"):
        ProvisioningPlan(
            target_root=source.target_root,
            roles=roles,
            service_sid=source.service_sid,
            administrator_sid=source.administrator_sid,
            root_policy=source.root_policy,
            role_policies=policies,
            owner_sid=source.owner_sid,
        )

    object.__setattr__(plan, "role_policies", MappingProxyType(policies))
    result = _assert_boundary_rejection(plan)
    assert "exact SecurityPolicy" in result.errors[0]


def test_hostile_root_policy_subclass_is_rejected_by_constructor_and_boundary(
    tmp_path, security_context
):
    source, plan, roles, policies = _caller_owned_plan(tmp_path, security_context)
    hostile = _hostile_policy(source.root_policy.owner_sid)

    with pytest.raises(ProvisioningContractError, match="exact SecurityPolicy"):
        ProvisioningPlan(
            target_root=source.target_root,
            roles=roles,
            service_sid=source.service_sid,
            administrator_sid=source.administrator_sid,
            root_policy=hostile,
            role_policies=policies,
            owner_sid=source.owner_sid,
        )

    object.__setattr__(plan, "root_policy", hostile)
    result = _assert_boundary_rejection(plan)
    assert "exact SecurityPolicy" in result.errors[0]


def test_direct_plan_rejects_root_owner_not_bound_by_constructor_contract(
    tmp_path, security_context
):
    source, _, roles, policies = _caller_owned_plan(tmp_path, security_context)
    unbound_root = SecurityPolicy(
        owner_sid="S-1-5-21-999-888-777-666",
        aces=source.root_policy.aces,
    )

    with pytest.raises(ProvisioningContractError, match="canonical identity contract"):
        ProvisioningPlan(
            target_root=source.target_root,
            roles=roles,
            service_sid=source.service_sid,
            administrator_sid=source.administrator_sid,
            root_policy=unbound_root,
            role_policies=policies,
        )


@pytest.mark.parametrize(
    "target",
    [Path(r"\\server\share\hms-qr"), Path(r"F:\\safe\\..\\escaped")],
    ids=["unc", "traversal"],
)
def test_direct_plan_target_contract_rejects_constructor_and_boundary(
    tmp_path, security_context, target
):
    source, plan, roles, policies = _caller_owned_plan(tmp_path, security_context)

    with pytest.raises(ProvisioningContractError):
        ProvisioningPlan(
            target_root=target,
            roles=roles,
            service_sid=source.service_sid,
            administrator_sid=source.administrator_sid,
            root_policy=source.root_policy,
            role_policies=policies,
            owner_sid=source.owner_sid,
        )

    object.__setattr__(plan, "target_root", target)
    result = _assert_boundary_rejection(plan)
    assert "target root" in result.errors[0]


@pytest.mark.parametrize("role", REQUIRED_LATER)
def test_tampered_deferred_role_is_rejected_at_provision_boundary(
    tmp_path, security_context, role
):
    _, plan, _, _ = _caller_owned_plan(tmp_path, security_context)
    policies = dict(plan.role_policies)
    policies[role] = plan.role_policies["releases"]
    object.__setattr__(plan, "roles", plan.roles + (role,))
    object.__setattr__(plan, "role_policies", MappingProxyType(policies))

    result = _assert_boundary_rejection(plan)

    assert "REQUIRED_LATER" in result.errors[0]


@pytest.mark.parametrize(
    ("role", "classification"),
    [("temp", "NOT_REQUIRED"), ("unknown-role", "UNKNOWN")],
)
def test_tampered_temp_or_unknown_role_is_rejected_at_provision_boundary(
    tmp_path, security_context, role, classification
):
    _, plan, _, _ = _caller_owned_plan(tmp_path, security_context)
    policies = dict(plan.role_policies)
    policies[role] = plan.role_policies["releases"]
    object.__setattr__(plan, "roles", plan.roles + (role,))
    object.__setattr__(plan, "role_policies", MappingProxyType(policies))

    result = _assert_boundary_rejection(plan)

    assert classification in result.errors[0]


def test_tampered_mixed_plan_rejects_before_any_requested_role_mutation(
    tmp_path, security_context
):
    _, plan, _, _ = _caller_owned_plan(tmp_path, security_context)
    policies = dict(plan.role_policies)
    policies["data"] = plan.role_policies["releases"]
    object.__setattr__(plan, "roles", ("releases", "data"))
    object.__setattr__(plan, "role_policies", MappingProxyType(policies))

    result = _assert_boundary_rejection(plan)

    assert "REQUIRED_LATER" in result.errors[0]


def test_tampered_forged_policy_is_rejected_at_provision_boundary(
    tmp_path, security_context
):
    _, plan, _, _ = _caller_owned_plan(tmp_path, security_context)
    policies = dict(plan.role_policies)
    policies["releases"] = policies["staging"]
    object.__setattr__(plan, "role_policies", MappingProxyType(policies))

    result = _assert_boundary_rejection(plan)

    assert "canonical identity contract" in result.errors[0]


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
