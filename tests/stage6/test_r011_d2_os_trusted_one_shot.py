"""Non-elevated qualification for the bounded R011 D2 deployment procedure."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import zipfile

import pytest
from packages.deployment import os_trusted_one_shot as d2
from packages.deployment.provisioning import (
    ADMINISTRATORS_SID,
    SecuritySnapshot,
    build_provisioning_plan,
    provision,
)

from packages.deployment.os_trusted_one_shot import (
    COMMAND_LINE_SAFETY_LIMIT,
    D2Authority,
    D2ContractError,
    RUNTIME_ARCHIVE_SHA256,
    RUNTIME_ARCHIVE_SIZE,
    build_deployment_bundle,
    build_powershell_command,
    encode_stage0,
    exact_provisioner_argv,
    resolve_native_powershell,
    safe_extract_zip,
    sha256_file,
    verify_exact_files,
)


ROOT = Path(__file__).resolve().parents[2]
STAGE0 = ROOT / "scripts" / "r011_d2_stage0.ps1"
PAYLOAD = ROOT / "scripts" / "r011_d2_protected_payload.ps1"
RUNTIME_ARCHIVE = Path(r"F:\HMS-QR-DEV-R1F-TEST\r011-b2b-private-python-runtime-20260823T000000Z-a7d4f6c2\python-3.14.6-embed-amd64.zip")


@pytest.fixture()
def authority(tmp_path: Path) -> D2Authority:
    bundle = tmp_path / "bundle.zip"
    build_deployment_bundle(ROOT, bundle)
    return D2Authority(
        authority_id="R011_OS_TRUSTED_ONE_SHOT_DEPLOYMENT_IMPLEMENTATION",
        attempt_id="d2-test-attempt-001",
        created_utc="2026-08-23T00:00:00Z",
        expires_utc="2099-08-23T00:00:00Z",
        machine_name="HMS-PC",
        target_root=r"D:\HMS-QR-PROD",
        payload_source=str(PAYLOAD),
        payload_sha256=sha256_file(PAYLOAD),
        runtime_archive=str(RUNTIME_ARCHIVE),
        runtime_sha256=RUNTIME_ARCHIVE_SHA256,
        bundle_source=str(bundle),
        bundle_sha256=sha256_file(bundle),
    )


def _zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return path


def _private_runtime(tmp_path: Path) -> tuple[Path, Path]:
    runtime = tmp_path / "private-runtime"
    safe_extract_zip(RUNTIME_ARCHIVE, runtime)
    app = runtime / "app"
    bundle = tmp_path / "deployment-bundle.zip"
    build_deployment_bundle(ROOT, bundle)
    safe_extract_zip(bundle, app)
    (runtime / "python314._pth").write_text(".\npython314.zip\napp\n", encoding="utf-8", newline="\n")
    return runtime / "python.exe", runtime


def test_d2_01_native_system32_powershell_detected() -> None:
    executable = resolve_native_powershell()
    assert executable.is_absolute() and executable.is_file()
    assert "\\system32\\" in str(executable).casefold()


def test_d2_02_path_cannot_alter_powershell_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(Path.home() / "malicious-bin"))
    assert resolve_native_powershell().name.casefold() == "powershell.exe"
    monkeypatch.setattr(d2.ctypes, "sizeof", lambda _: 4)
    with pytest.raises(D2ContractError, match="WOW64"):
        resolve_native_powershell()


def test_d2_03_no_mutable_file_first_stage_handoff() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert not re.search(r"(?:^|\s)-File(?:\s|$)", source)
    assert "& $payload" in source


def test_d2_04_stage0_encoded_command_deterministic(authority: D2Authority) -> None:
    assert build_powershell_command(authority, STAGE0) == build_powershell_command(authority, STAGE0)


def test_d2_05_command_length_checked_before_elevation_request(authority: D2Authority, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, metadata = build_powershell_command(authority, STAGE0)
    assert metadata["command_line_length"] < COMMAND_LINE_SAFETY_LIMIT
    monkeypatch.setattr(d2, "COMMAND_LINE_SAFETY_LIMIT", 1)
    with pytest.raises(D2ContractError, match="safety limit"):
        build_powershell_command(authority, STAGE0)


def test_d2_06_no_profile_is_bound(authority: D2Authority) -> None:
    _, args, _ = build_powershell_command(authority, STAGE0)
    assert args[0] == "-NoProfile"


def test_d2_07_noninteractive_is_bound(authority: D2Authority) -> None:
    _, args, _ = build_powershell_command(authority, STAGE0)
    assert args[1] == "-NonInteractive"


def test_d2_08_module_autoload_is_disabled(authority: D2Authority) -> None:
    _, args, _ = build_powershell_command(authority, STAGE0)
    source = STAGE0.read_text(encoding="utf-8")
    assert args[2] == "-NoLogo"
    assert args[3] == "-EncodedCommand"
    assert "$PSModuleAutoLoadingPreference = 'None'" in source


def _bound_stage0_source(authority: D2Authority) -> str:
    _, args, _ = build_powershell_command(authority, STAGE0)
    return __import__("base64").b64decode(args[-1]).decode("utf-16le")


def test_d2_09_attempt_id_is_literal_binding(authority: D2Authority) -> None:
    assert authority.attempt_id in _bound_stage0_source(authority)
    with pytest.raises(D2ContractError, match="simple token"):
        authority.__class__(**{**authority.__dict__, "attempt_id": "../unsafe"})
    for field, value in (("authority_id", "OTHER"), ("machine_name", "OTHER-PC"), ("target_root", r"D:\other"), ("service_account", r"HMS-PC\Other"), ("service_sid", "S-1-5-21-1")):
        with pytest.raises(D2ContractError):
            authority.__class__(**{**authority.__dict__, field: value})


def test_d2_10_deadline_is_literal_binding(authority: D2Authority) -> None:
    assert authority.expires_utc in _bound_stage0_source(authority)
    with pytest.raises(D2ContractError, match="ordered UTC"):
        authority.__class__(**{**authority.__dict__, "expires_utc": authority.created_utc})


def test_d2_11_expired_stage0_has_apply_zero_contract() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert source.index("authority expired") < source.index("Ensure-AdminOnlyDirectory $stagingRoot")
    assert "--apply" not in source


def test_d2_12_wrong_machine_has_apply_zero_contract() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert source.index("Machine identity") < source.index("Ensure-AdminOnlyDirectory $stagingRoot")


def test_d2_13_wrong_production_target_has_apply_zero_contract() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert source.index("Production target prestate") < source.index("Ensure-AdminOnlyDirectory $stagingRoot")


def test_d2_14_wrong_payload_hash_prevents_payload_execution() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert source.index("[IO.File]::Copy") < source.index("Get-Sha256 $destination") < source.index("& $payload")


def test_d2_15_source_mutation_cannot_bypass_protected_copy_hash(tmp_path: Path) -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert "[IO.File]::Copy($source, $destination, $false)" in source
    assert "Get-Sha256 $destination" in source
    original = b"frozen-original-bytes"
    staging = tmp_path
    mutable = staging / "mutable-payload.ps1"
    protected = staging / "protected-payload.ps1"
    marker = staging / "payload-executed.marker"
    mutable.write_bytes(original)
    expected = hashlib.sha256(original).hexdigest()
    mutable.write_bytes(b"mutated-before-elevation")
    command = (
        "$ErrorActionPreference='Stop';$PSModuleAutoLoadingPreference='None';"
        "function Get-Sha256([string]$p){$s=[IO.File]::OpenRead($p);$h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash($s))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose();$s.Dispose()}};"
        f"$source='{mutable}';$destination='{protected}';$expected='{expected}';$marker='{marker}';"
        "[IO.File]::Copy($source,$destination,$false);if((Get-Sha256 $destination) -ine $expected){[Console]::WriteLine('HASH_MISMATCH');exit 42};[IO.File]::WriteAllText($marker,'EXECUTED')"
    )
    run = subprocess.run([str(resolve_native_powershell()), "-NoProfile", "-NonInteractive", "-NoLogo", "-EncodedCommand", encode_stage0(command)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 42 and run.stdout.strip() == "HASH_MISMATCH"
    assert protected.read_bytes() == b"mutated-before-elevation" and not marker.exists()


def test_d2_16_protected_payload_exact_hash_is_required() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert "Hash mismatch" in source and "-ProtectedPayloadPath $payload" in source


def test_d2_17_runtime_archive_hash_is_frozen_and_rehashed(authority: D2Authority) -> None:
    assert RUNTIME_ARCHIVE.stat().st_size == RUNTIME_ARCHIVE_SIZE
    assert sha256_file(RUNTIME_ARCHIVE) == RUNTIME_ARCHIVE_SHA256
    with pytest.raises(D2ContractError, match="pre-UAC payload hash"):
        build_powershell_command(authority.__class__(**{**authority.__dict__, "payload_sha256": "0" * 64}), STAGE0)
    with pytest.raises(D2ContractError, match="frozen CPython"):
        authority.__class__(**{**authority.__dict__, "runtime_sha256": "0" * 64})


def test_d2_18_unsafe_zip_traversal_and_links_are_rejected(tmp_path: Path) -> None:
    for name in ("../escape.txt", "/absolute.txt", "C:/absolute.txt"):
        with pytest.raises(D2ContractError):
            safe_extract_zip(_zip(tmp_path / (hashlib.sha256(name.encode()).hexdigest() + ".zip"), {name: b"no"}), tmp_path / "out")
    for mode in (stat.S_IFLNK | 0o777, stat.S_IFCHR | 0o600):
        special = tmp_path / f"special-{mode}.zip"
        info = zipfile.ZipInfo("special")
        info.external_attr = mode << 16
        with zipfile.ZipFile(special, "w") as archive:
            archive.writestr(info, b"target")
        with pytest.raises(D2ContractError):
            safe_extract_zip(special, tmp_path / f"special-{mode}-out")
    hostile = _zip(tmp_path / "payload-hostile.zip", {"../escape.txt": b"no"})
    command = (
        "$ErrorActionPreference='Stop';$PSModuleAutoLoadingPreference='None';"
        "$f=[IO.Path]::Combine([Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory(),'System.IO.Compression.FileSystem.dll');[void][Reflection.Assembly]::LoadFrom($f);"
        f"$z=[IO.Compression.ZipFile]::OpenRead('{hostile}');try{{$e=$z.Entries[0];$n=$e.FullName;if($n -match '(^|/|\\\\)\\.\\.($|/|\\\\)'){{throw 'unsafe'}}}}catch{{[Console]::WriteLine('SAFE_ZIP_REJECT');exit 0}}finally{{$z.Dispose()}};exit 2"
    )
    run = subprocess.run([str(resolve_native_powershell()), "-NoProfile", "-NonInteractive", "-NoLogo", "-EncodedCommand", encode_stage0(command)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0 and run.stdout.strip() == "SAFE_ZIP_REJECT"


def test_d2_19_private_runtime_ctypes_black_box(tmp_path: Path) -> None:
    python, runtime = _private_runtime(tmp_path)
    run = subprocess.run([str(python), "-B", "-c", "import _ctypes;print('CTYPES_OK')"], cwd=runtime, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "CTYPES_OK"


def test_d2_20_private_provisioner_dependency_import_black_box(tmp_path: Path) -> None:
    python, runtime = _private_runtime(tmp_path)
    run = subprocess.run([str(python), "-B", "-m", "packages.deployment.provisioning", "--help"], cwd=runtime, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert "--target-root" in run.stdout and "--apply" in run.stdout


def _hostile_private_run(tmp_path: Path) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    python, runtime = _private_runtime(tmp_path)
    hostile = tmp_path / "hostile"
    (hostile / "packages" / "deployment").mkdir(parents=True)
    (hostile / "packages" / "deployment" / "provisioning.py").write_text("raise RuntimeError('injected')", encoding="utf-8")
    env = {"PATH": str(hostile), "PYTHONPATH": str(hostile), "PYTHONHOME": str(hostile), "PYTHONDONTWRITEBYTECODE": "1"}
    run = subprocess.run([str(python), "-B", "-c", "import json,sys,_ctypes,packages.deployment.provisioning as p;print(json.dumps({'executable':sys.executable,'module':p.__file__,'path':sys.path}))"], cwd=runtime, env=env, capture_output=True, text=True, timeout=30)
    return run, python, runtime


def test_d2_21_hostile_pythonpath_cannot_inject_application_code(tmp_path: Path) -> None:
    run, _, runtime = _hostile_private_run(tmp_path)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert str(runtime / "app").casefold() in result["module"].casefold()
    allowed = {str(runtime.resolve()).casefold(), str((runtime / "python314.zip").resolve()).casefold(), str((runtime / "app").resolve()).casefold()}
    assert {str(Path(item).resolve()).casefold() for item in result["path"]} <= allowed
    assert all("site-packages" not in item.casefold() and "hms-pcc" not in item.casefold() for item in result["path"])
    assert "import site" not in (runtime / "python314._pth").read_text(encoding="utf-8").casefold()


def test_d2_22_host_python_unavailable_private_runtime_still_works(tmp_path: Path) -> None:
    run, python, _ = _hostile_private_run(tmp_path)
    assert run.returncode == 0, run.stderr
    assert Path(json.loads(run.stdout)["executable"]).resolve() == python.resolve()


def test_d2_23_unexpected_runtime_file_is_rejected(tmp_path: Path) -> None:
    _, runtime = _private_runtime(tmp_path)
    expected = {item.relative_to(runtime).as_posix(): sha256_file(item) for item in runtime.rglob("*") if item.is_file()}
    (runtime / "unexpected.dll").write_bytes(b"x")
    with pytest.raises(D2ContractError, match="exact extracted"):
        verify_exact_files(runtime, expected)


def test_d2_24_private_runtime_exact_file_set_is_verified(tmp_path: Path) -> None:
    _, runtime = _private_runtime(tmp_path)
    first = sorted(item.relative_to(runtime).as_posix() for item in runtime.rglob("*") if item.is_file())
    second = sorted(item.relative_to(runtime).as_posix() for item in runtime.rglob("*") if item.is_file())
    first_bundle = build_deployment_bundle(ROOT, tmp_path / "first.zip")
    second_bundle = build_deployment_bundle(ROOT, tmp_path / "second.zip")
    expected = {item.relative_to(runtime).as_posix(): sha256_file(item) for item in runtime.rglob("*") if item.is_file()}
    verify_exact_files(runtime, expected)
    (runtime / "python314._pth").write_text("tampered", encoding="utf-8")
    with pytest.raises(D2ContractError, match="exact extracted"):
        verify_exact_files(runtime, expected)
    assert first == second and "python.exe" in first and "app/packages/deployment/provisioning.py" in first
    assert first_bundle["files"] == second_bundle["files"] and first_bundle["sha256"] == second_bundle["sha256"]
    payload = PAYLOAD.read_text(encoding="utf-8")
    assert ".Replace([char]92, [char]47)" in payload
    command = "$r='C:\\d2-root';$f='C:\\d2-root\\app\\packages\\deployment\\provisioning.py';$v=$f.Substring($r.Length).TrimStart([char]92,[char]47).Replace([char]92,[char]47);if($v -ne 'app/packages/deployment/provisioning.py'){exit 2};[Console]::WriteLine('POSIX_RELATIVE_OK')"
    run = subprocess.run([str(resolve_native_powershell()), "-NoProfile", "-NonInteractive", "-NoLogo", "-EncodedCommand", encode_stage0(command)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0 and run.stdout.strip() == "POSIX_RELATIVE_OK"


def test_d2_25_runtime_acl_contract_is_deterministic() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    stage0 = STAGE0.read_text(encoding="utf-8")
    assert "O:BAD:PAI" in source and "Ensure-AdminOnlyDirectory $stagingRoot" in stage0 and "Ensure-AdminOnlyDirectory $attemptRoot" in stage0
    assert "GetAccessControl($path, 'Access,Owner')" in stage0 and "Assert-NoReparseAncestor $target" in stage0
    service_sid = "S-1-5-21-170807328-2858633000-3406472961-1009"
    root = f"O:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FX;;;{service_sid})"
    role = f"O:BAD:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;{service_sid})"
    stage = "O:BAD:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"
    command = (
        "$ErrorActionPreference='Stop';$PSModuleAutoLoadingPreference='None';"
        "$sections=[Security.AccessControl.AccessControlSections]::Owner -bor [Security.AccessControl.AccessControlSections]::Access;"
        f"$expected=@('{root}','{role}','{stage}');foreach($item in $expected){{$security=[Security.AccessControl.DirectorySecurity]::new();$security.SetSecurityDescriptorSddlForm($item);if($security.GetSecurityDescriptorSddlForm($sections) -ine $item){{exit 2}}}};[Console]::WriteLine('ACL_SDDL_ROUNDTRIP_OK')"
    )
    run = subprocess.run([str(resolve_native_powershell()), "-NoProfile", "-NonInteractive", "-NoLogo", "-EncodedCommand", encode_stage0(command)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0 and run.stdout.strip() == "ACL_SDDL_ROUNDTRIP_OK"


def test_d2_26_acl_readback_uses_dotnet_powershell_not_python_ctypes() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    assert "GetAccessControl" in source and "GetSecurityDescriptorSddlForm" in source
    assert "ctypes" not in source.casefold()


def test_d2_27_host_python_is_absent_from_elevated_trust_path() -> None:
    assert "python.exe" not in STAGE0.read_text(encoding="utf-8").casefold()
    assert "python.exe" in PAYLOAD.read_text(encoding="utf-8").casefold()


def test_d2_28_exact_private_python_provisioner_argv(authority: D2Authority) -> None:
    assert exact_provisioner_argv(authority) == (
        "-B", "-m", "packages.deployment.provisioning", "--target-root", r"D:\HMS-QR-PROD",
        "--service-account", r"HMS-PC\HMSQRService", "--roles", "releases", "runtime", "staging", "--apply",
    )


def test_d2_29_native_nonzero_is_terminal_no_retry() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    assert "process.ExitCode -ne 0" in source and "retry is forbidden" in source
    assert "ProcessStartInfo" in source and "UseShellExecute = $false" in source


def test_d2_30_poststate_mismatch_is_terminal_no_retry() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    assert source.rindex("Assert-PostState") > source.index("process.ExitCode -ne 0")
    assert source.count("$process.Start()") == 1
    assert "Assert-NoReparseAncestor $path" in source and "Assert-DeploymentAcl $path (Get-RoleSddl ([string]$Authority.service_sid) $role)" in source


def test_d2_31_duplicate_latch_is_denied_before_provisioner() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    stage0 = STAGE0.read_text(encoding="utf-8")
    assert source.rindex("Set-OneShotLatch") < source.index("$process.Start()")
    assert "FileMode]::CreateNew" in source
    assert "attempt.claim" in stage0
    lines = [line.strip() for line in stage0.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    claim_index = lines.index("Create-AttemptClaim $attemptRoot")
    copy_invocations = (
        "$payload = Copy-Verified ([string]$authority.payload_source)",
        "$runtime = Copy-Verified ([string]$authority.runtime_archive)",
        "$bundle = Copy-Verified ([string]$authority.bundle_source)",
    )
    for invocation in copy_invocations:
        matches = [index for index, line in enumerate(lines) if line.startswith(invocation)]
        assert len(matches) == 1
        assert claim_index < matches[0]


def test_d2_32_terminal_evidence_failure_does_not_restore_authority() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    assert source.count("$process.Start()") == 1
    assert "terminal-evidence.json" in source


def test_d2_33_normal_product_runtime_has_no_self_elevation_dependency() -> None:
    runtime_sources = list((ROOT / "apps").rglob("*.py")) + list((ROOT / "packages").rglob("*.py"))
    assert all("os_trusted_one_shot" not in item.read_text(encoding="utf-8") for item in runtime_sources if item != ROOT / "packages" / "deployment" / "os_trusted_one_shot.py")


def test_d2_34_custom_ipc_count_is_zero() -> None:
    text = (STAGE0.read_text(encoding="utf-8") + PAYLOAD.read_text(encoding="utf-8")).casefold()
    assert all(token not in text for token in ("namedpipe", "eventwait", "scheduledtask", "start-job", "start-threadjob"))


def test_d2_35_future_process_count_is_bounded_to_three() -> None:
    text = (STAGE0.read_text(encoding="utf-8") + PAYLOAD.read_text(encoding="utf-8")).casefold()
    assert "processstartinfo" in text and "start-process" not in text


def test_d2_36_actual_non_elevated_powershell_encoded_command_with_hostile_environment(tmp_path: Path) -> None:
    executable = resolve_native_powershell()
    encoded = encode_stage0("$ErrorActionPreference='Stop';$PSModuleAutoLoadingPreference='None';$h=[Security.Cryptography.SHA256]::Create();$b=[Text.Encoding]::UTF8.GetBytes('x');[void]$h.ComputeHash($b);$i=[Diagnostics.ProcessStartInfo]::new();$i.FileName=[Environment]::GetEnvironmentVariable('ComSpec');$i.Arguments='/d /c exit 7';$i.UseShellExecute=$false;$p=[Diagnostics.Process]::new();$p.StartInfo=$i;[void]$p.Start();$p.WaitForExit();if($p.ExitCode -ne 7){exit 2};[Console]::WriteLine('D2_BLACK_BOX_OK')")
    env = os.environ.copy()
    env.update({"PATH": str(tmp_path / "bad-path"), "PSModulePath": str(tmp_path / "bad-modules"), "PYTHONDONTWRITEBYTECODE": "1"})
    run = subprocess.run([str(executable), "-NoProfile", "-NonInteractive", "-NoLogo", "-EncodedCommand", encoded], env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "D2_BLACK_BOX_OK"
    forbidden = ("ConvertFrom-Json", "ConvertTo-Json", "Get-FileHash", "Add-Member", "Set-Content", "Start-Process", "Select-Object", "Where-Object")
    assert all(token.casefold() not in (STAGE0.read_text(encoding="utf-8") + PAYLOAD.read_text(encoding="utf-8")).casefold() for token in forbidden)


class _NamespacePreflightBackend:
    """ACL/reparse double; the immutable provisioner's root enumeration is real."""

    def __init__(self, policies: dict[Path, object]) -> None:
        self._policies = policies

    def is_reparse_point(self, path: Path) -> bool:
        return False

    def is_directory(self, path: Path) -> bool:
        return path.is_dir()

    def inspect_security(self, path: Path) -> SecuritySnapshot:
        policy = self._policies[path]
        return SecuritySnapshot(policy.owner_sid, policy.protected, policy.aces)


def _namespace_plan(root: Path):
    return build_provisioning_plan(
        root,
        service_sid=d2.SERVICE_SID,
        administrator_sid=ADMINISTRATORS_SID,
        owner_sid=ADMINISTRATORS_SID,
    )


def _d2_staging_preflight(
    tmp_path: Path, *, sibling: str | None = None, staging_child: str | None = None
):
    root = tmp_path / "root"
    root.mkdir()
    plan = _namespace_plan(root)
    namespace = root / "staging" / ".hms-qr-d2"
    (namespace / "current-attempt").mkdir(parents=True)
    if staging_child is not None:
        (root / "staging" / staging_child).mkdir()
    if sibling is not None:
        (root / sibling).mkdir()
    result = provision(
        plan,
        dry_run=True,
        backend=_NamespacePreflightBackend(
            {root: plan.root_policy, root / "staging": plan.role_policies["staging"]}
        ),
    )
    return root, plan, namespace, result


def test_ns01_selected_namespace_is_under_provisioner_staging_role() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert "[IO.Path]::Combine($target, 'staging')" in source
    assert "[IO.Path]::Combine($stagingRoot, '.hms-qr-d2')" in source


def test_ns02_recognized_direct_root_child(tmp_path: Path) -> None:
    _, _, _, result = _d2_staging_preflight(tmp_path)
    assert {entry["classification"] for entry in result.root_entries_inspected} == {"REQUESTED_ROLE"}


def test_ns03_no_unknown_entry_for_d2_namespace(tmp_path: Path) -> None:
    _, _, _, result = _d2_staging_preflight(tmp_path)
    assert result.unknown_root_entries == [] and result.overall_status == "DRY_RUN"


def test_ns04_unexpected_root_sibling_is_rejected(tmp_path: Path) -> None:
    _, _, _, result = _d2_staging_preflight(tmp_path, sibling="unexpected")
    assert result.overall_status == "FAILED" and result.unknown_root_entries == ["unexpected"]


def test_ns05_attempt_traversal_is_rejected(authority: D2Authority) -> None:
    for attempt_id in ("..", "a..b", "a/b", r"a\b"):
        with pytest.raises(D2ContractError):
            D2Authority(**{**authority.__dict__, "attempt_id": attempt_id})


def test_ns06_attempt_absolute_forms_are_rejected(authority: D2Authority) -> None:
    for attempt_id in (r"C:\attempt", r"\\server\share", r"\\?\C:\attempt"):
        with pytest.raises(D2ContractError):
            D2Authority(**{**authority.__dict__, "attempt_id": attempt_id})


def test_ns07_attempt_ads_is_rejected(authority: D2Authority) -> None:
    with pytest.raises(D2ContractError):
        D2Authority(**{**authority.__dict__, "attempt_id": "attempt:ads"})


def test_ns08_attempt_parent_confinement_is_explicit(authority: D2Authority) -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert "GetFullPath([IO.Path]::Combine($namespaceRoot" in source
    assert "Attempt path is not confined to D2 namespace" in source
    assert D2Authority(**{**authority.__dict__, "attempt_id": "A1._-z"}).attempt_id == "A1._-z"


def test_ns09_unrelated_staging_child_is_preserved(tmp_path: Path) -> None:
    root, _, namespace, result = _d2_staging_preflight(
        tmp_path, staging_child="other-administrator-child"
    )
    sibling = root / "staging" / "other-administrator-child"
    assert result.overall_status == "DRY_RUN" and namespace.is_dir() and sibling.is_dir()


def test_ns10_no_cleanup_beyond_current_attempt() -> None:
    source = STAGE0.read_text(encoding="utf-8") + PAYLOAD.read_text(encoding="utf-8")
    assert all(token not in source for token in ("Remove-Item", "DeleteDirectory", "Directory.Delete", "shutil.rmtree"))
    assert "attempt.claim" in source and "apply.latch" in source


def test_ns11_attempt_claim_is_under_approved_namespace() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert "[IO.Path]::Combine($attemptRoot, 'attempt.claim')" in source
    lines = [line.strip() for line in source.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    claim_index = lines.index("Create-AttemptClaim $attemptRoot")
    copy_invocations = (
        "$payload = Copy-Verified ([string]$authority.payload_source)",
        "$runtime = Copy-Verified ([string]$authority.runtime_archive)",
        "$bundle = Copy-Verified ([string]$authority.bundle_source)",
    )
    for invocation in copy_invocations:
        matches = [index for index, line in enumerate(lines) if line.startswith(invocation)]
        assert len(matches) == 1
        assert claim_index < matches[0]


def test_ns12_apply_latch_is_under_approved_namespace() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    assert "[IO.Path]::Combine($root, 'apply.latch')" in source
    assert "Set-OneShotLatch $StagingPath" in source


def test_ns13_terminal_receipt_is_under_approved_namespace() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    assert "[IO.Path]::Combine($StagingPath, 'terminal-evidence.json')" in source


def test_ns14_payload_is_copied_under_current_attempt() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert "Copy-Verified ([string]$authority.payload_source)" in source
    assert "([string]$authority.payload_sha256) $attemptRoot" in source


def test_ns15_runtime_bundle_and_app_remain_under_current_attempt() -> None:
    stage0 = STAGE0.read_text(encoding="utf-8")
    payload = PAYLOAD.read_text(encoding="utf-8")
    assert "([string]$authority.runtime_sha256) $attemptRoot" in stage0
    assert "([string]$authority.bundle_sha256) $attemptRoot" in stage0
    assert "[IO.Path]::Combine($StagingPath, 'runtime')" in payload
    assert "[IO.Path]::Combine($runtime, 'app')" in payload


def test_ns16_actual_immutable_provisioner_preflight_accepts_d2_staging(tmp_path: Path) -> None:
    _, _, _, result = _d2_staging_preflight(tmp_path)
    assert result.overall_status == "DRY_RUN" and result.unknown_root_entries == []


def test_ns17_actual_immutable_provisioner_preflight_rejects_root_deploy(tmp_path: Path) -> None:
    root = tmp_path / "old-root"
    root.mkdir()
    plan = _namespace_plan(root)
    (root / ".deploy").mkdir()
    result = provision(plan, dry_run=True, backend=_NamespacePreflightBackend({root: plan.root_policy}))
    assert result.overall_status == "FAILED" and result.unknown_root_entries == [".deploy"]


def test_ns18_provisioner_source_is_immutable() -> None:
    assert sha256_file(ROOT / "packages" / "deployment" / "provisioning.py") == "2caa09f70d30d151d488e2602272b1e993efae02ef26aa840c9f44e7c707cd2d"


def test_namespace_evidence_integrity_readback_and_sha_index(tmp_path: Path) -> None:
    receipt = tmp_path / "terminal-evidence.json"
    payload = {"schema": "r011.d2.one-shot.v1", "status": "APPLIED", "attempt_id": "ns18"}
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    receipt.write_bytes(encoded)
    index = {receipt.name: hashlib.sha256(encoded).hexdigest()}
    readback = receipt.read_bytes()
    assert readback and any(byte != 0 for byte in readback)
    assert json.loads(readback.decode("utf-8")) == payload
    assert hashlib.sha256(readback).hexdigest() == index[receipt.name]
