"""The derived mobile-web builds must stay derivable from ``web/index.html``.

``index.html`` is the program; ``vps.html`` and ``lan.html`` are the same program
with one difference each, and both are served from disk byte-for-byte. They used
to be maintained by hand, so every theme, copy or CSS change had to be re-applied
to two more files. The task board records three separate rounds of exactly that,
and a forgotten round is silent - the LAN and VPS pages just keep the old look,
and nothing notices, because a guard can only read what is already on disk.

``scripts/build_mobile_web.py`` now performs the derivation, and these tests
regenerate into a temporary directory and demand a byte-identical result. Drift
therefore fails here instead of shipping, and the fix is one command.

The regeneration also repairs a stray CRLF: the manual edit that first split the
LAN build left ``<!-- LOGIN -->`` ending in ``\\r\\n`` while every other line in
the file ended in ``\\n``. The generated file is LF throughout, which is what
``index.html`` already was.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


SOURCE_ROOT = Path(__file__).resolve().parents[2]
WEB = SOURCE_ROOT / "web"
SOURCE = WEB / "index.html"
DERIVED = ("vps.html", "lan.html")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.build_mobile_web", *args],
        cwd=SOURCE_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_the_source_build_exists_and_is_the_largest():
    raw = SOURCE.read_bytes()
    assert raw.startswith(b"<!DOCTYPE html>") or b"<html" in raw[:512]
    assert not raw.startswith(b"\xef\xbb\xbf"), "index.html carries a UTF-8 BOM"
    for name in DERIVED:
        other = (WEB / name).read_bytes()
        assert len(other) <= len(raw), f"{name} is larger than its source"
        assert not other.startswith(b"\xef\xbb\xbf"), f"{name} carries a UTF-8 BOM"


def test_every_build_uses_one_consistent_line_ending():
    """A lone CRLF in an otherwise LF file is the fingerprint of a hand edit."""

    for name in ("index.html", *DERIVED):
        raw = (WEB / name).read_bytes()
        crlf = raw.count(b"\r\n")
        lone_lf = raw.count(b"\n") - crlf
        lone_cr = raw.count(b"\r") - crlf
        assert lone_cr == 0, f"{name} has {lone_cr} bare CR byte(s)"
        assert crlf == 0 or lone_lf == 0, (
            f"{name} mixes line endings: {crlf} CRLF and {lone_lf} LF"
        )


def test_check_mode_passes_on_the_committed_builds():
    result = _run("--check")
    assert result.returncode == 0, (
        f"the derived builds no longer match what index.html derives:\n"
        f"{result.stdout}{result.stderr}"
    )


def test_the_vps_build_is_the_source_verbatim():
    """The VPS page is served outside the LAN, so it keeps the connection screen."""

    assert (WEB / "vps.html").read_bytes() == SOURCE.read_bytes()


def test_the_lan_build_drops_the_connection_screen():
    lan = (WEB / "lan.html").read_text(encoding="utf-8")
    assert "conn-modal" not in lan
    assert "conn-origin" not in lan
    assert "hms-server-origin" not in lan
    assert "renderConnection" not in lan
    assert "openConnection" not in lan
    assert "saveConnection" not in lan
    assert "clearConnection" not in lan
    assert "<!-- LOGIN -->" in lan
    assert "function resolveServerOrigin() { return location.origin; }" in lan


def test_the_lan_build_keeps_everything_else():
    """The LAN page must not silently lose a feature the VPS page has."""

    lan = (WEB / "lan.html").read_text(encoding="utf-8")
    for marker in (
        "login-modal",
        "account-pill",
        "serverOrigin + '/tracking'",
        "serverOrigin + '/files'",
        "refreshProductCard",
        "openPartPicker",
        "selectPartFromList",
        "submitLogin",
    ):
        assert marker in lan, f"the LAN build lost {marker}"


def test_the_generator_refuses_a_source_it_cannot_derive(tmp_path):
    """A moved or renamed marker must fail loudly, not emit a half-derived page."""

    import scripts.build_mobile_web as builder

    source = SOURCE.read_text(encoding="utf-8")
    broken = source.replace(
        "      <div class='pill-btn' onclick='openConnection()'>",
        "      <div class='pill-btn' onclick='openServer()'>",
        1,
    )
    assert broken != source, "the connection chip marker was not found to break"
    with pytest.raises(builder.BuildError):
        builder.build_lan(broken)

    doubled = source.replace(
        "    function renderConnection() {", "    function renderConnection() {\n    function renderConnection() {", 1
    )
    with pytest.raises(builder.BuildError):
        builder.build_lan(doubled)


def test_the_derivation_ignores_crlf_in_the_source():
    """A CRLF checkout must derive the same page, not fail to find its markers.

    Git for Windows sets ``core.autocrlf=true`` at the system level and this
    repository had no ``.gitattributes``, so a fresh clone used to receive CRLF
    copies of files stored as LF. The generator then matched none of its
    line-exact markers and reported "found 0", which reads exactly like the
    source having been edited. Normalising makes the result depend on content
    rather than on how the checkout happened.
    """

    import scripts.build_mobile_web as builder

    source = SOURCE.read_text(encoding="utf-8")
    crlf = source.replace("\n", "\r\n")
    assert crlf != source, "the source has no LF to convert"

    lan = builder.build_lan(crlf)
    assert lan == builder.build_lan(source), "CRLF changed the derivation"
    assert "\r" not in lan, "the derived build inherited a CR byte"
    assert "conn-modal" not in lan
    assert "<!-- LOGIN -->" in lan


def test_check_mode_passes_on_a_crlf_checkout(tmp_path, monkeypatch):
    """``--check`` must stay green when the working tree came back as CRLF.

    This is the clone-must-work case. ``.gitattributes`` pins ``web/`` to LF, so
    a conforming checkout cannot reach this state - but a hand-edited
    ``index.html`` saved by an editor that writes CRLF can, and a guard that
    only passes on the machine that produced the files guards nothing.
    """

    import scripts.build_mobile_web as builder

    staged = tmp_path / "web"
    staged.mkdir()
    for name in ("index.html", *DERIVED):
        text = (WEB / name).read_text(encoding="utf-8")
        (staged / name).write_text(text.replace("\n", "\r\n"), encoding="utf-8")
    assert b"\r\n" in (staged / "index.html").read_bytes(), "the fixture is not CRLF"

    monkeypatch.setattr(builder, "WEB_DIR", staged)
    result = _run("--check")
    assert result.returncode == 0, (
        f"a CRLF working tree broke the drift guard:\n{result.stdout}{result.stderr}"
    )


def test_gitattributes_pins_the_web_tree_to_lf():
    """The fix for the clone case, asserted rather than assumed.

    ``core.autocrlf=true`` is a system-level Git for Windows default, so the
    checkout cannot be trusted to preserve LF on its own.
    """

    attributes = SOURCE_ROOT / ".gitattributes"
    assert attributes.is_file(), "no .gitattributes; web/ endings follow the host"
    rules = [
        line.strip()
        for line in attributes.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert "web/** text eol=lf" in rules, f"web/ is not pinned to LF: {rules}"

