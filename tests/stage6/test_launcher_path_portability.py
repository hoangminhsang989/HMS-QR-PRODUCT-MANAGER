"""Launcher and test-root portability gates.

A repository that moved between drives left its launchers pointing at drives
that no longer exist on this machine.  ``CHAY_TEST.bat`` and
``TEST_HMS_QR_SERVER.bat`` named ``H:``, and ``CHAY_WEB.bat`` named it for the
test root, so every one of them failed on a missing directory before the
application ever started - and the D2 qualification module named ``F:`` for its
pinned private runtime, which turned 18 green tests red.

Nothing in the source tree fails loudly in that situation: a ``.bat`` that
``mkdir``s a dead drive just reports success, and the D2 module resolved its
archive at import time so the failure only surfaced inside the fixture.  These
gates make the class of defect fail here instead.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

import pytest

import config.paths as paths_module
from config.paths import SOURCE_ROOT, require_test_root


ROOT = Path(__file__).resolve().parents[2]
LAUNCHERS = (
    "CHAY_DESKTOP.bat",
    "CHAY_SERVER_TOOL.bat",
    "CHAY_TEST.bat",
    "CHAY_WEB.bat",
    "KIEM_TRA_MAY_2.bat",
    "TAO_NUT_DESKTOP_HMS_QR.bat",
    "TAO_SHORTCUT_DESKTOP.bat",
    "TEST_HMS_QR_DESKTOP.bat",
    "TEST_HMS_QR_SERVER.bat",
    "THIET_LAP_SERVER_1_CLICK.bat",
)

# A bare drive letter followed by a separator, as it appears in a set/mkdir line.
DRIVE_REFERENCE = re.compile(r'(?<![A-Za-z0-9])([A-Za-z]):[\\/]')


def _launcher_text(name: str) -> str:
    path = ROOT / name
    assert path.is_file(), f"launcher {name} is missing from the repository root"
    return path.read_text(encoding="utf-8", errors="strict")


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_names_only_drives_this_machine_has(name: str) -> None:
    """Every absolute path a launcher writes to must resolve on this machine."""
    text = _launcher_text(name)
    available = {
        drive.upper()
        for drive in re.findall(r"\b([A-Za-z]):\\", text)
    }
    missing = sorted(
        drive
        for drive in available
        if not Path(f"{drive}:{os.sep}").is_dir()
    )
    assert not missing, (
        f"{name} still writes to a drive that does not exist on this machine: "
        + ", ".join(f"{drive}:" for drive in missing)
    )


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_prints_utf8_vietnamese(name: str) -> None:
    """The launchers speak Vietnamese, so cmd.exe has to be switched to 65001."""
    assert "chcp 65001" in _launcher_text(name), (
        f"{name} renders its Vietnamese text in the OEM codepage without chcp 65001"
    )


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_vietnamese_has_no_mixed_case_words(name: str) -> None:
    """A lowercase word with one uppercase Vietnamese letter is a mojibake fingerprint.

    The system ANSI codepage is 949, so a UTF-8 file round-tripped through
    PowerShell 5.1's ``Get-Content``/``Set-Content`` loses every character it
    cannot represent. What survives is not always ``?``: some letters come back
    as their uppercase counterpart, which reads as a typo rather than as damage.
    ``chưa`` became ``chƠa`` and ``quản trị`` became ``quẢn trị`` that way, in
    files that still decoded cleanly as UTF-8.

    ``Đ``/``đ`` are excluded because ``Đã`` is the correct capital form at the
    start of a sentence, and a word that is uppercase throughout is a heading,
    not damage.
    """

    text = _launcher_text(name)
    offenders = []
    # A run of Unicode letters, not an ASCII range: the horn letters that the
    # codepage round-trip damages most (U+01A0..U+01B0) sit below U+00C0, so an
    # ASCII-biased class splits "chƠa" into "ch" and "a" and sees nothing.
    for word in re.findall(r"[^\W\d_]+", text):
        # Đ/đ are excluded: every sentence that starts with one ("Đã tạo",
        # "Đang mở") is correctly mixed case in a way no other letter is.
        marked = [c for c in word if ord(c) > 127 and c not in ("\u0110", "\u0111")]
        upper = [c for c in marked if unicodedata.category(c) == "Lu"]
        lower = [c for c in marked if unicodedata.category(c) == "Ll"]
        ascii_lower = [c for c in word if c.isascii() and c.islower()]
        if upper and (lower or ascii_lower):
            offenders.append(word)
    assert not offenders, (
        f"{name} mixes case inside one Vietnamese word - the fingerprint of a "
        f"codepage round-trip: {', '.join(sorted(set(offenders)))}"
    )


# The messages a reader has to trust. A corrupted one still decodes as UTF-8 and
# still renders, so only the exact text catches it: "trẩc khi" read as plausible
# Vietnamese until it was compared against what it should say.
EXPECTED_MESSAGES = {
    "CHAY_DESKTOP.bat": (
        "echo Python 3.14 x64 chưa được cài đặt. "
        "Cài Python 3.14 trước khi mở Desktop."
    ),
    "CHAY_SERVER_TOOL.bat": "echo Python 3.14 x64 chưa được cài đặt.",
    "KIEM_TRA_MAY_2.bat": "echo Python 3.14 x64 chưa được cài đặt.",
    "TEST_HMS_QR_SERVER.bat": (
        "echo Tạo tài khoản quản trị test thất bại. "
        "Test server chưa được khởi động."
    ),
}


@pytest.mark.parametrize("name", sorted(EXPECTED_MESSAGES))
def test_launcher_vietnamese_messages_are_exact(name: str) -> None:
    """The operator-facing text must say exactly what it means to say."""

    expected = EXPECTED_MESSAGES[name]
    assert expected in _launcher_text(name), (
        f"{name} no longer contains the exact message:\n  {expected}\n"
        "A Vietnamese message that survived a codepage round-trip still looks "
        "like text; only the exact string proves it is the right text."
    )



def test_test_root_launcher_agrees_with_the_configured_root() -> None:
    """CHAY_TEST.bat must point at the same root the config layer resolves."""
    text = _launcher_text("CHAY_TEST.bat")
    match = re.search(r'set "HMS_QR_TEST_ROOT=([^"]+)"', text)
    assert match, "CHAY_TEST.bat no longer sets HMS_QR_TEST_ROOT"
    declared = Path(match.group(1))
    assert declared.is_dir(), (
        f"CHAY_TEST.bat points HMS_QR_TEST_ROOT at {declared}, which does not exist"
    )
    assert paths_module._required_absolute_path(
        paths_module.TEST_ROOT_ENV, environ={"HMS_QR_TEST_ROOT": str(declared)}
    ) == declared.resolve()
    assert require_test_root(environ={"HMS_QR_TEST_ROOT": str(declared)}).is_dir()


def test_d2_private_runtime_archive_resolves_without_an_override() -> None:
    """The pinned D2 runtime is external, so it must be found, not guessed at."""
    archive = _d2_runtime_archive()
    assert archive.is_file(), (
        f"the pinned R011 D2 private runtime was not found at {archive}; "
        "set HMS_QR_D2_RUNTIME_ARCHIVE to the current copy"
    )


def _d2_runtime_archive() -> Path:
    module = pytest.importorskip(
        "tests.stage6.test_r011_d2_os_trusted_one_shot", reason="D2 module"
    )
    return module.RUNTIME_ARCHIVE


def test_source_root_is_a_real_directory() -> None:
    """The module resolved its own root, so a stale copy cannot answer for it."""
    assert SOURCE_ROOT.is_dir()
    assert (SOURCE_ROOT / "config" / "paths.py").is_file()


# Documents a newcomer acts on. The historical records under
# docs/checkpoints, docs/authorities and docs/handoffs deliberately keep the
# paths that were true when they were written, and PROJECT_STATE.md is a
# snapshot, so none of those are scanned - rewriting history to match today's
# drive layout would destroy the only evidence of what was verified.
LIVE_DOCUMENTS = (
    "README.md",
    "docs/TEST_POLICY.md",
)


@pytest.mark.parametrize("name", LIVE_DOCUMENTS)
def test_live_documents_name_no_drive_this_machine_lacks(name: str) -> None:
    """A README that sends the reader to a dead drive fails on the first command.

    ``H:\\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`` was still the documented test
    root after the drive was gone. Nothing executes a Markdown file, so no test
    noticed; only a reader following the instructions would have.
    """

    path = ROOT / name
    assert path.is_file(), f"{name} is missing from the repository"
    text = path.read_text(encoding="utf-8")
    named = {drive.upper() for drive in DRIVE_REFERENCE.findall(text)}
    missing = sorted(
        drive for drive in named if not Path(f"{drive}:{os.sep}").is_dir()
    )
    assert not missing, (
        f"{name} tells the reader to use a drive this machine does not have: "
        + ", ".join(f"{drive}:" for drive in missing)
    )
