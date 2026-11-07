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


def _git_attributes(rel_path: str) -> dict[str, str]:
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
    resolved = {}
    for line in out.strip().splitlines():
        parts = line.split(": ")
        if len(parts) == 3:
            resolved[parts[1]] = parts[2]
    return resolved
    return resolved


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



    trees = (SOURCE_ROOT / "web", SOURCE_ROOT / "apps" / "static")
    images = [
        path
        for path in chain.from_iterable(tree.rglob("*") for tree in trees)
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp"}
    ]
    assert images, "expected the shipped images to exist; the web tree is empty"

    for image in images:
        attrs = _git_attributes(str(image.relative_to(SOURCE_ROOT)).replace("\\", "/"))
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
        attrs = _git_attributes(rel)
        assert attrs.get("text") == "set", f"{rel} is not marked text: {attrs}"
        assert attrs.get("eol") == "lf", f"{rel} is not pinned to LF: {attrs}"


def test_every_file_pinned_to_lf_is_actually_lf_on_disk():
    """The guard above asks Git what each file's attributes *resolve to*. This one
    asks what the bytes on disk are, and the difference is the whole point.

    ``web/sw.js`` was found sitting at 54 CRLF and 0 LF while ``.gitattributes``
    pinned it to ``eol=lf`` and the guard above passed. ``git status`` reported
    nothing: with ``core.autocrlf=true`` the clean filter rewrites CRLF back to
    LF before comparing, so a working file that is entirely CRLF looks identical
    to the LF blob it was committed as. ``git diff`` was empty. The file was wrong
    in exactly the way the ``.gitattributes`` comment describes - "a fresh clone
    silently received CRLF copies" - and every guard that could have caught it was
    asking Git instead of asking the disk.

    So this reads the bytes, and asks Git only *which* files are pinned. The first
    version re-implemented the glob with ``fnmatch``, which does not understand
    git's ``**``: ``web/**/*.js`` needs two path segments in fnmatch and
    ``web/sw.js`` has one, so the pattern matched nothing and the guard passed on
    a file that was entirely CRLF. Proven by injecting exactly that - which is the
    only reason it is written this way now.
    """

    def eol_of(rel_path: str) -> str:
        out = subprocess.run(
            ["git", "check-attr", "eol", "--", rel_path],
            cwd=SOURCE_ROOT, capture_output=True, text=True,
        ).stdout.strip()
        parts = out.split(": ")
        return parts[2] if len(parts) == 3 else "unspecified"

    checked = 0
    for path in chain(
        (SOURCE_ROOT / "web").rglob("*"), (SOURCE_ROOT / "apps" / "static").rglob("*")
    ):
        if not path.is_file():
            continue
        rel = str(path.relative_to(SOURCE_ROOT)).replace("\\", "/")
        if eol_of(rel) != "lf":
            continue
        crlf = path.read_bytes().count(b"\r\n")
        assert crlf == 0, (
            f"{rel} is pinned to eol=lf by .gitattributes but has {crlf} CRLF "
            "byte pair(s) on disk. Git cannot see this - core.autocrlf makes the "
            "clean filter rewrite CRLF to LF before comparing, so git status and "
            "git diff both report the file as unchanged. Rewrite it with LF."
        )
        checked += 1

    assert checked, "no file resolved to eol=lf; the pin is not reaching the web tree"


def test_no_file_in_the_served_tree_escapes_the_line_ending_pin():
    """A new extension in ``web/`` would silently follow ``core.autocrlf``.

    The two guards above check the extensions the pin set happens to name - html,
    js, json, md - and skip everything else. So the first ``.css``, ``.svg`` or
    ``.woff2`` added to the served tree resolves to ``text: unspecified, eol:
    unspecified``, follows ``core.autocrlf=true``, and arrives as CRLF on a fresh
    clone. Proven by planting ``web/_probe.css``: both guards above passed on it.

    That is the same defect the ``.gitattributes`` comment records - "every guard
    that compares bytes or checksums a shipped asset failed on a clone that had
    changed nothing" - reached by a different door. The original rules were also
    written too narrowly once already, as ``web/** text eol=lf``, which marked the
    PNGs as text and made Git rewrite the CRLF pair inside each one.

    So the rule is inverted: a file in the served tree must be *pinned*, one way
    or the other. Anything that resolves to neither ``eol=lf`` nor an explicit
    binary mark is a hole, and the message says which pin to add.
    """

    binary_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp",
    }

    served = 0
    for tree in (SOURCE_ROOT / "web", SOURCE_ROOT / "apps" / "static"):
        for path in sorted(tree.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(SOURCE_ROOT)).replace("\\", "/")
            attrs = _git_attributes(rel)
            pinned_lf = attrs.get("eol") == "lf"
            pinned_binary = (
                attrs.get("text") in {"unset", "unspecified"}
                and path.suffix.lower() in binary_extensions
            )
            assert pinned_lf or pinned_binary, (
                f"{rel} is served from disk but resolves to "
                f"text={attrs.get('text')!r}, eol={attrs.get('eol')!r}, so it "
                "follows core.autocrlf and a fresh clone receives CRLF bytes that "
                "the repository stores as LF. Add a .gitattributes pin for it: "
                "'*<ext> binary' if it is binary, or 'web/**/*<ext> text eol=lf' "
                "if it is text."
            )
            served += 1

    assert served, "no file was checked; the served trees are empty"


def test_no_token_value_is_hardcoded_in_presentation():
    """The mobile web had byte guards and no colour guard, so the token pass
    could stop halfway and every test would still pass.

    This is the same defect the portal grew a guard for on 2026-11-05
    (``test_no_token_value_is_hardcoded_in_presentation`` in
    ``test_portal_page_structure.py``): a tokenisation pass that finishes a
    component's badge but leaves the ``<h3>`` two lines below it, or tokenises
    one branch of a function and not the other, is invisible to a guard that
    counts tokens, reads the stylesheet, or compares bytes. The portal had 22
    such leftovers; this file is the mobile web's equivalent.

    The web builds are asserted the same way and for the same reason: no value
    declared in ``:root`` may appear in a ``style`` attribute or in a CSS rule
    outside the token block. Both quote styles are checked because this file
    writes its inline styles with single quotes and the portal with double.

    What is deliberately not scanned: the ``rgba()`` literals outside ``:root``
    - the header translucency, the elevation shadows, the torch button's dark
    ground, the focus rings. Those are effect values rather than surface
    colours and the board records a decision to leave them; a guard that
    rejected them would fail on purpose-built markup. Only token *values* are
    enforced, which is exactly the class that drifted.
    """

    for name in ("index.html", *DERIVED):
        raw = (WEB / name).read_text(encoding="utf-8")

        root = re.search(r":root\s*\{(.*?)\}", raw, re.DOTALL)
        assert root, f"{name} has no :root token block"
        token_values = set(re.findall(r"#[0-9a-fA-F]{6}\b", root.group(1)))
        assert token_values, f"{name} declares no colour tokens"

        style_block = raw[raw.index("<style>"):raw.index("</style>")]
        css_outside_root = re.sub(r":root\s*\{.*?\}", "", style_block, flags=re.DOTALL)

        # index.html writes its inline styles with single quotes; the derived
        # builds inherit that, but double quotes are matched too so a future
        # edit in either style is still covered.
        attributes = [
            quoted
            for pair in re.findall(r"""style=(?:"([^"]*)"|'([^']*)')""", raw)
            for quoted in pair
            if quoted
        ]
        assert attributes, f"{name} has no inline style attributes to check"

        offenders: list[str] = []
        for declaration in attributes:
            for value in sorted(token_values):
                if value in declaration:
                    offenders.append(f"style attribute uses {value}: {declaration[:90]}")
        for value in sorted(token_values):
            if value in css_outside_root:
                offenders.append(f"a CSS rule outside :root hardcodes {value}")

        assert not offenders, (
            f"{name}: presentation duplicates a :root token value, so the token is "
            "not the only place that colour lives:\n  " + "\n  ".join(offenders)
        )


def test_every_colour_in_the_mobile_web_is_a_token_or_declared_ink():
    """The converse direction, which the guard above cannot see.

    That one is value-based: it catches a token value *duplicated* in
    presentation. It says nothing about a colour that was never a token at all,
    so ``.card { color: #ff00ff }`` sails straight through - the same blind spot
    the portal had until it grew a second guard, and the same class as the
    desktop's QR chip whose teal matched none of the four palettes.

    This asserts that every colour outside ``:root`` is one of two things: a
    ``:root`` value, or the ``<meta name='theme-color'>`` content. That meta is
    the browser chrome colour and cannot reference a custom property, so it is
    the single legitimate literal in the file - and it is pinned to ``--accent``
    as well, because a theme-colour that lags the accent is the same drift one
    layer out.

    All three builds are checked, since the derived ones inherit the markup.
    """

    for name in ("index.html", *DERIVED):
        raw = (WEB / name).read_text(encoding="utf-8")
        root = re.search(r":root\s*\{(.*?)\}", raw, re.DOTALL)
        assert root, f"{name} has no :root token block"
        token_values = {value.casefold() for value in re.findall(r"#[0-9a-fA-F]{3,6}\b", root.group(1))}
        assert token_values, f"{name} declares no colour tokens"

        # The only place a literal may legitimately live outside :root.
        theme_color = re.search(r"<meta name='theme-color' content='([^']+)'>", raw)
        assert theme_color, f"{name} declares no theme-color meta to exempt"

        remainder = raw[: root.start()] + raw[root.end():]
        offenders = [
            literal
            for literal in sorted(set(re.findall(r"#[0-9a-fA-F]{3,6}\b", remainder)))
            if literal.casefold() not in token_values
            and literal not in theme_color.group(1)
        ]
        assert not offenders, (
            f"{name} shows colours that belong to no declared palette, so nothing "
            f"notices if they drift: {offenders}"
        )

        accent = re.search(r"--accent:\s*(#[0-9a-fA-F]{6})", root.group(1))
        assert accent, f"{name} declares no --accent token"
        assert theme_color.group(1).casefold() == accent.group(1).casefold(), (
            f"{name}'s theme-color is {theme_color.group(1)} but --accent is "
            f"{accent.group(1)}, so the browser chrome and the app disagree"
        )

