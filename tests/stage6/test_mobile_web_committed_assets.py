"""The mobile-web builds the server reads from disk must be committed.

``apps/mobile/web.py`` reads ``web/index.html``, ``web/lan.html`` and
``web/vps.html`` with ``read_bytes`` at request time, and answers 503 with a
"Thiếu tệp" page when one is missing. ``index.html`` has always been committed,
but the two derived builds were not: the Task 5 / Task 6 plan in
``docs/superpowers/plans/2026-10-28-ban-quyen-server-tool-2-duong-ket-noi.md``
ends with ``git add web/lan.html ...``, and that step was never run.

The consequence is invisible on the machine that produced them and total
anywhere else: a fresh clone - CI, a second factory machine, a redeploy - has no
``lan.html`` and no ``vps.html``, so ``GET /tracking/mobile/lan`` and
``GET /tracking/mobile/vps`` both answer 503 while ``/tracking/mobile`` and ``/``
keep working. Nothing in the suite noticed, because every guard reads the
working tree, and the working tree has the files.

The invariant is therefore checked against ``HEAD`` rather than the index: a
fresh clone is what has to work, and ``git add`` alone does not make that true.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


SOURCE_ROOT = Path(__file__).resolve().parents[2]
WEB = SOURCE_ROOT / "web"

# Every page the server serves straight from disk, and the assets it references.
SERVED_FROM_DISK = (
    "index.html",
    "lan.html",
    "vps.html",
    "manifest.json",
    "sw.js",
    "static/favicon.png",
    "static/icon-192.png",
    "static/icon-512.png",
    "static/jsqr.min.js",
)


def _committed_paths() -> set[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", "--name-only"],
        cwd=SOURCE_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        pytest.skip(f"could not read HEAD: {result.stderr.strip()[:200]}")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


@pytest.mark.parametrize("relative", SERVED_FROM_DISK)
def test_every_served_mobile_asset_is_committed(relative: str):
    """A fresh clone must be able to serve the mobile app, not just this one."""

    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    path = WEB / relative
    assert path.is_file(), f"{relative} is missing from the working tree"
    assert f"web/{relative}" in _committed_paths(), (
        f"web/{relative} exists here but is not committed, so a fresh clone "
        f"cannot serve it. Commit it (the Task 5/Task 6 plan already asked for "
        f"`git add web/{relative}`)."
    )


def test_no_file_under_web_is_left_uncommitted():
    """Anything the server can read from ``web/`` has to travel with the repo."""

    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    committed = _committed_paths()
    present = {
        item.relative_to(WEB).as_posix()
        for item in WEB.rglob("*")
        if item.is_file()
    }
    assert present, "web/ contains no files at all"
    uncommitted = sorted(name for name in present if f"web/{name}" not in committed)
    assert not uncommitted, (
        "these files exist under web/ but are not committed, so a fresh clone "
        "serves a 503 for them:\n  " + "\n  ".join(uncommitted)
    )


def test_every_gitignore_that_protects_a_large_tree_is_itself_committed():
    """An ignore file is only as durable as its own commit.

    ``installer/wheels/.gitignore`` holds one line, ``*.whl``, and
    ``installer/python/.gitignore`` holds one line, ``*.exe``. Between them they
    keep 331 MB out of the repository - a 160 MB PySide6 wheel, a 73 MB one, a
    42 MB one and a 29 MB Python installer executable among nine binaries. The
    root ``.gitignore`` does not mention ``installer/`` at all, so those two
    two-line files are the entire protection.

    Nothing checked that. If either were deleted, or left uncommitted by a
    refactor, the next ``git add -A`` would commit a third of a gigabyte of
    wheels and nothing would say so until the push. That is the same shape as the
    defect this file exists for: something invisible on the machine that produced
    it and total anywhere else.

    So each ignore file is asked for directly. ``check-ignore`` tells us which
    rule is doing the work, and ``ls-tree HEAD`` tells us whether that rule
    travels with the repository.
    """

    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    committed = _committed_paths()
    assert committed, "could not read HEAD"

    ignore_files = []
    for path in SOURCE_ROOT.rglob(".gitignore"):
        if not path.is_file():
            continue
        relative = path.relative_to(SOURCE_ROOT).as_posix()
        # an ignore file inside an already-ignored tree is ignored itself, and
        # that is correct: .opencode/.gitignore belongs to the agent, not here
        hidden = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=SOURCE_ROOT, capture_output=True, timeout=60,
        )
        if hidden.returncode == 0:
            continue
        ignore_files.append(relative)

    ignore_files.sort()
    assert ignore_files, "the repository has no .gitignore files at all"

    uncommitted = sorted(name for name in ignore_files if name not in committed)
    assert not uncommitted, (
        "these .gitignore files are not committed, so a fresh clone has none of "
        "their rules and the files they hide become committable:\n  "
        + "\n  ".join(uncommitted)
        + "\n  Commit them. `installer/wheels/.gitignore` and "
        "`installer/python/.gitignore` between them keep 331 MB of wheels and a "
        "Python installer out of the repository."
    )


def test_no_large_file_is_left_unignored():
    """The 331 MB of installer binaries are only safe while something hides them.

    The audit that found them read 331 MB of wheel as UTF-8 text and raised
    ``MemoryError`` - three guards did, once the directory had grown. They are
    ignored today, by two nested ``.gitignore`` files, and that is checked above.
    This is the other half: if a large file ever ends up neither tracked nor
    ignored, it is one ``git add -A`` away from the repository, and nothing
    currently says so.

    The threshold is deliberately large. A source file of a few hundred kilobytes
    is not a problem; a 42 MB wheel is.
    """

    if shutil.which("git") is None:
        pytest.skip("git is not installed")

    threshold = 8 * 1024 * 1024
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=SOURCE_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert tracked.returncode == 0, f"could not list tracked files: {tracked.stderr[:200]}"
    tracked_set = {line.strip() for line in tracked.stdout.splitlines() if line.strip()}

    exposed = []
    for path in SOURCE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size <= threshold:
            continue
        relative = path.relative_to(SOURCE_ROOT).as_posix()
        if relative in tracked_set:
            continue
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=SOURCE_ROOT,
            capture_output=True,
            timeout=60,
        )
        if ignored.returncode == 0:
            continue
        exposed.append((size, relative))

    exposed.sort(reverse=True)
    assert not exposed, (
        "these large files are neither tracked by git nor ignored, so the next "
        "`git add -A` would commit them:\n  "
        + "\n  ".join(f"{size / 1024 / 1024:.1f} MB  {name}" for size, name in exposed)
        + "\n  Add a .gitignore rule for them, or delete them."
    )
