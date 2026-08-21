"""Idempotent Windows provisioning for approved Machine-A child roles.

The command-line interface is dry-run by default.  A future, separately
authorized production stage may opt into mutation with ``--apply``.  This
module never creates the target root, changes its owner/DACL, manages accounts,
or deletes an incompatible object.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Iterable, Mapping, NamedTuple


SYSTEM_SID: Final = "S-1-5-18"
ADMINISTRATORS_SID: Final = "S-1-5-32-544"
BROAD_PRINCIPAL_SIDS: Final = frozenset(
    {"S-1-1-0", "S-1-5-11", "S-1-5-32-545"}
)

FILE_ALL_ACCESS: Final = 0x001F01FF
FILE_GENERIC_READ: Final = 0x00120089
FILE_GENERIC_EXECUTE: Final = 0x001200A0
FILE_READ_EXECUTE_CHILD: Final = 0x001200A9
FILE_MODIFY: Final = 0x001301BF
OBJECT_AND_CONTAINER_INHERIT: Final = 0x03

REQUIRED_NOW: Final = ("releases", "runtime", "staging")
REQUIRED_LATER: Final = (
    "data",
    "ingest",
    "logs",
    "backups",
    "secrets",
    "rollback",
)
NOT_REQUIRED: Final = ("temp",)


class ProvisioningContractError(ValueError):
    """The requested target, role, or security contract is unsafe."""


class SecurityInspectionError(OSError):
    """Windows could not prove the required filesystem security state."""


@dataclass(frozen=True, order=True)
class AceSpec:
    sid: str
    access_mask: int
    flags: int = OBJECT_AND_CONTAINER_INHERIT
    ace_type: int = 0  # ACCESS_ALLOWED_ACE_TYPE

    def __post_init__(self) -> None:
        if not self.sid.startswith("S-1-"):
            raise ProvisioningContractError(f"invalid SID: {self.sid}")
        if self.sid in BROAD_PRINCIPAL_SIDS:
            raise ProvisioningContractError(
                f"broad principal is forbidden in provisioning ACLs: {self.sid}"
            )
        if not 0 <= self.access_mask <= 0xFFFFFFFF:
            raise ProvisioningContractError("access mask must fit an unsigned DWORD")
        if self.flags not in {0, OBJECT_AND_CONTAINER_INHERIT}:
            raise ProvisioningContractError("only exact or OI/CI ACEs are supported")
        if self.ace_type != 0:
            raise ProvisioningContractError("only explicit allow ACEs are supported")

    def to_dict(self) -> dict[str, object]:
        return {
            "sid": self.sid,
            "access_mask": f"0x{self.access_mask:08X}",
            "flags": f"0x{self.flags:02X}",
            "ace_type": "ALLOW",
        }


@dataclass(frozen=True)
class SecurityPolicy:
    owner_sid: str
    aces: tuple[AceSpec, ...]
    protected: bool = True

    def __post_init__(self) -> None:
        if not self.owner_sid.startswith("S-1-"):
            raise ProvisioningContractError(f"invalid owner SID: {self.owner_sid}")
        if self.owner_sid in BROAD_PRINCIPAL_SIDS:
            raise ProvisioningContractError("a broad principal cannot own a role")
        if not self.protected:
            raise ProvisioningContractError("provisioned DACLs must be protected")
        if not self.aces:
            raise ProvisioningContractError("an explicit recovery ACL is required")
        identities = [ace.sid for ace in self.aces]
        if len(identities) != len(set(identities)):
            raise ProvisioningContractError("duplicate ACL principals are forbidden")

    @property
    def sddl(self) -> str:
        flag_name = {0: "", OBJECT_AND_CONTAINER_INHERIT: "OICI"}
        ace_text = "".join(
            f"(A;{flag_name[ace.flags]};0x{ace.access_mask:08X};;;{ace.sid})"
            for ace in self.aces
        )
        return f"O:{self.owner_sid}D:P{ace_text}"

    def to_dict(self) -> dict[str, object]:
        return {
            "owner_sid": self.owner_sid,
            "protected": self.protected,
            "aces": [ace.to_dict() for ace in self.aces],
        }


@dataclass(frozen=True)
class SecuritySnapshot:
    owner_sid: str
    protected: bool
    aces: tuple[AceSpec, ...]

    def matches(self, policy: SecurityPolicy) -> bool:
        return (
            self.owner_sid == policy.owner_sid
            and self.protected == policy.protected
            and sorted(self.aces) == sorted(policy.aces)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "owner_sid": self.owner_sid,
            "protected": self.protected,
            "aces": [ace.to_dict() for ace in sorted(self.aces)],
        }


class RoleSpec(NamedTuple):
    """Immutable catalog record used as the sole role-policy authority."""

    name: str
    classification: str
    purpose: str
    authority_root: str
    service_access_mask: int | None


ROLE_SPECS: Final = MappingProxyType({
    "releases": RoleSpec(
        "releases", "REQUIRED_NOW", "immutable certified releases", "APP_INSTALL_ROOT", FILE_READ_EXECUTE_CHILD
    ),
    "runtime": RoleSpec(
        "runtime", "REQUIRED_NOW", "isolated versioned Python runtime", "ISOLATED_PRODUCTION_PYTHON_RUNTIME", FILE_READ_EXECUTE_CHILD
    ),
    "staging": RoleSpec(
        "staging", "REQUIRED_NOW", "hash-verified deployment staging", "DEPLOYMENT_STAGING_ROOT", None
    ),
    "data": RoleSpec(
        "data", "REQUIRED_LATER", "persistent application state", "APP_DATA_ROOT", FILE_MODIFY
    ),
    "ingest": RoleSpec(
        "ingest", "REQUIRED_LATER", "durable local-first file intake", "LOCAL_INGEST_ROOT", FILE_MODIFY
    ),
    "logs": RoleSpec(
        "logs", "REQUIRED_LATER", "rotated sanitized operational logs", "APP_LOG_ROOT", FILE_MODIFY
    ),
    "backups": RoleSpec(
        "backups", "REQUIRED_LATER", "operator-owned protected recovery artifacts", "PROTECTED_BACKUP_DESTINATION", None
    ),
    "secrets": RoleSpec(
        "secrets", "REQUIRED_LATER", "DPAPI-protected service-private references", "SECRET_STORE", FILE_GENERIC_READ
    ),
    "rollback": RoleSpec(
        "rollback", "REQUIRED_LATER", "retained known-good release", "ROLLBACK_RELEASE_ROOT", FILE_READ_EXECUTE_CHILD
    ),
    "temp": RoleSpec(
        "temp", "NOT_REQUIRED", "scoped transient work, not a top-level persistent role", "SCOPED_TEMPORARY_WORKSPACE", FILE_MODIFY
    ),
})
# Keep the public catalog readable while preventing callers from changing the
# security classifications that are the authority for plan validation.


@dataclass(frozen=True)
class ProvisioningPlan:
    target_root: Path
    roles: tuple[str, ...]
    service_sid: str
    administrator_sid: str
    root_policy: SecurityPolicy
    role_policies: Mapping[str, SecurityPolicy]
    production_binding: bool = False
    owner_sid: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        target, roles, owner, root_policy, policies = _validate_plan_state(self)
        # A frozen dataclass does not freeze caller-owned lists or dictionaries.
        # Take ownership during construction, before the public instance escapes,
        # and retain only policies freshly derived from ROLE_SPECS.
        object.__setattr__(self, "target_root", target)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "owner_sid", owner)
        object.__setattr__(self, "root_policy", root_policy)
        object.__setattr__(self, "role_policies", MappingProxyType(policies))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "r011.provisioning-plan.v1",
            "target_root": str(self.target_root),
            "roles": list(self.roles),
            "planned_role_count": len(self.roles),
            "service_sid": self.service_sid,
            "administrator_sid": self.administrator_sid,
            "root_policy": self.root_policy.to_dict(),
            "role_policies": {
                role: self.role_policies[role].to_dict() for role in self.roles
            },
            "role_contracts": {
                role: {
                    "classification": ROLE_SPECS[role].classification,
                    "purpose": ROLE_SPECS[role].purpose,
                    "authority_root": ROLE_SPECS[role].authority_root,
                }
                for role in self.roles
            },
            "production_binding": self.production_binding,
            "destructive_operation_count": 0,
        }


@dataclass
class ProvisioningResult:
    overall_status: str
    target_root: str
    planned_roles: list[str]
    created_roles: list[str] = field(default_factory=list)
    already_correct_roles: list[str] = field(default_factory=list)
    failed_role: str | None = None
    collision_information: list[dict[str, str]] = field(default_factory=list)
    reparse_rejection: str | None = None
    security_verification_status: str = "NOT_RUN"
    partial_state_status: str = "NONE"
    mutation_count: int = 0
    security_changes_required: list[str] = field(default_factory=list)
    root_namespace_status: str = "NOT_RUN"
    root_entries_inspected: list[dict[str, str]] = field(default_factory=list)
    deferred_roles_present: list[str] = field(default_factory=list)
    deferred_roles_absent: list[str] = field(default_factory=list)
    not_allowed_roles_present: list[str] = field(default_factory=list)
    unknown_root_entries: list[str] = field(default_factory=list)
    incompatible_root_entries: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["schema"] = "r011.provisioning-result.v1"
        result["planned_role_count"] = len(self.planned_roles)
        return result


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _ACE_HEADER(ctypes.Structure):
    _fields_ = [
        ("AceType", wintypes.BYTE),
        ("AceFlags", wintypes.BYTE),
        ("AceSize", wintypes.WORD),
    ]


class _ACL_SIZE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("AceCount", wintypes.DWORD),
        ("AclBytesInUse", wintypes.DWORD),
        ("AclBytesFree", wintypes.DWORD),
    ]


class WindowsSecurityBackend:
    """Small Windows-native boundary for secure create and semantic readback."""

    FILE_ATTRIBUTE_DIRECTORY = 0x10
    FILE_ATTRIBUTE_REPARSE_POINT = 0x400
    INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
    SE_FILE_OBJECT = 1
    OWNER_SECURITY_INFORMATION = 0x00000001
    DACL_SECURITY_INFORMATION = 0x00000004
    SE_DACL_PROTECTED = 0x1000
    ACL_SIZE_INFORMATION_CLASS = 2

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows filesystem security is required")
        self.advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_api()

    def _configure_api(self) -> None:
        self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
        self.kernel32.CreateDirectoryW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(_SECURITY_ATTRIBUTES),
        ]
        self.kernel32.CreateDirectoryW.restype = wintypes.BOOL
        self.kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        self.kernel32.GetFileAttributesW.restype = wintypes.DWORD
        self.advapi.GetNamedSecurityInfoW.argtypes = [
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.LPVOID),
        ]
        self.advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
        self.advapi.GetSecurityDescriptorControl.argtypes = [
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.WORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.advapi.GetSecurityDescriptorControl.restype = wintypes.BOOL
        self.advapi.GetAclInformation.argtypes = [
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self.advapi.GetAclInformation.restype = wintypes.BOOL
        self.advapi.GetAce.argtypes = [
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPVOID),
        ]
        self.advapi.GetAce.restype = wintypes.BOOL
        self.advapi.ConvertSidToStringSidW.argtypes = [
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        self.advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
        self.advapi.LookupAccountNameW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPVOID,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.advapi.LookupAccountNameW.restype = wintypes.BOOL
        self.kernel32.LocalFree.argtypes = [wintypes.LPVOID]
        self.kernel32.LocalFree.restype = wintypes.LPVOID

    @staticmethod
    def _raise_last_error(action: str) -> None:
        error = ctypes.get_last_error()
        raise SecurityInspectionError(error, f"{action}: {ctypes.FormatError(error)}")

    def _sid_to_string(self, sid_pointer: int | wintypes.LPVOID) -> str:
        output = wintypes.LPWSTR()
        pointer = wintypes.LPVOID(sid_pointer) if isinstance(sid_pointer, int) else sid_pointer
        if not self.advapi.ConvertSidToStringSidW(pointer, ctypes.byref(output)):
            self._raise_last_error("ConvertSidToStringSidW")
        try:
            return output.value
        finally:
            self.kernel32.LocalFree(ctypes.cast(output, wintypes.LPVOID))

    def resolve_account_sid(self, account: str) -> str:
        sid_size = wintypes.DWORD(0)
        domain_size = wintypes.DWORD(0)
        sid_type = wintypes.DWORD(0)
        self.advapi.LookupAccountNameW(
            None,
            account,
            None,
            ctypes.byref(sid_size),
            None,
            ctypes.byref(domain_size),
            ctypes.byref(sid_type),
        )
        if sid_size.value == 0:
            self._raise_last_error(f"LookupAccountNameW({account})")
        sid = ctypes.create_string_buffer(sid_size.value)
        domain = ctypes.create_unicode_buffer(max(domain_size.value, 1))
        if not self.advapi.LookupAccountNameW(
            None,
            account,
            sid,
            ctypes.byref(sid_size),
            domain,
            ctypes.byref(domain_size),
            ctypes.byref(sid_type),
        ):
            self._raise_last_error(f"LookupAccountNameW({account})")
        return self._sid_to_string(ctypes.addressof(sid))

    def attributes(self, path: Path) -> int:
        attributes = self.kernel32.GetFileAttributesW(str(path))
        if attributes == self.INVALID_FILE_ATTRIBUTES:
            self._raise_last_error(f"GetFileAttributesW({path})")
        return int(attributes)

    def is_reparse_point(self, path: Path) -> bool:
        return bool(self.attributes(path) & self.FILE_ATTRIBUTE_REPARSE_POINT)

    def is_directory(self, path: Path) -> bool:
        return bool(self.attributes(path) & self.FILE_ATTRIBUTE_DIRECTORY)

    def create_secure_directory(self, path: Path, policy: SecurityPolicy) -> None:
        descriptor = wintypes.LPVOID()
        descriptor_size = wintypes.DWORD(0)
        if not self.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            policy.sddl,
            1,
            ctypes.byref(descriptor),
            ctypes.byref(descriptor_size),
        ):
            self._raise_last_error("ConvertStringSecurityDescriptorToSecurityDescriptorW")
        try:
            attributes = _SECURITY_ATTRIBUTES(
                ctypes.sizeof(_SECURITY_ATTRIBUTES), descriptor, False
            )
            if not self.kernel32.CreateDirectoryW(str(path), ctypes.byref(attributes)):
                self._raise_last_error(f"CreateDirectoryW({path})")
        finally:
            self.kernel32.LocalFree(descriptor)

    def inspect_security(self, path: Path) -> SecuritySnapshot:
        owner = wintypes.LPVOID()
        dacl = wintypes.LPVOID()
        descriptor = wintypes.LPVOID()
        status = self.advapi.GetNamedSecurityInfoW(
            str(path),
            self.SE_FILE_OBJECT,
            self.OWNER_SECURITY_INFORMATION | self.DACL_SECURITY_INFORMATION,
            ctypes.byref(owner),
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        )
        if status != 0:
            raise SecurityInspectionError(
                int(status), f"GetNamedSecurityInfoW({path}) failed with {status}"
            )
        try:
            control = wintypes.WORD(0)
            revision = wintypes.DWORD(0)
            if not self.advapi.GetSecurityDescriptorControl(
                descriptor, ctypes.byref(control), ctypes.byref(revision)
            ):
                self._raise_last_error("GetSecurityDescriptorControl")
            if not dacl:
                raise SecurityInspectionError("a null DACL is forbidden")
            size = _ACL_SIZE_INFORMATION()
            if not self.advapi.GetAclInformation(
                dacl,
                ctypes.byref(size),
                ctypes.sizeof(size),
                self.ACL_SIZE_INFORMATION_CLASS,
            ):
                self._raise_last_error("GetAclInformation")
            aces: list[AceSpec] = []
            for index in range(size.AceCount):
                ace_pointer = wintypes.LPVOID()
                if not self.advapi.GetAce(dacl, index, ctypes.byref(ace_pointer)):
                    self._raise_last_error(f"GetAce({index})")
                address = int(ace_pointer.value)
                header = _ACE_HEADER.from_address(address)
                mask = ctypes.c_uint32.from_address(address + 4).value
                sid = self._sid_to_string(address + 8)
                aces.append(AceSpec(sid, mask, int(header.AceFlags), int(header.AceType)))
            return SecuritySnapshot(
                owner_sid=self._sid_to_string(owner),
                protected=bool(control.value & self.SE_DACL_PROTECTED),
                aces=tuple(aces),
            )
        finally:
            self.kernel32.LocalFree(descriptor)


def _validate_roles(roles: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(roles)
    if not normalized:
        raise ProvisioningContractError("at least one approved role is required")
    if any(type(role) is not str for role in normalized):
        raise ProvisioningContractError("roles must be plain strings")
    if len(normalized) != len(set(normalized)):
        raise ProvisioningContractError("duplicate roles are forbidden")
    for role in normalized:
        spec = ROLE_SPECS.get(role)
        classification = spec.classification if spec is not None else "UNKNOWN"
        if classification != "REQUIRED_NOW":
            raise ProvisioningContractError(
                f"role '{role}' has classification {classification}; only REQUIRED_NOW roles "
                "may be requested in the current provisioning stage"
            )
        if Path(role).name != role or any(token in role for token in ("/", "\\", "..", ":")):
            raise ProvisioningContractError(f"role is not a direct child name: {role}")
    return normalized


def directory_model() -> dict[str, list[str]]:
    return {
        "REQUIRED_NOW": list(REQUIRED_NOW),
        "REQUIRED_LATER": list(REQUIRED_LATER),
        "NOT_REQUIRED": list(NOT_REQUIRED),
    }


def _recovery_aces(administrator_sid: str, *, flags: int) -> list[AceSpec]:
    return [
        AceSpec(SYSTEM_SID, FILE_ALL_ACCESS, flags),
        AceSpec(administrator_sid, FILE_ALL_ACCESS, flags),
    ]


def _role_security_policy(
    role: str,
    *,
    service_sid: str,
    administrator_sid: str,
    owner_sid: str,
) -> SecurityPolicy:
    """Derive a role's exact policy from the single ROLE_SPECS contract."""

    spec = ROLE_SPECS[role]
    aces = _recovery_aces(administrator_sid, flags=OBJECT_AND_CONTAINER_INHERIT)
    if spec.service_access_mask is not None:
        aces.append(AceSpec(service_sid, spec.service_access_mask))
    return SecurityPolicy(owner_sid, tuple(aces))


def _canonical_target_root(target_root: str | Path) -> Path:
    """Apply the builder's local-drive/no-UNC/no-traversal target contract."""

    try:
        raw = Path(target_root)
    except (TypeError, ValueError) as exc:
        raise ProvisioningContractError("target root must be a filesystem path") from exc
    if ".." in raw.parts:
        raise ProvisioningContractError("target root traversal is forbidden")
    target = Path(os.path.abspath(os.fspath(raw)))
    if not target.is_absolute() or not target.drive or str(target).startswith("\\\\"):
        raise ProvisioningContractError("target root must be an absolute local-drive path")
    return target


def _canonical_sid(value: object, field: str) -> str:
    if type(value) is not str or not value.startswith("S-1-"):
        raise ProvisioningContractError(f"{field} must be a SID string")
    if value in BROAD_PRINCIPAL_SIDS:
        raise ProvisioningContractError(f"{field} must not be a broad principal")
    return value


def _policy_value(policy: object, field: str) -> tuple[str, bool, tuple[tuple[str, int, int, int], ...]]:
    """Read exact immutable policy primitives without trusting user equality."""

    if type(policy) is not SecurityPolicy:
        raise ProvisioningContractError(f"{field} must be an exact SecurityPolicy")
    owner = _canonical_sid(policy.owner_sid, f"{field} owner")
    if type(policy.protected) is not bool:
        raise ProvisioningContractError(f"{field} protected flag must be a bool")
    if type(policy.aces) is not tuple:
        raise ProvisioningContractError(f"{field} ACEs must use immutable tuple storage")
    aces: list[tuple[str, int, int, int]] = []
    for ace in policy.aces:
        if type(ace) is not AceSpec:
            raise ProvisioningContractError(f"{field} must contain exact AceSpec values")
        sid = _canonical_sid(ace.sid, f"{field} ACE SID")
        if type(ace.access_mask) is not int or not 0 <= ace.access_mask <= 0xFFFFFFFF:
            raise ProvisioningContractError(f"{field} ACE access mask is invalid")
        if type(ace.flags) is not int or ace.flags not in {0, OBJECT_AND_CONTAINER_INHERIT}:
            raise ProvisioningContractError(f"{field} ACE flags are invalid")
        if type(ace.ace_type) is not int or ace.ace_type != 0:
            raise ProvisioningContractError(f"{field} ACE type is invalid")
        aces.append((sid, ace.access_mask, ace.flags, ace.ace_type))
    return owner, policy.protected, tuple(aces)


def _root_security_policy(
    *,
    service_sid: str,
    administrator_sid: str,
    owner_sid: str,
) -> SecurityPolicy:
    """Derive the target-root policy from the reviewed identity contract."""

    aces = _recovery_aces(administrator_sid, flags=0)
    aces.append(AceSpec(service_sid, FILE_GENERIC_EXECUTE, 0))
    return SecurityPolicy(owner_sid, tuple(aces))


def _validate_plan_state(
    plan: ProvisioningPlan,
    *,
    require_canonical_storage: bool = False,
) -> tuple[Path, tuple[str, ...], str, SecurityPolicy, dict[str, SecurityPolicy]]:
    """Validate a plan solely against the canonical role-policy contract."""

    target = _canonical_target_root(plan.target_root)
    if not isinstance(plan.role_policies, Mapping):
        raise ProvisioningContractError("role policies must be a mapping")

    roles = _validate_roles(plan.roles)
    policies = dict(plan.role_policies)
    if set(policies) != set(roles):
        raise ProvisioningContractError("role policy set must match planned roles exactly")

    service_sid = _canonical_sid(plan.service_sid, "service SID")
    administrator_sid = _canonical_sid(plan.administrator_sid, "administrator SID")
    owner = administrator_sid if plan.owner_sid is None else _canonical_sid(plan.owner_sid, "owner SID")
    expected_root_policy = _root_security_policy(
        service_sid=service_sid,
        administrator_sid=administrator_sid,
        owner_sid=owner,
    )
    if _policy_value(plan.root_policy, "root policy") != _policy_value(
        expected_root_policy, "canonical root policy"
    ):
        raise ProvisioningContractError("root policy must match the canonical identity contract")

    canonical_policies: dict[str, SecurityPolicy] = {}
    for role in roles:
        expected_policy = _role_security_policy(
            role,
            service_sid=service_sid,
            administrator_sid=administrator_sid,
            owner_sid=owner,
        )
        if _policy_value(policies[role], f"role policy for '{role}'") != _policy_value(
            expected_policy, f"canonical role policy for '{role}'"
        ):
            raise ProvisioningContractError(
                f"role policy for '{role}' must match ROLE_SPECS and the canonical identity contract"
            )
        canonical_policies[role] = expected_policy

    if require_canonical_storage:
        if not isinstance(plan.roles, tuple) or plan.roles != roles:
            raise ProvisioningContractError("plan roles must use canonical immutable storage")
        if not isinstance(plan.role_policies, MappingProxyType):
            raise ProvisioningContractError(
                "plan role policies must use read-only canonical storage"
            )
    return target, roles, owner, expected_root_policy, canonical_policies


def _effective_plan_at_mutation_boundary(plan: ProvisioningPlan) -> ProvisioningPlan:
    """Revalidate and snapshot the effective plan before namespace inspection."""

    target, roles, owner, root_policy, policies = _validate_plan_state(
        plan, require_canonical_storage=True
    )
    return ProvisioningPlan(
        target_root=target,
        roles=roles,
        service_sid=plan.service_sid,
        administrator_sid=plan.administrator_sid,
        root_policy=root_policy,
        role_policies=policies,
        owner_sid=owner,
        production_binding=plan.production_binding,
    )


def build_provisioning_plan(
    target_root: str | Path,
    *,
    service_sid: str,
    roles: Iterable[str] = REQUIRED_NOW,
    administrator_sid: str = ADMINISTRATORS_SID,
    owner_sid: str | None = None,
    production_binding: bool = False,
) -> ProvisioningPlan:
    target = _canonical_target_root(target_root)
    planned_roles = _validate_roles(roles)
    owner = owner_sid or administrator_sid
    root_policy = _root_security_policy(
        service_sid=service_sid,
        administrator_sid=administrator_sid,
        owner_sid=owner,
    )
    policies: dict[str, SecurityPolicy] = {}
    for role in planned_roles:
        policies[role] = _role_security_policy(
            role,
            service_sid=service_sid,
            administrator_sid=administrator_sid,
            owner_sid=owner,
        )
    return ProvisioningPlan(
        target_root=target,
        roles=planned_roles,
        service_sid=service_sid,
        administrator_sid=administrator_sid,
        root_policy=root_policy,
        role_policies=policies,
        owner_sid=owner,
        production_binding=production_binding,
    )


def _path_exists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _path_chain(target: Path) -> list[Path]:
    current = Path(target.anchor)
    chain = [current]
    for part in target.parts[1:]:
        current = current / part
        chain.append(current)
    return chain


def _existing_role_incompatibility(
    path: Path, policy: SecurityPolicy, backend: WindowsSecurityBackend
) -> tuple[str | None, bool]:
    """Return an incompatibility reason and whether the entry is a reparse point."""

    try:
        if backend.is_reparse_point(path):
            return "reparse point", True
        if not backend.is_directory(path):
            return "not a directory", False
        snapshot = backend.inspect_security(path)
        if not snapshot.matches(policy):
            return "security policy mismatch", False
        return None, False
    except (OSError, ProvisioningContractError) as exc:
        # Preserve full inventory coverage if one child cannot be inspected.
        return f"security inspection failed: {exc}", False


def _preflight(
    plan: ProvisioningPlan, backend: WindowsSecurityBackend
) -> tuple[
    list[str],
    list[str],
    list[dict[str, str]],
    str | None,
    list[str],
    list[dict[str, str]],
    list[str],
    list[str],
    list[str],
    list[str],
    list[str],
]:
    missing: list[str] = []
    correct: list[str] = []
    collisions: list[dict[str, str]] = []
    errors: list[str] = []
    reparse: str | None = None
    root_entries: list[dict[str, str]] = []
    deferred_present: list[str] = []
    deferred_absent: list[str] = []
    not_allowed_present: list[str] = []
    unknown_entries: list[str] = []
    incompatible_entries: list[str] = []

    try:
        for path in _path_chain(plan.target_root):
            if _path_exists(path) and backend.is_reparse_point(path):
                reparse = str(path)
                raise ProvisioningContractError(f"unsafe reparse path: {path}")
        if not _path_exists(plan.target_root):
            raise ProvisioningContractError("target root must already exist")
        if not backend.is_directory(plan.target_root):
            raise ProvisioningContractError("target root is not a directory")
        root_snapshot = backend.inspect_security(plan.target_root)
        if not root_snapshot.matches(plan.root_policy):
            raise ProvisioningContractError(
                "target root owner/DACL does not match the reviewed precondition"
            )
        entries = {entry.name: entry for entry in plan.target_root.iterdir()}
        deferred_absent = [role for role in REQUIRED_LATER if role not in entries]
        for name, entry in entries.items():
            spec = ROLE_SPECS.get(name)
            if spec is None:
                root_entries.append(
                    {
                        "path": str(entry),
                        "classification": "UNKNOWN_ENTRY",
                        "status": "UNKNOWN_ENTRY_PRESENT",
                    }
                )
                unknown_entries.append(name)
                incompatible_entries.append(name)
                collisions.append(
                    {"path": str(entry), "reason": "unexpected root entry"}
                )
                continue
            if name in plan.roles:
                reason, is_reparse = _existing_role_incompatibility(
                    entry, plan.role_policies[name], backend
                )
                status = "ALREADY_CORRECT" if reason is None else "INCOMPATIBLE"
                root_entries.append(
                    {
                        "path": str(entry),
                        "classification": "REQUESTED_ROLE",
                        "status": status,
                    }
                )
                if reason is None:
                    correct.append(name)
                else:
                    if is_reparse:
                        reparse = str(entry)
                    collisions.append({"path": str(entry), "reason": reason})
                    incompatible_entries.append(name)
                continue
            if spec.classification == "REQUIRED_LATER":
                deferred_present.append(name)
                policy = _role_security_policy(
                    name,
                    service_sid=plan.service_sid,
                    administrator_sid=plan.administrator_sid,
                    owner_sid=plan.root_policy.owner_sid,
                )
                reason, is_reparse = _existing_role_incompatibility(entry, policy, backend)
                status = "DEFERRED_PRESENT_EXACT" if reason is None else "INCOMPATIBLE"
                root_entries.append(
                    {
                        "path": str(entry),
                        "classification": "DEFERRED_ROLE",
                        "status": status,
                    }
                )
                if reason is not None:
                    if is_reparse:
                        reparse = str(entry)
                    collisions.append({"path": str(entry), "reason": reason})
                    incompatible_entries.append(name)
                continue
            # A catalog name alone is never authority to retain an unplanned root entry.
            root_entries.append(
                {
                    "path": str(entry),
                    "classification": "NOT_ALLOWED_ROLE",
                    "status": "NOT_ALLOWED_ROLE_PRESENT",
                }
            )
            not_allowed_present.append(name)
            incompatible_entries.append(name)
            collisions.append({"path": str(entry), "reason": "not allowed root role"})
        if collisions:
            raise ProvisioningContractError("root namespace contains incompatible entries")
        for role in plan.roles:
            if role not in entries:
                missing.append(role)
                root_entries.append(
                    {
                        "path": str(plan.target_root / role),
                        "classification": "REQUESTED_ROLE",
                        "status": "PLANNED_CREATE",
                    }
                )
    except (OSError, ProvisioningContractError) as exc:
        errors.append(str(exc))
    return (
        missing,
        correct,
        collisions,
        reparse,
        errors,
        root_entries,
        deferred_present,
        deferred_absent,
        not_allowed_present,
        unknown_entries,
        incompatible_entries,
    )


def provision(
    plan: ProvisioningPlan,
    *,
    dry_run: bool = True,
    backend: WindowsSecurityBackend | None = None,
) -> ProvisioningResult:
    """Inspect or converge approved roles without deleting or weakening state."""

    try:
        effective_plan = _effective_plan_at_mutation_boundary(plan)
    except (AttributeError, ProvisioningContractError, TypeError) as exc:
        return ProvisioningResult(
            overall_status="FAILED",
            target_root=str(getattr(plan, "target_root", "")),
            planned_roles=[],
            security_verification_status="FAIL",
            root_namespace_status="NOT_RUN",
            errors=[str(exc)],
            dry_run=dry_run,
        )

    security = backend or WindowsSecurityBackend()
    (
        missing,
        correct,
        collisions,
        reparse,
        errors,
        root_entries,
        deferred_present,
        deferred_absent,
        not_allowed_present,
        unknown_entries,
        incompatible_entries,
    ) = _preflight(effective_plan, security)
    result = ProvisioningResult(
        overall_status="DRY_RUN" if dry_run else "PENDING",
        target_root=str(effective_plan.target_root),
        planned_roles=list(effective_plan.roles),
        already_correct_roles=correct,
        collision_information=collisions,
        reparse_rejection=reparse,
        security_verification_status="PASS" if not errors else "FAIL",
        security_changes_required=list(missing),
        root_namespace_status="PASS" if not errors else "FAIL",
        root_entries_inspected=root_entries,
        deferred_roles_present=deferred_present,
        deferred_roles_absent=deferred_absent,
        not_allowed_roles_present=not_allowed_present,
        unknown_root_entries=unknown_entries,
        incompatible_root_entries=incompatible_entries,
        errors=errors,
        dry_run=dry_run,
    )
    if errors:
        result.overall_status = "FAILED"
        collision_roles = {
            Path(item["path"]).name
            for item in collisions
            if Path(item["path"]).name in effective_plan.roles
        }
        result.failed_role = next(
            (role for role in effective_plan.roles if role in collision_roles), None
        )
        return result
    if dry_run:
        return result
    if not missing:
        result.overall_status = "ALREADY_CORRECT"
        result.security_verification_status = "PASS"
        return result

    for role in effective_plan.roles:
        if role not in missing:
            continue
        path = effective_plan.target_root / role
        try:
            # CreateDirectoryW receives the protected DACL in SECURITY_ATTRIBUTES,
            # so sensitive roles never persist with inherited broad permissions.
            security.create_secure_directory(path, effective_plan.role_policies[role])
            result.mutation_count += 1
            snapshot = security.inspect_security(path)
            if not snapshot.matches(effective_plan.role_policies[role]):
                raise SecurityInspectionError(
                    f"security verification failed immediately after creating {path}"
                )
            result.created_roles.append(role)
        except (OSError, ProvisioningContractError) as exc:
            result.overall_status = "PARTIAL_FAILURE"
            result.failed_role = role
            result.partial_state_status = "PRESERVED_CREATED_ROLES"
            result.security_verification_status = "FAIL"
            result.errors.append(str(exc))
            return result

    result.overall_status = "APPLIED"
    result.partial_state_status = "NONE"
    result.security_verification_status = "PASS"
    result.security_changes_required = []
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply the reviewed HMS QR child-role provisioner."
    )
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--service-account", default=r"HMS-PC\HMSQRService")
    parser.add_argument("--roles", nargs="+", default=list(REQUIRED_NOW))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Mutate approved child roles; requires separate production authority.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    backend = WindowsSecurityBackend()
    service_sid = backend.resolve_account_sid(args.service_account)
    plan = build_provisioning_plan(
        args.target_root,
        service_sid=service_sid,
        roles=args.roles,
        production_binding=True,
    )
    result = provision(plan, dry_run=not args.apply, backend=backend)
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.overall_status not in {"FAILED", "PARTIAL_FAILURE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ADMINISTRATORS_SID",
    "BROAD_PRINCIPAL_SIDS",
    "NOT_REQUIRED",
    "ProvisioningContractError",
    "ProvisioningPlan",
    "ProvisioningResult",
    "REQUIRED_LATER",
    "REQUIRED_NOW",
    "ROLE_SPECS",
    "SecurityPolicy",
    "SecuritySnapshot",
    "WindowsSecurityBackend",
    "build_provisioning_plan",
    "directory_model",
    "main",
    "provision",
]
