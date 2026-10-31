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
