"""R011-WP1A-R1A canonical Git-object artifact remediation tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

import packages.deployment.artifact as artifact_module
from packages.deployment.artifact import ArtifactBuildError, build_release, verify_release


def _run(cwd: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(list(args), cwd=cwd, input=input_bytes, capture_output=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr.decode("utf-8", "replace"))
    return result.stdout


def _repository(root: Path) -> Path:
    repo = root / "source"
    repo.mkdir()
    _run(repo, "git", "init", "-q")
    _run(repo, "git", "config", "user.name", "R1A Test")
    _run(repo, "git", "config", "user.email", "r1a@example.invalid")
    _run(repo, "git", "config", "core.autocrlf", "false")
    (repo / ".gitattributes").write_bytes(b"normal.txt text\nfixture.bin -text\nmixed.txt -text\n")
    (repo / "pyproject.toml").write_bytes(b"[project]\nname='r1a-fixture'\n")
    (repo / "normal.txt").write_bytes(b"alpha\nbeta\ngamma\n")
    (repo / "fixture.bin").write_bytes(bytes(range(256)) + b"\x00\r\n\xff")
    (repo / "mixed.txt").write_bytes(b"alpha\r\nbeta\ngamma\rcoda\x00")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "r011_collect_inventory_readonly.ps1").write_bytes(b"Set-StrictMode -Version Latest\n'fixture'\n")
    _run(repo, "git", "add", ".")
    _run(repo, "git", "commit", "-qm", "fixture")
    return repo


def _clone(source: Path, target: Path, *, autocrlf: bool, eol: str) -> Path:
    _run(target.parent, "git", "clone", "-q", "-n", "--no-hardlinks", str(source), str(target))
    _run(target, "git", "config", "core.autocrlf", "true" if autocrlf else "false")
    _run(target, "git", "config", "core.eol", eol)
    _run(target, "git", "checkout", "-q", "-f", "HEAD")
    assert not _run(target, "git", "status", "--porcelain")
    return target


def test_cross_checkout_eol_invariance_and_exact_blob_preservation(tmp_path):
    source = _repository(tmp_path)
    clone_crlf = _clone(source, tmp_path / "clone-crlf", autocrlf=True, eol="crlf")
    clone_lf = _clone(source, tmp_path / "clone-lf", autocrlf=False, eol="lf")
    assert b"\r\n" in (clone_crlf / "normal.txt").read_bytes()
    assert b"\r\n" not in (clone_lf / "normal.txt").read_bytes()

    selected = ["pyproject.toml", "normal.txt", "fixture.bin", "mixed.txt"]
    a = build_release(clone_crlf, tmp_path / "build-a", release_id="same", files=selected, build_timestamp="2026-08-16T00:00:00+00:00")
    b = build_release(clone_lf, tmp_path / "build-b", release_id="same", files=selected, build_timestamp="2026-08-16T00:00:00+00:00")
    manifest_a, manifest_b = verify_release(a), verify_release(b)
    assert manifest_a == manifest_b
    assert manifest_a["artifact_identity"] == manifest_b["artifact_identity"]

    for name in ("normal.txt", "fixture.bin", "mixed.txt"):
        canonical = _run(source, "git", "cat-file", "blob", f"HEAD:{name}")
        payload = (a / "payload" / name).read_bytes()
        entry = next(item for item in manifest_a["files"] if item["path"] == name)
        assert payload == canonical
        assert entry["size"] == len(canonical)
        assert entry["sha256"] == hashlib.sha256(canonical).hexdigest()


def test_requested_head_and_tree_mismatch_fail_closed(tmp_path):
    repo = _repository(tmp_path)
    parent = _run(repo, "git", "rev-parse", "HEAD").decode().strip()
    (repo / "normal.txt").write_bytes(b"second\n")
    _run(repo, "git", "add", "normal.txt")
    _run(repo, "git", "commit", "-qm", "second")
    with pytest.raises(ArtifactBuildError):
        build_release(repo, tmp_path / "wrong-head", release_id="bad", files=["normal.txt"], git_head=parent)
    with pytest.raises(ArtifactBuildError):
        build_release(repo, tmp_path / "wrong-tree", release_id="bad", files=["normal.txt"], git_tree="0" * 40)


def test_dirty_tracked_and_untracked_worktrees_are_refused(tmp_path):
    repo = _repository(tmp_path)
    (repo / "normal.txt").write_bytes(b"dirty\n")
    with pytest.raises(ArtifactBuildError): build_release(repo, tmp_path / "dirty-a", release_id="dirty", files=["normal.txt"])
    _run(repo, "git", "restore", "normal.txt")
    (repo / "untracked.txt").write_bytes(b"untracked")
    with pytest.raises(ArtifactBuildError): build_release(repo, tmp_path / "dirty-b", release_id="dirty", files=["normal.txt"])


def test_git_object_read_failure_has_no_worktree_fallback(tmp_path, monkeypatch):
    repo = _repository(tmp_path)
    original = artifact_module._git_bytes
    def fail_blob(root, *args):
        if args[:2] == ("cat-file", "blob"):
            raise ArtifactBuildError("injected object read failure")
        return original(root, *args)
    monkeypatch.setattr(artifact_module, "_git_bytes", fail_blob)
    assert (repo / "normal.txt").is_file()
    with pytest.raises(ArtifactBuildError, match="injected object read failure"):
        build_release(repo, tmp_path / "object-failure", release_id="fail", files=["normal.txt"])


def test_missing_path_and_unsupported_tree_mode_fail_closed(tmp_path):
    repo = _repository(tmp_path)
    with pytest.raises(ArtifactBuildError, match="Git tree input missing"):
        build_release(repo, tmp_path / "missing", release_id="missing", files=["absent.txt"])

    oid = _run(repo, "git", "hash-object", "-w", "--stdin", input_bytes=b"normal.txt").decode().strip()
    _run(repo, "git", "update-index", "--add", "--cacheinfo", f"120000,{oid},synthetic-link")
    _run(repo, "git", "commit", "-qm", "add synthetic symlink entry")
    clone = _clone(repo, tmp_path / "symlink-clone", autocrlf=False, eol="lf")
    with pytest.raises(ArtifactBuildError, match="unsupported Git tree entry"):
        build_release(clone, tmp_path / "unsupported", release_id="unsupported", files=["synthetic-link"])


def test_semantic_identity_documents_timestamp_exclusion(tmp_path):
    repo = _repository(tmp_path)
    first = build_release(repo, tmp_path / "time-a", release_id="same", files=["pyproject.toml"], build_timestamp="2026-08-16T00:00:00+00:00")
    second = build_release(repo, tmp_path / "time-b", release_id="same", files=["pyproject.toml"], build_timestamp="2026-08-16T00:01:00+00:00")
    a, b = verify_release(first), verify_release(second)
    assert a["created_at"] != b["created_at"]
    assert a["artifact_identity"] == b["artifact_identity"]
    assert a["artifact_identity"]["semantic_input"] == "canonical-json(files)"
    assert a["artifact_identity"]["volatile_fields_excluded"] == ["created_at"]


def test_default_inventory_includes_readonly_collector_from_git_blob(tmp_path):
    repo = _repository(tmp_path)
    release = build_release(repo, tmp_path / "default-build", release_id="default", build_timestamp="2026-08-16T00:00:00+00:00")
    manifest = verify_release(release)
    path = "scripts/r011_collect_inventory_readonly.ps1"
    entry = next(item for item in manifest["files"] if item["path"] == path)
    canonical = _run(repo, "git", "cat-file", "blob", f"HEAD:{path}")
    assert (release / "payload" / path).read_bytes() == canonical
    assert entry["sha256"] == hashlib.sha256(canonical).hexdigest()
    assert entry["size"] == len(canonical)
