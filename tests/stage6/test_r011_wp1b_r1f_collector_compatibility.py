"""Windows PowerShell 5.1 compatibility guards for the R011 inventory collector."""
from __future__ import annotations

import json
import locale
import re
import subprocess
from pathlib import Path

import pytest

from packages.deployment.inventory import (
    InventoryValidationError,
    ReadOnlyInventoryCollector,
    validate_inventory,
)


ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = ROOT / "scripts" / "r011_collect_inventory_readonly.ps1"
POWERSHELL = "powershell.exe"


def _decode_powershell_output(output: bytes) -> str:
    encodings = ("utf-8-sig", locale.getpreferredencoding(False), "mbcs")
    for encoding in dict.fromkeys(encodings):
        try:
            return output.decode(encoding)
        except UnicodeDecodeError:
            continue
    return output.decode(locale.getpreferredencoding(False), errors="replace")


def _run_powershell(*arguments: str) -> subprocess.CompletedProcess[str]:
    raw = subprocess.run(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", *arguments],
        capture_output=True,
        check=False,
    )
    return subprocess.CompletedProcess(
        args=raw.args,
        returncode=raw.returncode,
        stdout=_decode_powershell_output(raw.stdout),
        stderr=_decode_powershell_output(raw.stderr),
    )


def _synthetic_inventory() -> dict:
    return ReadOnlyInventoryCollector().collect()


@pytest.fixture(scope="module")
def collector_result() -> subprocess.CompletedProcess[str]:
    return _run_powershell(
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(COLLECTOR),
    )


def test_windows_powershell_51_is_the_compatibility_runtime():
    result = _run_powershell(
        "-Command",
        "$PSVersionTable.PSVersion.ToString()",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("5.1.")


def test_assignment_targets_do_not_collide_with_read_only_automatic_variables():
    collector = str(COLLECTOR).replace("'", "''")
    command = rf"""
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{collector}', [ref]$tokens, [ref]$errors)
$assignmentTargets = @(
    $ast.FindAll({{ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] }}, $true) |
        ForEach-Object {{
            if ($_.Left -is [System.Management.Automation.Language.VariableExpressionAst]) {{
                $_.Left.VariablePath.UserPath
            }}
        }}
)
$protectedVariables = @(
    Get-Variable | Where-Object {{
        ($_.Options -band [System.Management.Automation.ScopedItemOptions]::ReadOnly) -or
        ($_.Options -band [System.Management.Automation.ScopedItemOptions]::Constant)
    }} | ForEach-Object {{ $_.Name }}
)
$candidateNames = @(
    'ExecutionContext', 'Host', 'PID', 'HOME', 'Error', 'Matches', 'Args',
    'Input', 'PSScriptRoot', 'PSCommandPath', 'MyInvocation', 'PSVersionTable',
    'NestedPromptLevel', 'StackTrace', 'This'
)
$classifications = @(
    foreach ($name in $candidateNames) {{
        $variable = Get-Variable -Name $name -ErrorAction SilentlyContinue
        [pscustomobject]@{{
            name = $name
            exists = [bool]$variable
            options = if ($variable) {{ $variable.Options.ToString() }} else {{ 'ABSENT' }}
        }}
    }}
)
[pscustomobject]@{{
    parse_error_count = @($errors).Count
    assignment_targets = @($assignmentTargets)
    protected_variables = @($protectedVariables)
    candidate_classifications = @($classifications)
}} | ConvertTo-Json -Depth 5 -Compress
"""
    result = _run_powershell("-Command", command)
    assert result.returncode == 0, result.stderr
    audit = json.loads(result.stdout)
    assert audit["parse_error_count"] == 0

    assignment_targets = {name.casefold() for name in audit["assignment_targets"]}
    protected_variables = {name.casefold() for name in audit["protected_variables"]}
    assert "executioncontext" in protected_variables
    assert assignment_targets.isdisjoint(protected_variables)

    classifications = {
        item["name"].casefold(): item["options"]
        for item in audit["candidate_classifications"]
    }
    assert set(classifications) == {
        "executioncontext",
        "host",
        "pid",
        "home",
        "error",
        "matches",
        "args",
        "input",
        "psscriptroot",
        "pscommandpath",
        "myinvocation",
        "psversiontable",
        "nestedpromptlevel",
        "stacktrace",
        "this",
    }
    assert classifications["executioncontext"] in {"ReadOnly", "Constant", "Constant, AllScope"}


def test_execution_context_local_references_move_together_without_schema_drift():
    source = COLLECTOR.read_text(encoding="utf-8")
    assert not re.search(r"(?im)^\s*\$executionContext\s*[+]?=", source)
    assert '$inventoryExecutionContext = Read-Section -Name "execution_context"' in source
    assert "execution_context=$inventoryExecutionContext" in source
    assert "execution_context = $inventoryExecutionContext" in source
    assert 'inventory_schema_version = "r011.machine-inventory.v1"' in source


def test_exact_collector_loads_and_emits_schema_valid_json(collector_result):
    assert collector_result.returncode == 0, collector_result.stderr
    assert "VariableNotWritable" not in collector_result.stderr
    payload = json.loads(collector_result.stdout)
    assert validate_inventory(payload) == payload
    assert payload["machine_identity"]["execution_context"]["state"] in {
        "KNOWN",
        "ACCESS_DENIED",
        "UNKNOWN",
        "UNSUPPORTED",
    }


def test_runtime_output_preserves_secret_and_command_line_minimization(collector_result):
    assert collector_result.returncode == 0, collector_result.stderr
    output = collector_result.stdout
    assert not re.search(r'(?i)"(?:CommandLine|PathName|ImagePath|Arguments)"\s*:', output)
    assert not re.search(r"(?i)-----BEGIN [^-]*(?:PRIVATE KEY|OPENSSH KEY)-----", output)
    assert not re.search(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", output)
    assert not re.search(
        r"(?i)postgres(?:ql)?://[^\s\"/:]+:[^\s\"@]+@",
        output,
    )


def test_benign_service_display_name_secret_words_are_allowed():
    payload = _synthetic_inventory()
    payload["services"] = {
        "state": "KNOWN",
        "items": [
            {
                "Name": "synthetic-metadata-service",
                "DisplayName": "Synthetic Password Token Key Secret Metadata",
                "State": "Running",
                "StartMode": "Auto",
                "StartName": "LocalSystem",
            }
        ],
    }
    payload["tls"] = {
        "state": "KNOWN",
        "items": [
            {
                "Subject": "CN=Synthetic Password Key Metadata",
                "HasPrivateKey": True,
            }
        ],
    }
    assert validate_inventory(payload) == payload


@pytest.mark.parametrize(
    "secret_key",
    (
        "password",
        "passwd",
        "credential",
        "secret",
        "token",
        "api_key",
        "private_key",
        "authorization",
        "connection_string",
    ),
)
def test_secret_bearing_structural_keys_remain_fail_closed(secret_key):
    payload = _synthetic_inventory()
    payload["services"] = {secret_key: "SYNTHETIC_CANARY"}
    with pytest.raises(InventoryValidationError, match="secret-bearing field"):
        validate_inventory(payload)


@pytest.mark.parametrize(
    "secret_value",
    (
        "password=SYNTHETIC_CANARY",
        "postgresql://synthetic:SYNTHETIC_CANARY@localhost/db",
        "Authorization: Bearer SYNTHETIC_CANARY_VALUE",
        "-----BEGIN SYNTHETIC PRIVATE KEY-----",
    ),
)
def test_credential_bearing_value_signatures_remain_fail_closed(secret_value):
    payload = _synthetic_inventory()
    payload["services"] = {"state": "KNOWN", "items": [{"note": secret_value}]}
    with pytest.raises(InventoryValidationError, match="secret-bearing value"):
        validate_inventory(payload)


@pytest.mark.parametrize("raw_field", ("PathName", "ImagePath", "CommandLine", "Arguments"))
def test_raw_execution_fields_remain_fail_closed(raw_field):
    payload = _synthetic_inventory()
    payload["services"] = {
        "state": "KNOWN",
        "items": [{raw_field: "SYNTHETIC_COMMAND_CANARY"}],
    }
    with pytest.raises(InventoryValidationError, match="secret-bearing field"):
        validate_inventory(payload)
