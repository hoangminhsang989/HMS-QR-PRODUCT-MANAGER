"""``apps/design_tokens.py`` had no test at all, and it was wrong twice.

**First defect - the status colours named statuses that do not exist.**
``STATUS_COLORS`` was keyed by names from an older status model:
``IN_PROCESS``, ``QC_CHECKED``, ``SHORTAGE``, ``PACKING`` and
``PARTIALLY_DELIVERED``. ``packages.domain.product.ProductStatus`` is a
``StrEnum`` whose value is its own name, and it has none of those five. Instead
it has ``NEW``, ``WAITING``, ``IN_PROGRESS``, ``QC_PASS`` and ``CANCELLED``,
which had no colour at all.

The consequence is not a crash, which is why it survived: the tracking window
colours a status cell with ``value in STATUS_COLORS``
(``apps/desktop/tracking_window.py:135``). Five of the eleven real statuses
never match, so they render with **no background colour** while the other six
get one - against ``DESIGN.md``'s rule that status is always text plus semantic
colour. The dict was copied from DESIGN.md's own status mapping, which carried
the same five dead names, so the document and the code agreed with each other
and both disagreed with the enum.

**Second defect - colours reached the Qt stylesheet without a token.**
``alternate-background-color: #f0f1f2`` was a surface with no declaration, and
``#ffffff`` was used as the ink on an accent fill while the token that supplied
it was named ``surface`` - the same "a token doing another token's job" mistake
that produced three contrast defects elsewhere in this product. Both are now
declared (``surface_alt``, ``on_accent``) with the values they already had, so
no pixel moved.

The third surface was the one nobody was watching: the mobile web and the portal
each grew a token guard in 2026-11-05, and this file - the authority for the
desktop - had none.
"""

from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess
import sys

from packages.domain.product import ProductStatus

from apps.design_tokens import INK, STATUS_COLORS, TOKENS, PY_SIDE_THEME


SOURCE_ROOT = Path(__file__).resolve().parents[2]
DESIGN = SOURCE_ROOT / "DESIGN.md"

_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def test_status_colors_covers_exactly_the_real_statuses():
    """Every status must have a colour, and no key may name a status that
    does not exist.

    Both directions matter. A missing key is the visible defect - the cell
    renders uncoloured. A key that names nothing is the reason it went
    unnoticed: it makes the dict look complete (11 entries, 11 statuses) while
    five of the entries can never match.
    """

    real = {member.value for member in ProductStatus}
    declared = set(STATUS_COLORS)

    assert declared == real, (
        "STATUS_COLORS and ProductStatus disagree:\n"
        f"  real statuses with no colour: {sorted(real - declared)}\n"
        f"  keys naming no real status:   {sorted(declared - real)}"
    )


def test_status_colors_only_uses_declared_tokens():
    """A colour must be *referenced* from ``TOKENS``, not merely equal to one of
    its values.

    The first version of this guard compared ``STATUS_COLORS`` values against
    ``TOKENS.values()`` and passed while the stylesheet still hardcoded
    ``#f0f1f2`` - because the fix had declared a token with that exact value, so
    the literal and the reference were indistinguishable. Comparing values
    cannot tell a token from a colour that happens to match it.

    So this reads the source and applies the same rule the web and the portal
    are held to: a colour is written **once**, in the token block, and nowhere
    else. The ``TOKENS = {...}`` block is therefore excluded, and the module
    docstring too, because it names the two colours it is describing.
    """

    literals = _HEX.findall(_code_outside_the_token_blocks())

    assert not literals, (
        "a colour is written outside the TOKENS block, so that colour now lives "
        f"in two places: {sorted(set(literals))}"
    )


def test_the_stylesheet_interpolates_tokens_rather_than_pasting_them():
    """``PY_SIDE_THEME`` is an f-string; if it were ever replaced by a pasted,
    already-resolved stylesheet, every colour would still be right and no token
    would mean anything any more.

    A typo in a key is not the risk - that raises ``KeyError`` at import, so it
    fails loudly and immediately. The risk is a stylesheet that no longer reads
    the dictionary at all, which is silent.
    """

    body = _code_outside_the_token_blocks()
    references = set(re.findall(r"TOKENS\['([\w]+)'\]", body))

    assert references, "PY_SIDE_THEME no longer interpolates any TOKENS entry"
    missing = sorted(references - set(TOKENS))
    assert not missing, f"PY_SIDE_THEME references undeclared tokens: {missing}"

    # Every colour the rendered stylesheet actually shows must be the value of a
    # token it interpolates, so a pasted colour cannot ride along.
    rendered = {value.casefold() for value in _HEX.findall(PY_SIDE_THEME)}
    from_tokens = {TOKENS[name].casefold() for name in references}
    assert rendered == from_tokens, (
        "the Qt stylesheet shows colours no referenced token produces: "
        f"{sorted(rendered - from_tokens)}"
    )


def test_every_status_ground_carries_readable_text():
    """A status cell paints dark ``text_primary`` text straight onto the ground
    and sets no foreground of its own.

    ``apps/desktop/tracking_window.py:135`` calls ``setBackground`` and nothing
    else, so the ground has to be light enough for the table's own text colour
    to read on. It used not to be: ``STATUS_COLORS`` held the *saturated*
    semantic colours (``info``, ``warning``, ``success``, ``danger``), which
    measure 2.49-3.47:1 against ``text_primary`` - ten of the eleven statuses
    below the 4.5:1 that DESIGN.md's status-mapping rule requires, and the
    defect had been there for the six statuses that were coloured before the
    key fix landed.

    ``apps/desktop/product_master_window.py`` painted the very same cells from
    its own dict of pale tints, all of which clear 9:1. The two windows
    disagreed and the paler one was right, so both now read the one dict in
    ``apps.design_tokens`` and this asserts the property that made it right.
    """

    text = TOKENS["text_primary"]
    failures = [
        f"{status}: {colour} on {text} is {_contrast(text, colour):.2f}:1"
        for status, colour in STATUS_COLORS.items()
        if _contrast(text, colour) < 4.5
    ]

    assert not failures, (
        "a status cell ground is too dark for the text the table paints on it "
        "(no foreground is set, so the ground must stay pale):\n  "
        + "\n  ".join(failures)
    )


def _contrast(foreground: str, background: str) -> float:
    """WCAG 2.1 relative-luminance contrast ratio for two ``#rrggbb`` colours."""

    def _luminance(colour: str) -> float:
        channels = []
        for index in (1, 3, 5):
            value = int(colour[index:index + 2], 16) / 255
            channels.append(
                value / 12.92 if value <= 0.03928
                else ((value + 0.055) / 1.055) ** 2.4
            )
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    light, dark = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_the_two_desktop_windows_paint_status_cells_from_one_palette():
    """``product_master_window`` used to keep its own eleven hex tints.

    The two windows painted the same status cells from two different palettes,
    which is how the tracking window came to use saturated grounds while its
    sibling used pale ones. ``product_master_window`` now derives its
    label-keyed view from ``apps.design_tokens.STATUS_COLORS``, so a change to
    a status colour is a change in one place.

    It looks the colours up by the *label* the tables display, so this also
    asserts the bridge is complete: every status must have a label, and the
    resulting map must agree with the shared one.
    """

    from apps.desktop import product_master_window as master

    derived = master.STATUS_COLORS
    expected = {
        master.STATUS_LABELS[status]: colour
        for status, colour in STATUS_COLORS.items()
    }

    assert len(derived) == len(STATUS_COLORS) == len(master.STATUS_LABELS), (
        "the desktop windows do not cover the same statuses: "
        f"{len(derived)} label-keyed, {len(STATUS_COLORS)} status-keyed, "
        f"{len(master.STATUS_LABELS)} labels"
    )
    assert derived == expected, (
        "product_master_window's status colours no longer come from "
        "apps.design_tokens.STATUS_COLORS"
    )


def test_no_desktop_file_writes_a_colour_outside_the_token_blocks():
    """The guard has to cover the surface, not just the token file.

    This is the lesson that cost three sessions. The portal got a token guard,
    then the mobile web got one, then this file got one - and each time the
    guard only read the file that declares the tokens. ``apps/desktop/`` is the
    surface; it renders from several files, and until this test existed **16
    hex literals lived in it** with nothing looking: a teal confirmation chip in
    a palette that matches neither the desktop's blue nor the web's teal, a hint
    label, four print-label and QR-glyph inks, and a ``VALIDATION_WARNING_COLOR``
    that duplicated a status ground by value.

    A guard scoped to ``design_tokens.py`` passes on all of that, because the
    token file itself is clean. The defect is always in the file that *uses* the
    colour, so the guard has to read the users.

    Two blocks are excluded: ``TOKENS`` and ``INK``. ``INK`` is separate because
    the desktop also *draws* things - the 1500-DPI print label, the faux QR glyph
    in a table cell, the Excel corner marker - and a printed label has to be dark
    ink on paper whichever way the UI theme goes. Both blocks are still the only
    places a colour may be written.
    """

    surface = sorted((SOURCE_ROOT / "apps" / "desktop").rglob("*.py"))
    assert surface, "apps/desktop contains no Python files to check"

    offenders: list[str] = []
    for path in surface:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for literal in _HEX.findall(line):
                offenders.append(
                    f"{path.relative_to(SOURCE_ROOT).as_posix()}:{number}: {literal}"
                )

    assert not offenders, (
        "the desktop surface writes colours outside apps/design_tokens.py, so "
        "they cannot be changed in one place and nothing notices when they "
        "drift:\n  " + "\n  ".join(offenders)
    )


def test_the_theme_the_desktop_applies_is_light():
    """``DESIGN.md`` names LIGHT the canonical acceptance direction
    (``CANONICAL_THEME=LIGHT``), and this tree has produced a dark palette three
    times: the portal's ``#0d1520``/``#00d2b4``, the admin page's, and a
    hand-written stylesheet in ``tracking_window`` (``#18212b`` ground,
    ``#eef4fa`` text, ``#177e70`` buttons).

    That last one never rendered - the line below it applied ``PY_SIDE_THEME``
    over it before the window was shown, which this test verifies directly - but
    it is exactly the kind of thing that starts as dead code and becomes live the
    day somebody reorders two lines. So the property is asserted, not the line.
    """

    assert _luminance(TOKENS["background"]) > 0.5, (
        f"the desktop ground {TOKENS['background']} is dark, but DESIGN.md names "
        "LIGHT as the canonical theme"
    )
    assert _luminance(TOKENS["text_primary"]) < 0.2, (
        f"the desktop text {TOKENS['text_primary']} is too light for a light ground"
    )


def test_the_tracking_window_renders_light_not_from_a_dead_dark_stylesheet():
    """Empirical, not inferred: the window is built offscreen and its effective
    palette is read back.

    The dark stylesheet this replaced was never visible, and a test that only
    grepped the source could not tell the difference between "the dark code is
    gone" and "the dark code is still there but overwritten". Only reading the
    rendered window can.

    It runs in a **subprocess** on purpose. The first version built the window in
    this process and passed on its own, then broke two tests in
    ``tests/test_desktop_license_gate.py`` that assert no top-level widget is
    visible - because a shown ``TrackingWindow`` outlives the test in the shared
    ``QApplication``. Qt state is global, so anything that creates and shows a
    window has to be kept out of the suite's process, not tidied up after.
    """

    probe = (
        "import sys;"
        "sys.path.insert(0, %r);"
        "from PySide6.QtWidgets import QApplication;"
        "from apps.desktop.tracking_window import TrackingWindow;"
        "app = QApplication([]);"
        "w = TrackingWindow();"
        "print(w.palette().color(w.backgroundRole()).name())"
    ) % str(SOURCE_ROOT)

    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=SOURCE_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
    )

    assert result.returncode == 0, (
        "could not build the tracking window offscreen:\n" + result.stderr[-600:]
    )
    ground = result.stdout.strip().splitlines()[-1]
    assert _luminance(ground) > 0.5, (
        f"the tracking window renders on a dark ground ({ground}); DESIGN.md "
        "names LIGHT canonical and every other desktop window applies PY_SIDE_THEME"
    )


def _luminance(colour: str) -> float:
    """WCAG relative luminance for a ``#rrggbb`` colour."""

    channels = []
    for index in (1, 3, 5):
        value = int(colour[index:index + 2], 16) / 255
        channels.append(
            value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _code_outside_the_token_blocks() -> str:
    """The module source with its docstring and its colour blocks removed.

    Those are the only places a hex literal is allowed to appear: the blocks are
    where colours are declared, and the docstring describes the colours it is
    talking about. ``INK`` is a block too - see
    ``test_no_desktop_file_writes_a_colour_outside_the_token_blocks``.
    """

    import ast

    source = (SOURCE_ROOT / "apps" / "design_tokens.py").read_text(encoding="utf-8")
    docstring = ast.get_docstring(ast.parse(source), clean=False) or ""

    for name in ("TOKENS", "INK"):
        block = re.search(rf"^{name} = \{{.*?^\}}", source, re.DOTALL | re.MULTILINE)
        assert block, f"design_tokens.py has no {name} = {{...}} block to exclude"
        source = source.replace(block.group(0), "", 1)

    return source.replace(docstring, "", 1)


def test_the_documented_status_mapping_names_the_same_statuses():
    """``DESIGN.md`` is the authority the code was copied from, and it was the
    stale one. It has to stay in step with the enum now that it is correct."""

    text = DESIGN.read_text(encoding="utf-8")
    section = re.search(r"## Status mapping\s*\n\s*\n(.+)", text)
    assert section, "DESIGN.md has no '## Status mapping' section"

    documented = set(re.findall(r"\b([A-Z][A-Z_]{2,})\b", section.group(1)))
    real = {member.value for member in ProductStatus}

    assert documented == real, (
        "DESIGN.md's status mapping and ProductStatus disagree:\n"
        f"  real statuses not in the document: {sorted(real - documented)}\n"
        f"  documented names that are not real statuses: {sorted(documented - real)}"
    )


def test_the_docstring_does_not_cite_a_section_that_does_not_exist():
    """The old docstring justified the palette difference by pointing at the
    "Two surfaces, two token sets" section of DESIGN.md. There is no such
    section. The real one is "Known drift - recorded, not yet reconciled", and
    the difference is not cosmetic: a citation that names a decision makes the
    drift look settled, while the actual heading says it is unreconciled and a
    product decision.

    This is the same "a document that lies" class as the toast description the
    mobile web carried in 2026-11-05. A guard that reads the citation and the
    document it cites is the only thing that catches it, because the claim is
    false in a way that reads as reassuring.
    """

    import apps.design_tokens as module

    def _normalise(text: str) -> str:
        """Compare names, not punctuation: the real heading uses an em dash and
        prose usually writes a hyphen."""

        return " ".join(text.replace("—", "-").replace("–", "-").split())

    docstring = _normalise(module.__doc__ or "")
    headings = {
        _normalise(line.lstrip("#"))
        for line in DESIGN.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("#")
    }

    cited = re.findall(r'"([^"]+)"\s+section of DESIGN\.md', docstring)
    assert cited, "the docstring no longer cites a DESIGN.md section to check"
    for name in cited:
        assert _normalise(name) in headings, (
            f"apps/design_tokens.py cites the {name!r} section of DESIGN.md, "
            f"which does not exist. Real headings: {sorted(headings)}"
        )
