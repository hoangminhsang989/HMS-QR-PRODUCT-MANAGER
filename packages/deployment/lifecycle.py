"""Transaction-oriented local fake install/update/remove/rollback framework."""
from __future__ import annotations
import json, shutil
from pathlib import Path
from dataclasses import dataclass
from config.paths import require_test_root
from .artifact import verify_release
from .preflight import PreflightResult

PERSISTENT_ROOTS = ("APP_DATA_ROOT", "APP_LOG_ROOT", "LOCAL_INGEST_ROOT", "SECRET_STORE", "POSTGRESQL_DATA_ROOT")

@dataclass
class LocalDeploymentBackend:
    root: Path
    def __post_init__(self):
        self.root = Path(self.root)
        try: self.root.resolve().relative_to(require_test_root())
        except ValueError as exc: raise ValueError("local deployment backend must remain under external test root") from exc
        self.state_path = self.root / "fake-state.json"; self.root.mkdir(parents=True, exist_ok=True)
    def state(self) -> dict:
        if not self.state_path.exists(): return {"active_release": None, "retained_releases": [], "transactions": []}
        return json.loads(self.state_path.read_text(encoding="utf-8"))
    def save(self, state: dict) -> None: self.state_path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    def path(self, symbolic: str) -> Path:
        p = self.root / symbolic; p.mkdir(parents=True, exist_ok=True); return p

def _stage(backend: LocalDeploymentBackend, artifact: str | Path) -> tuple[str, Path]:
    manifest = verify_release(artifact); release = manifest["release_id"]
    target = backend.path("APP_INSTALL_ROOT") / release
    if target.exists(): verify_release(target, expected_head=manifest["git_head"], expected_tree=manifest["git_tree"])
    else: shutil.copytree(artifact, target); verify_release(target)
    return release, target

def install_release(backend: LocalDeploymentBackend, artifact: str | Path, preflight: PreflightResult, *, health_ready: bool = True) -> dict:
    if not preflight.passed or preflight.machine_mutation_count: raise ValueError("install requires passing pure preflight")
    release, _ = _stage(backend, artifact); s = backend.state(); previous = s.get("active_release")
    phases = ["PRESTATE", "VERIFY", "STAGE"]
    if health_ready:
        if previous and previous != release and previous not in s["retained_releases"]: s["retained_releases"].append(previous)
        s["active_release"] = release; phases += ["ACTIVATE", "VERIFY_HEALTH", "ACCEPT"]
    else:
        phases += ["VERIFY_HEALTH_FAILED", "REVERT"]; s["active_release"] = previous
    s["transactions"].append({"release": release, "phases": phases, "accepted": health_ready}); backend.save(s); return s

def activate_release(backend: LocalDeploymentBackend, artifact: str | Path) -> dict:
    return install_release(backend, artifact, PreflightResult(True), health_ready=True)

def update_release(backend: LocalDeploymentBackend, artifact: str | Path, preflight: PreflightResult | None = None, *, health_ready: bool = True) -> dict:
    return install_release(backend, artifact, preflight or PreflightResult(True), health_ready=health_ready)

def rollback_release(backend: LocalDeploymentBackend, release: str | None = None, *, config_compatible: bool = False, schema_compatible: bool = False) -> dict:
    if not config_compatible or not schema_compatible: raise ValueError("application/config/database rollback compatibility is not proven")
    s = backend.state(); retained = s.get("retained_releases", []); target = release or (retained[-1] if retained else None)
    if not target: raise ValueError("no retained rollback release")
    verify_release(backend.path("APP_INSTALL_ROOT") / target)
    current = s.get("active_release"); s["retained_releases"] = [x for x in retained if x != target]
    if current and current != target: s["retained_releases"].append(current)
    s["active_release"] = target; s["transactions"].append({"release": target, "phases": ["VERIFY_PREVIOUS", "VERIFY_COMPATIBILITY", "ACTIVATE", "VERIFY_HEALTH"], "automatic_db_downgrade": False}); backend.save(s); return s

def uninstall(backend: LocalDeploymentBackend, *, remove_releases: bool = True) -> dict:
    s = backend.state()
    if remove_releases:
        install = backend.path("APP_INSTALL_ROOT")
        for child in install.iterdir(): shutil.rmtree(child) if child.is_dir() else child.unlink()
    s["active_release"] = None; s["transactions"].append({"phases": ["REMOVE_RELEASES", "PRESERVE_PERSISTENT_DATA"]}); backend.save(s); return s
