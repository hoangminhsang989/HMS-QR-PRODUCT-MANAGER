"""Pure, fail-closed preflight and dry-run over artifact, plan, and inventory."""
from dataclasses import dataclass, field
from typing import Any
from .artifact import verify_release, ArtifactBuildError
from .configuration import validate_production_config, ConfigValidationError
from .inventory import validate_inventory, InventoryValidationError
from .plans import DeploymentPlan, validate_plan

@dataclass
class PreflightResult:
    passed: bool
    checks: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    machine_mutation_count: int = 0

def _items(section: Any) -> list[dict[str, Any]]:
    if not isinstance(section, dict) or section.get("state") != "KNOWN": return []
    return [v for v in section.get("items", []) if isinstance(v, dict)]

def run_preflight(artifact: str, config: dict[str, Any], inventory: dict[str, Any], plan: DeploymentPlan | None = None) -> PreflightResult:
    checks: dict[str, str] = {}; errors: list[str] = []; manifest = None
    def check(name, fn):
        try: fn(); checks[name] = "PASS"
        except (ArtifactBuildError, ConfigValidationError, InventoryValidationError, ValueError, OSError, KeyError, TypeError) as exc: checks[name] = "FAIL"; errors.append(f"{name}: {exc}")
    def artifact_check():
        nonlocal manifest; manifest = verify_release(artifact)
    check("artifact", artifact_check)
    check("config", lambda: validate_production_config(config))
    check("inventory", lambda: validate_inventory(inventory))
    def plan_check():
        if plan is None or manifest is None: raise ValueError("deployment plan required")
        validate_plan(plan, inventory, manifest)
    check("plan_binding", plan_check)
    def policy_checks():
        if plan is None: raise ValueError("deployment plan required")
        os_items = _items(inventory.get("os")); arch = str(os_items[0].get("architecture", "")) if os_items else ""
        if arch not in {"AMD64", "x86_64", "64-bit"}: raise ValueError("unsupported or unknown OS architecture")
        volumes = _items(inventory.get("volumes"))
        if not volumes or max(int(v.get("free_bytes", -1)) for v in volumes) < plan.min_free_bytes: raise ValueError("insufficient or unknown storage")
        if any(not v.get("filesystem") for v in volumes): raise ValueError("unknown filesystem")
        listeners = _items(inventory.get("listeners"))
        if any(int(v.get("port", -1)) == plan.network.port for v in listeners): raise ValueError("API port occupied")
        services = _items(inventory.get("services"))
        if any(str(v.get("name", "")).casefold() == plan.service_name.casefold() for v in services): raise ValueError("service name collision")
        if plan.postgresql.decision not in {"INSTALL", "ADOPT", "SIDE_BY_SIDE"}: raise ValueError("PostgreSQL decision unavailable")
        if not plan.python_runtime or plan.python_runtime.startswith("<"): raise ValueError("runtime unresolved")
        if not plan.network.tls.termination or not plan.network.tls.certificate_ref.startswith("ref:"): raise ValueError("TLS decision missing")
        if not plan.network.firewall.pre_state_hash or not plan.network.firewall.rule_id: raise ValueError("firewall plan incomplete")
        if not plan.backup_prerequisite or not plan.rollback_actions: raise ValueError("rollback prerequisite missing")
        if set(plan.resolved_roots) != {"APP_INSTALL_ROOT", "APP_DATA_ROOT", "APP_LOG_ROOT", "LOCAL_INGEST_ROOT", "SECRET_STORE", "POSTGRESQL_DATA_ROOT", "DEPLOYMENT_STAGING_ROOT", "ROLLBACK_RELEASE_ROOT"}: raise ValueError("resolved roots incomplete")
    check("machine_policy", policy_checks)
    checks["mutation"] = "ZERO"
    return PreflightResult(not errors, checks, errors, 0)

def dry_run(artifact: str, config: dict[str, Any], inventory: dict[str, Any], plan: DeploymentPlan) -> dict[str, Any]:
    result = run_preflight(artifact, config, inventory, plan)
    if not result.passed: raise ValueError("dry-run preflight failed: " + "; ".join(result.errors))
    return {"schema": "r011.dry-run.v1", "inventory_sha256": plan.inventory_sha256, "release_id": plan.release_id,
            "planned_mutations": list(plan.planned_mutations), "required_uac_class": plan.required_uac_class,
            "rollback_actions": list(plan.rollback_actions), "machine_mutation_count": 0, "executed": False, "verdict": "DRY_RUN_ONLY"}
