"""Deterministic immutable release artifact builder and fail-closed verifier."""
from __future__ import annotations
import hashlib, json, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from config.paths import require_test_root

MANIFEST_SCHEMA = "r011.release-manifest.v1"
class ArtifactBuildError(ValueError): pass

def _git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if p.returncode:
        raise ArtifactBuildError(f"git command failed: {' '.join(args)}")
    return p.stdout.strip()

def _git_bytes(root: Path, *args: str) -> bytes:
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if p.returncode:
        raise ArtifactBuildError(f"git object command failed: {' '.join(args)}")
    return p.stdout

def _identity(root: Path, requested_head: str | None = None, requested_tree: str | None = None) -> tuple[str, str]:
    if _git(root, "status", "--porcelain"):
        raise ArtifactBuildError("certified build requires a clean worktree")
    head, tree = _git(root, "rev-parse", "HEAD"), _git(root, "rev-parse", "HEAD^{tree}")
    if not head or not tree or head == "HEAD":
        raise ArtifactBuildError("unknown Git identity")
    if requested_head is not None:
        resolved = _git(root, "rev-parse", f"{requested_head}^{{commit}}")
        if resolved != head: raise ArtifactBuildError("requested Git HEAD does not match clean build environment")
    if requested_tree is not None and requested_tree != tree:
        raise ArtifactBuildError("requested Git tree does not match clean build environment")
    return head, tree

def _tree_entries(root: Path, head: str) -> dict[str, tuple[str, str, str]]:
    records = _git_bytes(root, "ls-tree", "-r", "-z", "--full-tree", head).split(b"\0")
    result: dict[str, tuple[str, str, str]] = {}
    for record in records:
        if not record: continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, oid = metadata.decode("ascii").split(" ")
            path = raw_path.decode("utf-8", "surrogateescape")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ArtifactBuildError("malformed Git tree entry") from exc
        if path in result: raise ArtifactBuildError("duplicate Git tree path")
        result[path] = (mode, kind, oid)
    return result

def _blob_bytes(root: Path, mode: str, kind: str, oid: str, path: str) -> bytes:
    if kind != "blob" or mode not in {"100644", "100755"}:
        raise ArtifactBuildError(f"unsupported Git tree entry for release payload: {path} ({mode} {kind})")
    return _git_bytes(root, "cat-file", "blob", oid)

def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def build_release(source_root: str | Path, output_root: str | Path, *, release_id: str,
                  expected_alembic_head: str = "0005_store_forward", build_timestamp: str | None = None,
                  builder_version: str = "r011-wp1a-r1a-1", files: Iterable[str] | None = None,
                  git_head: str | None = None, git_tree: str | None = None) -> Path:
    source, output = Path(source_root), Path(output_root)
    try: output.resolve().relative_to(require_test_root())
    except ValueError as exc: raise ArtifactBuildError("certified build output must remain under the external test root") from exc
    try: output.resolve().relative_to(source.resolve())
    except ValueError: pass
    else: raise ArtifactBuildError("release output must not be inside the source repository")
    head, tree = _identity(source, git_head, git_tree)
    if not release_id or any(c in release_id for c in "\\/:"):
        raise ArtifactBuildError("invalid release id")
    entries_by_path = _tree_entries(source, head)
    selected = list(files) if files is not None else [p for p in entries_by_path if p.startswith(("apps/", "packages/", "config/", "migrations/")) or p in {"pyproject.toml", "alembic.ini", "scripts/r011_collect_inventory_readonly.ps1"}]
    selected = sorted(set(selected))
    dest = output / release_id
    if dest.exists():
        raise ArtifactBuildError("release output already exists; immutable output")
    payload = dest / "payload"
    payload.mkdir(parents=True)
    entries = []
    for rel in selected:
        if rel not in entries_by_path: raise ArtifactBuildError(f"release Git tree input missing: {rel}")
        mode, kind, oid = entries_by_path[rel]
        content = _blob_bytes(source, mode, kind, oid, rel)
        target = payload / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        entries.append({"path": rel.replace("\\", "/"), "sha256": hashlib.sha256(content).hexdigest(), "size": len(content), "role": "source"})
    inventory_identity = hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    manifest = {
        "manifest_schema": MANIFEST_SCHEMA, "release_id": release_id, "git_head": head, "git_tree": tree,
        "expected_alembic_head": expected_alembic_head, "created_at": build_timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "builder_version": builder_version, "artifact_identity": {"algorithm": "sha256", "semantic_input": "canonical-json(files)", "volatile_fields_excluded": ["created_at"], "file_inventory": inventory_identity},
        "source_baseline": {"git_head": head, "git_tree": tree}, "python_runtime": {"requires": ">=3.11", "global_site_packages": False},
        "dependency_identity": {"authority": "pyproject.toml", "file": "pyproject.toml"},
        "config_schema_version": "r011.production-config.v1", "compatibility": {"rollback": "application-only-compatible-schema"},
        "rollback": {"retain_previous": True, "automatic_db_downgrade": False}, "files": entries,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return dest

def verify_release(artifact_root: str | Path, *, expected_release_id: str | None = None, expected_head: str | None = None,
                   expected_tree: str | None = None, expected_alembic_head: str | None = None) -> dict:
    root = Path(artifact_root); mf = root / "manifest.json"
    try: manifest = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ArtifactBuildError("malformed or truncated manifest") from exc
    required = {"manifest_schema", "release_id", "git_head", "git_tree", "expected_alembic_head", "created_at", "builder_version", "artifact_identity", "source_baseline", "python_runtime", "dependency_identity", "config_schema_version", "compatibility", "rollback", "files"}
    if required - set(manifest) or manifest.get("manifest_schema") != MANIFEST_SCHEMA or not isinstance(manifest.get("files"), list):
        raise ArtifactBuildError("unsupported manifest schema")
    if expected_release_id and manifest.get("release_id") != expected_release_id: raise ArtifactBuildError("release id mismatch")
    if not isinstance(manifest.get("release_id"), str) or not manifest["release_id"]: raise ArtifactBuildError("invalid release identity")
    if any(not isinstance(manifest.get(k), str) or len(manifest[k]) != 40 for k in ("git_head", "git_tree")): raise ArtifactBuildError("invalid Git identity metadata")
    if expected_head and manifest.get("git_head") != expected_head: raise ArtifactBuildError("Git HEAD mismatch")
    if expected_tree and manifest.get("git_tree") != expected_tree: raise ArtifactBuildError("Git tree mismatch")
    if expected_alembic_head and manifest.get("expected_alembic_head") != expected_alembic_head: raise ArtifactBuildError("Alembic head mismatch")
    seen = set()
    for e in manifest["files"]:
        rel = e.get("path");
        if not isinstance(rel, str) or rel in seen or Path(rel).is_absolute() or ".." in Path(rel).parts: raise ArtifactBuildError("invalid file inventory")
        seen.add(rel); p = root / "payload" / rel
        if not p.is_file() or p.stat().st_size != e.get("size") or _sha(p) != e.get("sha256"): raise ArtifactBuildError(f"artifact file mismatch: {rel}")
    actual = {p.relative_to(root / "payload").as_posix() for p in (root / "payload").rglob("*") if p.is_file()}
    if actual != seen: raise ArtifactBuildError("unexpected or missing artifact file")
    identity = hashlib.sha256(json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    expected_identity = {"algorithm": "sha256", "semantic_input": "canonical-json(files)", "volatile_fields_excluded": ["created_at"], "file_inventory": identity}
    if manifest.get("artifact_identity") != expected_identity: raise ArtifactBuildError("whole artifact identity mismatch")
    if manifest.get("source_baseline") != {"git_head": manifest["git_head"], "git_tree": manifest["git_tree"]}: raise ArtifactBuildError("source baseline mismatch")
    return manifest

def scan_release_payload_for_paths(
    artifact_root: str | Path,
    forbidden_roots: Iterable[str | Path],
) -> tuple[dict[str, str], ...]:
    """Return payload files containing caller-supplied host-specific roots."""
    root = Path(artifact_root); manifest = verify_release(root); findings = []
    normalized_forbidden = []
    for forbidden in forbidden_roots:
        raw = str(forbidden).strip()
        if not raw: continue
        normalized = re.sub(r"/+", "/", raw.replace("\\", "/")).casefold().rstrip("/")
        if normalized: normalized_forbidden.append((raw, normalized))
    for entry in manifest["files"]:
        payload_path = root / "payload" / entry["path"]
        text = payload_path.read_bytes().decode("utf-8", errors="ignore")
        normalized_text = re.sub(r"/+", "/", text.replace("\\", "/")).casefold()
        for raw, normalized in normalized_forbidden:
            if normalized in normalized_text:
                findings.append({"path": entry["path"], "forbidden_root": raw})
    return tuple(findings)
