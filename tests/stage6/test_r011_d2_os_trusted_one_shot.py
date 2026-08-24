"""Non-elevated qualification for the bounded R011 D2 deployment procedure."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
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
    TRUSTED_BUNDLE_FILES,
    TRUSTED_BUNDLE_SHA256,
    TRUSTED_PAYLOAD_PATH,
    TRUSTED_PAYLOAD_SHA256,
    TRUSTED_STAGE0_PATH,
    TRUSTED_STAGE0_SHA256,
    TRUST_MANIFEST_SHA256,
    RUNTIME_ARCHIVE_SHA256,
    RUNTIME_ARCHIVE_SIZE,
    build_deployment_bundle,
    build_powershell_command,
    build_trusted_snapshot,
    encode_stage0,
    exact_provisioner_argv,
    resolve_native_powershell,
    safe_extract_zip,
    sha256_file,
    trusted_manifest_bytes,
    verify_exact_files,
)


ROOT = Path(__file__).resolve().parents[2]
STAGE0 = ROOT / "scripts" / "r011_d2_stage0.ps1"
PAYLOAD = ROOT / "scripts" / "r011_d2_protected_payload.ps1"
RUNTIME_ARCHIVE = Path(
    os.environ.get(
        "HMS_QR_D2_RUNTIME_ARCHIVE",
        r"F:\HMS-QR-DEV-R1F-TEST\r011-b2b-private-python-runtime-20260823T000000Z-a7d4f6c2\python-3.14.6-embed-amd64.zip",
    )
)


@pytest.fixture()
def authority(tmp_path: Path) -> D2Authority:
    bundle = tmp_path / "bundle.zip"
    build_deployment_bundle(ROOT, bundle)
    now = datetime.now(timezone.utc)
    return D2Authority(
        authority_id="R011_OS_TRUSTED_ONE_SHOT_DEPLOYMENT_IMPLEMENTATION",
        attempt_id="d2-test-attempt-001",
        created_utc=(now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        expires_utc=(now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        machine_name="HMS-PC",
        target_root=r"D:\HMS-QR-PROD",
        payload_source=str(PAYLOAD),
        payload_sha256=sha256_file(PAYLOAD),
        runtime_archive=str(RUNTIME_ARCHIVE),
        runtime_sha256=RUNTIME_ARCHIVE_SHA256,
        bundle_source=str(bundle),
        bundle_sha256=sha256_file(bundle),
    )


def _authority_values(authority: D2Authority, **changes: object) -> dict[str, object]:
    values = {item.name: getattr(authority, item.name) for item in fields(D2Authority)}
    values.update(changes)
    return values


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


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _payload_function_source() -> str:
    source = PAYLOAD.read_text(encoding="utf-8")
    return source[source.index("$ErrorActionPreference"):source.index("# __D2_MAIN__")]


def _run_payload_function_harness(commands: str) -> subprocess.CompletedProcess[str]:
    source = (
        _payload_function_source()
        + "\n$Authority=@{attempt_id='terminal-test-001';trust_manifest_sha256='"
        + TRUST_MANIFEST_SHA256
        + "'}\n"
        + commands
    )
    return subprocess.run(
        [
            str(resolve_native_powershell()),
            "-NoProfile",
            "-NonInteractive",
            "-NoLogo",
            "-Command",
            "-",
        ],
        input=source,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _run_payload_function_harness_file_capture(
    commands: str, root: Path
) -> subprocess.CompletedProcess[str]:
    source = (
        _payload_function_source()
        + "\n$Authority=@{attempt_id='terminal-test-001';trust_manifest_sha256='"
        + TRUST_MANIFEST_SHA256
        + "'}\n"
        + commands
    )
    stdout_path = root / "powershell-stdout.txt"
    stderr_path = root / "powershell-stderr.txt"
    argv = [
        str(resolve_native_powershell()),
        "-NoProfile",
        "-NonInteractive",
        "-NoLogo",
        "-Command",
        "-",
    ]
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        completed = subprocess.run(
            argv,
            input=source.encode("utf-8"),
            stdout=stdout,
            stderr=stderr,
            timeout=30,
        )
    return subprocess.CompletedProcess(
        argv,
        completed.returncode,
        stdout_path.read_text(encoding="utf-8"),
        stderr_path.read_text(encoding="utf-8"),
    )


def _read_terminal_envelope(path: Path) -> dict[str, object]:
    envelope_bytes = path.read_bytes()
    envelope = json.loads(envelope_bytes.decode("utf-8"))
    payload_bytes = __import__("base64").b64decode(envelope["payload_base64"])
    assert hashlib.sha256(payload_bytes).hexdigest() == envelope["payload_sha256"]
    return json.loads(payload_bytes.decode("utf-8"))


def test_trust_01_manifest_and_reviewed_stage0_are_code_owned(authority: D2Authority) -> None:
    assert hashlib.sha256(trusted_manifest_bytes()).hexdigest() == TRUST_MANIFEST_SHA256
    assert TRUSTED_STAGE0_PATH == STAGE0 and TRUSTED_PAYLOAD_PATH == PAYLOAD
    assert d2._canonical_trusted_bytes(STAGE0, TRUSTED_STAGE0_SHA256, "Stage-0")
    _, _, metadata = build_powershell_command(authority, STAGE0)
    assert metadata["stage0_template_sha256"] == TRUSTED_STAGE0_SHA256
    assert len(metadata["stage0_raw_sha256"]) == 64
    assert metadata["trust_manifest_sha256"] == TRUST_MANIFEST_SHA256


def test_trust_02_alternate_or_modified_stage0_is_rejected(
    authority: D2Authority, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    alternate = tmp_path / "alternate-stage0.ps1"
    alternate.write_text("__AUTHORITY_ASSIGNMENTS__\nWrite-Output 'UNREVIEWED'\n", encoding="utf-8")
    with pytest.raises(D2ContractError, match="trusted manifest"):
        build_powershell_command(authority, alternate)
    monkeypatch.setattr(d2, "TRUSTED_STAGE0_PATH", alternate)
    with pytest.raises(D2ContractError, match="identity mismatch"):
        build_powershell_command(authority, alternate)


def test_trust_03_caller_self_hash_cannot_authorize_payload_or_bundle(
    authority: D2Authority, tmp_path: Path
) -> None:
    alternate_payload = tmp_path / "alternate-payload.ps1"
    alternate_payload.write_text("Write-Output 'UNREVIEWED'", encoding="utf-8")
    payload_authority = D2Authority(
        **_authority_values(
            authority,
            payload_source=str(alternate_payload),
            payload_sha256=sha256_file(alternate_payload),
        )
    )
    with pytest.raises(D2ContractError, match="trusted manifest"):
        build_trusted_snapshot(payload_authority)
    alternate_bundle = tmp_path / "alternate-bundle.zip"
    alternate_bundle.write_bytes(b"unreviewed-bundle")
    bundle_authority = D2Authority(
        **_authority_values(
            authority,
            bundle_source=str(alternate_bundle),
            bundle_sha256=sha256_file(alternate_bundle),
        )
    )
    with pytest.raises(D2ContractError, match="trusted committed-byte manifest"):
        build_trusted_snapshot(bundle_authority)


def test_trust_04_authority_snapshot_schema_and_mutation_boundary(authority: D2Authority) -> None:
    assert not hasattr(authority, "__dict__")
    snapshot = build_trusted_snapshot(authority)
    object.__setattr__(authority, "payload_source", r"C:\unreviewed\payload.ps1")
    assert snapshot.payload_source == str(TRUSTED_PAYLOAD_PATH)
    with pytest.raises(D2ContractError):
        build_trusted_snapshot(authority)
    assert [item.name for item in fields(type(snapshot))] == [
        "authority_id", "attempt_id", "created_utc", "expires_utc", "machine_name",
        "target_root", "payload_source", "payload_sha256", "runtime_archive",
        "runtime_sha256", "bundle_source", "bundle_sha256", "service_account",
        "service_sid", "roles", "trust_manifest_sha256", "reviewed_lineage_parent",
    ]


def test_trust_05_unexpected_types_and_powershell_metacharacters_are_inert(
    authority: D2Authority, tmp_path: Path
) -> None:
    object.__setattr__(authority, "target_root", object())
    with pytest.raises(D2ContractError, match="changed type"):
        build_trusted_snapshot(authority)
    clean = D2Authority(**_authority_values(authority, target_root=r"D:\HMS-QR-PROD"))
    hostile_bundle = tmp_path / "bundle';Write-Output PWNED;#`n$(Write-Output PWNED).zip"
    hostile_bundle.write_bytes(Path(clean.bundle_source).read_bytes())
    hostile = D2Authority(
        **_authority_values(
            clean,
            bundle_source=str(hostile_bundle),
            bundle_sha256=TRUSTED_BUNDLE_SHA256,
        )
    )
    snapshot = build_trusted_snapshot(hostile)
    assignments = d2.render_authority_assignments(snapshot)
    run = subprocess.run(
        [str(resolve_native_powershell()), "-NoProfile", "-NonInteractive", "-NoLogo", "-EncodedCommand", encode_stage0(assignments + "\n[Console]::WriteLine('SERIALIZED_OK')")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0 and run.stdout.strip() == "SERIALIZED_OK"


def test_trust_06_bundle_manifest_rejects_extra_executable_and_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copied = tmp_path / "source"
    for relative in (*TRUSTED_BUNDLE_FILES, "packages/deployment/os_trusted_one_shot.py"):
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    (copied / "packages" / "deployment" / "unexpected.py").write_text("raise SystemExit", encoding="utf-8")
    monkeypatch.setattr(d2, "_REPOSITORY_ROOT", copied)
    with pytest.raises(D2ContractError, match="unexpected executable"):
        build_deployment_bundle(copied, tmp_path / "unexpected.zip")
    (copied / "packages" / "deployment" / "unexpected.py").unlink()
    (copied / "packages" / "deployment" / "provisioning.py").write_text("raise SystemExit", encoding="utf-8")
    with pytest.raises(D2ContractError, match="identity mismatch"):
        build_deployment_bundle(copied, tmp_path / "tampered.zip")


def test_trust_07_lf_and_crlf_checkouts_build_identical_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copied = tmp_path / "crlf-source"
    for relative in (*TRUSTED_BUNDLE_FILES, "packages/deployment/os_trusted_one_shot.py"):
        destination = copied / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        canonical = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
        destination.write_bytes(canonical.replace(b"\n", b"\r\n"))
    monkeypatch.setattr(d2, "_REPOSITORY_ROOT", copied)
    result = build_deployment_bundle(copied, tmp_path / "crlf.zip")
    assert result["sha256"] == TRUSTED_BUNDLE_SHA256
    assert result["files"] == dict(TRUSTED_BUNDLE_FILES)


def test_trust_08_authority_schema_rejects_unknown_missing_future_and_long_lived(
    authority: D2Authority, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = _authority_values(authority)
    with pytest.raises(TypeError):
        D2Authority(**{**values, "unexpected_field": "x"})
    missing = dict(values)
    del missing["attempt_id"]
    with pytest.raises(TypeError):
        D2Authority(**missing)
    now = datetime.now(timezone.utc)
    with pytest.raises(D2ContractError, match="maximum"):
        D2Authority(
            **_authority_values(
                authority,
                created_utc=now.isoformat().replace("+00:00", "Z"),
                expires_utc=(now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            )
        )
    future = D2Authority(
        **_authority_values(
            authority,
            created_utc=(now + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
            expires_utc=(now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        )
    )
    monkeypatch.setattr(d2, "_utc_now", lambda: now)
    with pytest.raises(D2ContractError, match="not active"):
        build_trusted_snapshot(future)


@pytest.mark.parametrize(
    ("status", "phase", "native_exit", "failure_code"),
    [
        ("SUCCESS", "TERMINAL_SUCCESS", 0, "NONE"),
        ("FAILED", "PROVISIONER_WAIT", 37, "NATIVE_NONZERO"),
        ("FAILED", "POSTSTATE", 0, "POSTSTATE_FAILED"),
        ("INDETERMINATE", "PROVISIONER_START", None, "INTERRUPTED_OR_NO_NATIVE_EXIT"),
    ],
)
def test_terminal_01_state_model_and_readback(
    tmp_path: Path, status: str, phase: str, native_exit: int | None, failure_code: str
) -> None:
    receipt = tmp_path / "terminal-evidence.json"
    native = "$null" if native_exit is None else str(native_exit)
    run = _run_payload_function_harness(
        f"Publish-TerminalEvidence {_ps_literal(str(receipt))} '{status}' '{phase}' {native} '{failure_code}' 'bounded detail'"
    )
    assert run.returncode == 0, run.stderr
    payload = _read_terminal_envelope(receipt)
    assert payload["status"] == status and payload["phase"] == phase
    assert payload["native_exit_code"] == native_exit and payload["failure_code"] == failure_code
    assert payload["retry_authorized"] is False


def test_terminal_02_native_exit_is_durable_before_terminal_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "terminal-evidence.json"
    run = _run_payload_function_harness(
        f"Publish-NativeExitEvidence {_ps_literal(str(tmp_path))} 37;"
        f"Publish-TerminalEvidence {_ps_literal(str(receipt))} 'FAILED' 'PROVISIONER_WAIT' 37 'NATIVE_NONZERO' ''"
    )
    assert run.returncode == 0, run.stderr
    assert (tmp_path / "provisioner-native-exit-code.txt").read_text(encoding="ascii") == "37\n"
    assert _read_terminal_envelope(receipt)["native_exit_code"] == 37


@pytest.mark.parametrize("failure_mode", ["write", "move", "readback"])
def test_terminal_03_uncommitted_primary_always_resolves_to_durable_baseline(
    tmp_path: Path, failure_mode: str
) -> None:
    baseline = tmp_path / "terminal-baseline.json"
    latch = tmp_path / "apply.latch"
    primary = tmp_path / "terminal-evidence.json"
    index = tmp_path / "terminal-authority-index.json"
    if failure_mode == "write":
        override = (
            "$OriginalWrite=${function:Write-DurableEvidenceBytes};"
            "function Write-DurableEvidenceBytes([string]$path,[byte[]]$bytes){if($path.EndsWith('terminal-evidence.json')){throw 'INJECTED_WRITE'};& $OriginalWrite $path $bytes}"
        )
    elif failure_mode == "move":
        override = (
            "$OriginalMove=${function:Move-EvidenceFile};"
            "function Move-EvidenceFile([string]$source,[string]$destination){if($destination.EndsWith('terminal-evidence.json')){throw 'INJECTED_MOVE'};& $OriginalMove $source $destination}"
        )
    else:
        override = (
            "$OriginalRead=${function:Read-EvidenceBytes};"
            "function Read-EvidenceBytes([string]$path){$bytes=& $OriginalRead $path;if($path.EndsWith('terminal-evidence.json')){$bytes[0]=$bytes[0]-bxor 1};return $bytes}"
        )
    commands = (
        f"Publish-TerminalEvidence {_ps_literal(str(baseline))} 'INDETERMINATE' 'APPLY_LATCH_PENDING' $null 'APPLY_NOT_TERMINALLY_COMMITTED' '';"
        + f"$baselineHash=Get-BytesSha256 (Read-EvidenceBytes {_ps_literal(str(baseline))});Set-OneShotLatch {_ps_literal(str(tmp_path))} $baselineHash;"
        + override
        + f";try{{Publish-AuthoritativeTerminalEvidence {_ps_literal(str(baseline))} {_ps_literal(str(latch))} {_ps_literal(str(primary))} {_ps_literal(str(index))} 'SUCCESS' 'TERMINAL_SUCCESS' 0 'NONE' ''}}catch{{}};"
        + f"[Console]::WriteLine((Resolve-TerminalEvidencePath {_ps_literal(str(baseline))} {_ps_literal(str(latch))} {_ps_literal(str(primary))} {_ps_literal(str(index))}))"
    )
    run = _run_payload_function_harness(commands)
    assert run.returncode == 0, run.stderr
    assert Path(run.stdout.strip()) == baseline
    payload = _read_terminal_envelope(baseline)
    assert payload["status"] == "INDETERMINATE"
    assert payload["failure_code"] == "APPLY_NOT_TERMINALLY_COMMITTED"


def test_terminal_04_receipt_is_create_new_and_cannot_be_relabelled(tmp_path: Path) -> None:
    receipt = tmp_path / "terminal-evidence.json"
    first = _run_payload_function_harness(
        f"Publish-TerminalEvidence {_ps_literal(str(receipt))} 'FAILED' 'POSTSTATE' 0 'POSTSTATE_FAILED' 'first'"
    )
    assert first.returncode == 0, first.stderr
    frozen = receipt.read_bytes()
    second = _run_payload_function_harness(
        f"Publish-TerminalEvidence {_ps_literal(str(receipt))} 'SUCCESS' 'TERMINAL_SUCCESS' 0 'NONE' 'second'"
    )
    assert second.returncode != 0
    assert receipt.read_bytes() == frozen
    assert _read_terminal_envelope(receipt)["status"] == "FAILED"


def test_terminal_05_valid_commit_index_is_the_only_terminal_precedence_authority(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "terminal-baseline.json"
    latch = tmp_path / "apply.latch"
    receipt = tmp_path / "terminal-evidence.json"
    index = tmp_path / "terminal-authority-index.json"
    run = _run_payload_function_harness(
        f"Publish-TerminalEvidence {_ps_literal(str(baseline))} 'INDETERMINATE' 'APPLY_LATCH_PENDING' $null 'APPLY_NOT_TERMINALLY_COMMITTED' '';"
        f"$baselineHash=Get-BytesSha256 (Read-EvidenceBytes {_ps_literal(str(baseline))});Set-OneShotLatch {_ps_literal(str(tmp_path))} $baselineHash;"
        f"Publish-AuthoritativeTerminalEvidence {_ps_literal(str(baseline))} {_ps_literal(str(latch))} {_ps_literal(str(receipt))} {_ps_literal(str(index))} 'SUCCESS' 'TERMINAL_SUCCESS' 0 'NONE' '';"
        f"[Console]::WriteLine((Resolve-TerminalEvidencePath {_ps_literal(str(baseline))} {_ps_literal(str(latch))} {_ps_literal(str(receipt))} {_ps_literal(str(index))}))"
    )
    assert run.returncode == 0, run.stderr
    assert Path(run.stdout.strip()) == receipt
    assert _read_terminal_envelope(receipt)["status"] == "SUCCESS"
    parsed_index = json.loads(index.read_text(encoding="utf-8"))
    assert parsed_index["authoritative_receipt"] == receipt.name
    assert parsed_index["terminal_sha256"] == hashlib.sha256(receipt.read_bytes()).hexdigest()
    assert parsed_index["baseline_sha256"] == hashlib.sha256(baseline.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "failure_mode",
    [
        "missing_latch",
        "baseline_changed",
        "uppercase_label",
        "uppercase_digest",
        "extra_terminal_lf",
    ],
)
def test_terminal_05b_latch_baseline_binding_is_required_for_terminal_authority(
    tmp_path: Path, failure_mode: str
) -> None:
    baseline = tmp_path / "terminal-baseline.json"
    latch = tmp_path / "apply.latch"
    receipt = tmp_path / "terminal-evidence.json"
    index = tmp_path / "terminal-authority-index.json"
    commands = (
        f"Publish-TerminalEvidence {_ps_literal(str(baseline))} 'INDETERMINATE' 'APPLY_LATCH_PENDING' $null 'APPLY_NOT_TERMINALLY_COMMITTED' '';"
    )
    if failure_mode != "missing_latch":
        commands += (
            f"$baselineHash=Get-BytesSha256 (Read-EvidenceBytes {_ps_literal(str(baseline))});"
            f"Set-OneShotLatch {_ps_literal(str(tmp_path))} $baselineHash;"
        )
    if failure_mode == "baseline_changed":
        commands += (
            f"[IO.File]::AppendAllText({_ps_literal(str(baseline))},'tamper',[Text.Encoding]::ASCII);"
        )
    elif failure_mode == "uppercase_label":
        commands += f"[IO.File]::WriteAllText({_ps_literal(str(latch))},('BASELINE_SHA256=' + $baselineHash + \"`n\"),[Text.Encoding]::ASCII);"
    elif failure_mode == "uppercase_digest":
        commands += f"[IO.File]::WriteAllText({_ps_literal(str(latch))},('baseline_sha256=' + $baselineHash.ToUpperInvariant() + \"`n\"),[Text.Encoding]::ASCII);"
    elif failure_mode == "extra_terminal_lf":
        commands += f"[IO.File]::AppendAllText({_ps_literal(str(latch))},\"`n\",[Text.Encoding]::ASCII);"
    commands += (
        f"try{{Publish-AuthoritativeTerminalEvidence {_ps_literal(str(baseline))} {_ps_literal(str(latch))} {_ps_literal(str(receipt))} {_ps_literal(str(index))} 'SUCCESS' 'TERMINAL_SUCCESS' 0 'NONE' '';exit 9}}"
        "catch{[Console]::WriteLine($_.Exception.Message)}"
    )
    run = _run_payload_function_harness(commands)
    assert run.returncode == 0, run.stderr
    assert "latch" in run.stdout.casefold()
    assert not receipt.exists() and not index.exists()


def test_terminal_06_native_exit_publication_failure_is_truthfully_indeterminate() -> None:
    run = _run_payload_function_harness(
        "$classification=Get-TerminalFailureClassification 'NATIVE_EXIT_PUBLICATION' 0;"
        "[Console]::WriteLine(([string]$classification.status + '|' + [string]$classification.failure_code))"
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "INDETERMINATE|NATIVE_EXIT_PUBLICATION_FAILED"


def test_terminal_06b_successfully_published_native_nonzero_is_truthfully_failed() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    publication = source.rindex("Publish-NativeExitEvidence $StagingPath $nativeExitCode")
    result_phase = source.rindex("$phase = 'PROVISIONER_RESULT'")
    nonzero = source.rindex("if ($nativeExitCode -ne 0)")
    assert publication < result_phase < nonzero
    run = _run_payload_function_harness(
        "$classification=Get-TerminalFailureClassification 'PROVISIONER_RESULT' 37;"
        "[Console]::WriteLine(([string]$classification.status + '|' + [string]$classification.failure_code))"
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "FAILED|NATIVE_NONZERO"


def test_terminal_07_native_create_suspended_job_contained_exit_is_captured(
    tmp_path: Path,
) -> None:
    executable = os.environ["ComSpec"]
    run = _run_payload_function_harness_file_capture(
        f"$contained=Start-ContainedProcess {_ps_literal(executable)} '/d /c exit 7' {_ps_literal(str(tmp_path))};"
        "$exit=Wait-ContainedProcess $contained;[Console]::WriteLine(('EXIT=' + [string]$exit))",
        tmp_path,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "EXIT=7"


def test_terminal_08_abrupt_controller_death_kills_owned_child_before_escape_marker(
    tmp_path: Path,
) -> None:
    import ctypes

    child_script = tmp_path / "contained-child.py"
    marker = tmp_path / "escaped.marker"
    pid_path = tmp_path / "contained.pid"
    child_script.write_text(
        "import pathlib,sys,time\ntime.sleep(3)\npathlib.Path(sys.argv[1]).write_text('escaped', encoding='ascii')\n",
        encoding="utf-8",
        newline="\n",
    )
    arguments = subprocess.list2cmdline(["-B", str(child_script), str(marker)])
    source = (
        _payload_function_source()
        + "\n$Authority=@{attempt_id='containment-test-001';trust_manifest_sha256='"
        + TRUST_MANIFEST_SHA256
        + "'}\n"
        + f"$contained=Start-ContainedProcess {_ps_literal(sys.executable)} {_ps_literal(arguments)} {_ps_literal(str(tmp_path))};"
        + f"[IO.File]::WriteAllText({_ps_literal(str(pid_path))},[string]$contained.pid,[Text.Encoding]::ASCII);"
        + "$null=Wait-ContainedProcess $contained"
    )
    controller = subprocess.Popen(
        [
            str(resolve_native_powershell()),
            "-NoProfile",
            "-NonInteractive",
            "-NoLogo",
            "-Command",
            "-",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert controller.stdin is not None
    controller.stdin.write(source)
    controller.stdin.close()
    deadline = time.monotonic() + 10
    while not pid_path.exists() and controller.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    if not pid_path.exists():
        controller.wait(timeout=5)
        stdout = controller.stdout.read() if controller.stdout is not None else ""
        stderr = controller.stderr.read() if controller.stderr is not None else ""
        pytest.fail(f"contained PID was not published: stdout={stdout!r} stderr={stderr!r}")
    child_pid = int(pid_path.read_text(encoding="ascii"))
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    child_handle = kernel32.OpenProcess(0x00100000, False, child_pid)
    assert child_handle
    try:
        controller.terminate()
        controller.wait(timeout=5)
        assert kernel32.WaitForSingleObject(ctypes.c_void_p(child_handle), 5000) == 0
        assert not marker.exists()
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(child_handle))


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
        authority.__class__(**_authority_values(authority, attempt_id="../unsafe"))
    for field, value in (("authority_id", "OTHER"), ("machine_name", "OTHER-PC"), ("target_root", r"D:\other"), ("service_account", r"HMS-PC\Other"), ("service_sid", "S-1-5-21-1")):
        with pytest.raises(D2ContractError):
            authority.__class__(**_authority_values(authority, **{field: value}))


def test_d2_10_deadline_is_literal_binding(authority: D2Authority) -> None:
    assert authority.expires_utc in _bound_stage0_source(authority)
    with pytest.raises(D2ContractError, match="ordered UTC"):
        authority.__class__(**_authority_values(authority, expires_utc=authority.created_utc))


def test_d2_11_expired_stage0_has_apply_zero_contract() -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert source.index("authority is not active") < source.index("Ensure-AdminOnlyDirectory $stagingRoot")
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
    with pytest.raises(D2ContractError, match="trusted committed-byte manifest"):
        build_powershell_command(authority.__class__(**_authority_values(authority, payload_sha256="0" * 64)), STAGE0)
    with pytest.raises(D2ContractError, match="frozen CPython"):
        authority.__class__(**_authority_values(authority, runtime_sha256="0" * 64))


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
    assert "$nativeExitCode -ne 0" in source and "retry is forbidden" in source
    assert "Publish-NativeExitEvidence" in source and "NATIVE_NONZERO" in source
    assert "CreateProcessW" in source and "CREATE_SUSPENDED" not in source
    assert "[uint32]0x01080004" in source and "PROC_THREAD_ATTRIBUTE_JOB_LIST" in source
    assert "UpdateProcThreadAttribute" in source and "IsProcessInJob" in source


def test_d2_30_poststate_mismatch_is_terminal_no_retry() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    assert source.rindex("Assert-PostState") > source.index("$nativeExitCode -ne 0")
    assert source.count("$script:D2NativeApi.CreateProcessW.Invoke(") == 1
    assert "POSTSTATE_FAILED" in source and "Publish-TerminalEvidence" in source
    assert "Assert-NoReparseAncestor $path" in source and "Assert-DeploymentAcl $path (Get-RoleSddl ([string]$Authority.service_sid) $role)" in source


def test_d2_31_duplicate_latch_is_denied_before_provisioner() -> None:
    source = PAYLOAD.read_text(encoding="utf-8")
    stage0 = STAGE0.read_text(encoding="utf-8")
    assert source.rindex("Set-OneShotLatch $StagingPath") < source.rindex("$contained = Start-ContainedProcess")
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
    assert source.count("$script:D2NativeApi.CreateProcessW.Invoke(") == 1
    assert "terminal-baseline.json" in source and "terminal-authority-index.json" in source
    assert "Resolve-TerminalEvidencePath" in source and "APPLY_NOT_TERMINALLY_COMMITTED" in source


def test_d2_33_normal_product_runtime_has_no_self_elevation_dependency() -> None:
    runtime_sources = list((ROOT / "apps").rglob("*.py")) + list((ROOT / "packages").rglob("*.py"))
    assert all("os_trusted_one_shot" not in item.read_text(encoding="utf-8") for item in runtime_sources if item != ROOT / "packages" / "deployment" / "os_trusted_one_shot.py")


def test_d2_34_custom_ipc_count_is_zero() -> None:
    text = (STAGE0.read_text(encoding="utf-8") + PAYLOAD.read_text(encoding="utf-8")).casefold()
    assert all(token not in text for token in ("namedpipe", "eventwait", "scheduledtask", "start-job", "start-threadjob"))


def test_d2_35_future_process_count_is_bounded_to_three() -> None:
    text = (STAGE0.read_text(encoding="utf-8") + PAYLOAD.read_text(encoding="utf-8")).casefold()
    assert text.count("$script:d2nativeapi.createprocessw.invoke(") == 1
    assert "start-process" not in text and "add-type" not in text


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
            D2Authority(**_authority_values(authority, attempt_id=attempt_id))


def test_ns06_attempt_absolute_forms_are_rejected(authority: D2Authority) -> None:
    for attempt_id in (r"C:\attempt", r"\\server\share", r"\\?\C:\attempt"):
        with pytest.raises(D2ContractError):
            D2Authority(**_authority_values(authority, attempt_id=attempt_id))


def test_ns07_attempt_ads_is_rejected(authority: D2Authority) -> None:
    with pytest.raises(D2ContractError):
        D2Authority(**_authority_values(authority, attempt_id="attempt:ads"))


def test_ns08_attempt_parent_confinement_is_explicit(authority: D2Authority) -> None:
    source = STAGE0.read_text(encoding="utf-8")
    assert "GetFullPath([IO.Path]::Combine($namespaceRoot" in source
    assert "Attempt path is not confined to D2 namespace" in source
    assert D2Authority(**_authority_values(authority, attempt_id="A1._-z")).attempt_id == "A1._-z"


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
    assert "[IO.Path]::Combine($StagingPath, 'terminal-baseline.json')" in source
    assert "[IO.Path]::Combine($StagingPath, 'terminal-evidence.json')" in source
    assert "[IO.Path]::Combine($StagingPath, 'terminal-authority-index.json')" in source


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
    canonical = (ROOT / "packages" / "deployment" / "provisioning.py").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(canonical).hexdigest() == TRUSTED_BUNDLE_FILES["packages/deployment/provisioning.py"]


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
