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

from itertools import chain
from pathlib import Path
import re
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


def test_the_global_control_rule_enforces_the_44px_touch_target():
    """Every control must be at least 44px, not only the ones that remember to.

    ``DESIGN.md`` requires 44px mobile action targets. The stylesheet honoured
    that in seven specific selectors (``.pill-btn``, ``.qc-btn``,
    ``.mode-tab-btn``, ``.sample-btn``, ``.btn-cam``, ``.portal-link``,
    ``.file-link``) - and in the global ``button, input, select, textarea`` rule
    it relied on ``padding: 11px 14px`` alone, with no ``min-height``.

    That works until something overrides the padding, and two buttons did: the
    camera overlay's torch and stop buttons carry inline ``padding: 6px 14px``,
    which lands them at **31px** tall. Two more were too small without any
    override at all - the modal close glyph is 18px in an 11px-padded box, which
    is 43px *wide*, and the login modal's "Đăng xuất" is a 13px font in the same
    box, which is 41px tall.

    All four were invisible to the first audit because it measured only the
    initial page. Driving the page into the camera and login states and measuring
    every visible control found them; the fix belongs on the global rule, so that
    a future button cannot repeat the mistake by forgetting a ``min-height``.

    This asserts the global rule carries the floor. It is structural and
    deterministic - it does not need a browser - and it fails if the rule is
    ever narrowed back to padding alone.
    """

    for name in ("index.html", *DERIVED):
        raw = (WEB / name).read_text(encoding="utf-8")

        m = re.search(r"button,\s*input,\s*select,\s*textarea\s*\{([^}]*)\}", raw)
        assert m, f"{name} has no global control rule"
        shared = m.group(1)
        assert re.search(r"min-height:\s*44px", shared), (
            f"{name}: the global button/input/select/textarea rule has no 44px "
            "min-height, so any control whose padding is overridden - as the "
            "camera overlay's torch and stop buttons do - drops below the "
            "44px touch target DESIGN.md requires"
        )

        b = re.search(r"(?<![\w-])button\s*\{([^}]*)\}", raw)
        assert b, f"{name} has no button rule"
        assert re.search(r"min-width:\s*44px", b.group(1)), (
            f"{name}: the button rule has no 44px min-width, so a small glyph "
            "button such as the modal close 'x' stays narrower than the touch "
            "target (measured 43px wide)"
        )


def test_narrow_widths_do_not_truncate_the_pill_values():
    """The default pill state must be readable at 360px, the commonest phone width.

    ``.pill-btn`` is a row: label on the left, value on the right, with the value
    capped by ``.pill-btn b { max-width: 130px; overflow: hidden;
    text-overflow: ellipsis }``. The cap is deliberate - a long operator name or
    process name has to be cut somehow - but at 360px the arithmetic leaves no
    room for even the *default* value.

    Measured in Chrome at 360px: the pill is 164px wide, minus 24px padding, 8px
    gap and a 75px label, leaves **57px** for the value. ``Chưa chọn`` needs
    **65px**. So every operator, before they have picked anything, saw
    ``Chưa c…``. ``Đăng nhập`` needed 66px against 63px and was cut the same way.
    390px was short by 2px. Both are among the most common phone widths.

    An ellipsis is the right answer for a value that is genuinely too long. It is
    the wrong answer for the state every user starts in, which is not long at all
    - the container is simply too narrow to hold a label and a value side by side.

    The fix stacks the pill at <=480px so the value takes the full width, which is
    why this asserts the stacking rather than a pixel count: a browser is needed
    to measure text, and this suite is deliberately deterministic.
    """

    for name in ("index.html", *DERIVED):
        raw = (WEB / name).read_text(encoding="utf-8")

        start = raw.find("@media (max-width: 480px)")
        assert start != -1, f"{name} has no narrow-width media query"
        depth = 0
        end = start
        while end < len(raw):
            if raw[end] == "{":
                depth += 1
            elif raw[end] == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        block = raw[start : end + 1]

        assert re.search(r"\.pill-btn\s*\{[^}]*flex-direction:\s*column", block), (
            f"{name}: at <=480px the pill still lays its label and value out in a "
            "row, so a 65px value gets 57px and renders as an ellipsis"
        )
        assert re.search(r"\.pill-btn\s+b\s*\{[^}]*max-width:\s*100%", block), (
            f"{name}: the value keeps its 130px cap at narrow widths, so it is "
            "still squeezed even once the pill is stacked"
        )


def test_the_css_is_actually_inside_a_style_element():
    """The stylesheet has to reach the browser, not just exist in the file.

    ``web/index.html`` carries 463 lines of CSS - the whole design system:
    ``--accent`` teal, the 16px card radius, the status colours, the shadows. On
    2026-11-03 the opening ``<style>`` tag was gone while the closing
    ``</style>`` survived, so the HTML parser could not put those bytes in a style
    element and they became character data instead.

    Nothing noticed, because every guard here reads bytes: this file checks
    line endings, BOMs and byte-identical derivation, and the deployment tests
    check what is served. Not one of them asks whether the CSS is *applied*. The
    page shipped unstyled to production.

    Verified by measurement, not by reading. Loaded in Chrome at
    https://hms-qr-product-manager-web.vercel.app/, HTTP 200:

        styleElements: 0
        sheetCount: 0
        bodyFont: "Times New Roman"     <- the browser default, not --font
        bodyBg: "rgba(0, 0, 0, 0)"      <- no --bg-grad
        accent: ""                      <- the :root block never registered

    ``"Times New Roman"`` is the tell: it is what a page with no CSS at all looks
    like, and it is not any font this project declares.

    The assertion is structural and deterministic - it asks where the token block
    lives rather than launching a browser - so it runs everywhere and still fails
    on exactly this defect.
    """

    for name in ("index.html", *DERIVED):
        raw = (WEB / name).read_text(encoding="utf-8")
        opening = raw.count("<style")
        closing = raw.count("</style>")
        assert opening == closing, (
            f"{name} has {opening} opening <style> tag(s) but {closing} </style>; "
            "CSS outside a style element is inert text"
        )
        assert opening >= 1, f"{name} has no <style> element at all"

        # The :root token block must sit between a <style> and its </style>.
        token_at = raw.find("--accent")
        assert token_at != -1, f"{name} declares no --accent token"
        last_open = raw.rfind("<style", 0, token_at)
        assert last_open != -1, (
            f"{name} declares --accent with no <style> before it, so the browser "
            "never sees the token"
        )
        close_after = raw.find("</style>", last_open)
        assert close_after > token_at, (
            f"{name} declares --accent outside any <style> element, so the whole "
            "design system is inert"
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

    The assertion is behavioural - it asks Git what attributes each shipped file
    actually resolves to - because parsing the rule text is what let the defect
    through in the first place. The rules were first written as ``web/** text
    eol=lf``, which reads as "pin the text files to LF" but also marked the six
    PNGs under those trees as text. Each of those images carries exactly one
    CRLF byte pair in its compressed data, so Git's clean filter rewrote it and
    every fresh clone reported the six files as permanently modified - which
    made build_release refuse to build from a clone at all.

    """
    attributes = SOURCE_ROOT / ".gitattributes"
    assert attributes.is_file(), "no .gitattributes; web/ endings follow the host"

    def resolved(rel_path):
        """What Git says this one file's attributes resolve to.

        ``check-attr`` prints ``<path>: <attr>: <value>``, so the attribute name
        is the middle field - keying on the path instead silently returned the
        value of whichever line happened to come last, which is how this guard
        first passed while asserting the wrong thing.

        """
        out = subprocess.run(
            ["git", "check-attr", "text", "eol", "--", rel_path],
            cwd=SOURCE_ROOT,
            capture_output=True,
            text=True,
        ).stdout
        resolved_now = {}
        for line in out.strip().splitlines():
            parts = line.split(": ")
            if len(parts) == 3:
                resolved_now[parts[1]] = parts[2]
        return resolved_now

    trees = (SOURCE_ROOT / "web", SOURCE_ROOT / "apps" / "static")
    images = [
        path
        for path in chain.from_iterable(tree.rglob("*") for tree in trees)
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp"}
    ]
    assert images, "expected the shipped images to exist; the web tree is empty"

    for image in images:
        attrs = resolved(str(image.relative_to(SOURCE_ROOT)).replace("\\", "/"))
        assert attrs.get("text") in {"unset", "unspecified"}, (
            f"{image.name} resolves as text={attrs.get('text')!r}, so Git may rewrite "
            "the CRLF byte pair inside its binary data"
        )

    text_files = [
        path
        for path in chain.from_iterable(tree.rglob("*") for tree in trees)
        if path.is_file() and path.suffix.lower() in {".html", ".js", ".json", ".md"}
    ]
    assert text_files, "expected the shipped text assets to exist; the web tree is empty"

    for path in text_files:
        rel = str(path.relative_to(SOURCE_ROOT)).replace("\\", "/")
        attrs = resolved(rel)
        assert attrs.get("text") == "set", f"{rel} is not marked text: {attrs}"
        assert attrs.get("eol") == "lf", f"{rel} is not pinned to LF: {attrs}"

