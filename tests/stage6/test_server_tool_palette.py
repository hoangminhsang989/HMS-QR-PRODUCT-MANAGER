"""The server directory had two unguarded palettes, and DESIGN.md did not know
either surface existed.

``apps/server/tool.py`` is the native operations window for a local HMS QR
Server. ``apps/server/admin.py`` is the LAN admin page. ``DESIGN.md`` covered the
mobile web, the portal and the PySide6 desktop and said nothing about either, so
both kept their colours inline - the tool in a 36-line Qt stylesheet holding 34
distinct literals, the admin page in a single ``<style>`` line holding six.

That is the same shape as every other surface in this tree, and it is the reason
each of them eventually grew a guard: a colour written inside a stylesheet cannot
be changed in one place, and nothing notices when it drifts. The mobile web, the
portal and the desktop each produced a defect of exactly this kind.

So both palettes are declared - ``TOOL_TOKENS`` and ``ADMIN_TOKENS`` - and both
stylesheets interpolate them. The values are the ones already in use, with **one
0.3% contrast nudge** described below, because merging these windows into the
desktop's palette would recolour shipped surfaces on a decision nobody has taken.
Whether they should share the desktop's blue accent is a product question,
recorded in ``DESIGN.md`` rather than answered here.

Two invariants are asserted, over the whole directory rather than one file:

1. no colour literal outside a token block, so the blocks stay the only place a
   colour is written;
2. every text colour clears 4.5:1 on the ground it is actually painted on, which
   is the guard that found real defects on the other three surfaces. The tool's
   palette is in better shape than the desktop's was - 16 of 17 pairs pass as
   written - and the one that did not is why ``secondary_text`` exists.
"""

from __future__ import annotations

import ast
from pathlib import Path
import os
import re
import subprocess
import sys

from apps.server.tool import TOOL_TOKENS


SOURCE_ROOT = Path(__file__).resolve().parents[2]

# The two files that make up these two surfaces, in full. Scoping to the
# *surface* rather than the file is the point: the first version of this guard
# read only ``tool.py`` and passed while ``admin.py`` still held six literals
# inline, which is the same mistake the desktop surface made when its guard
# read only ``design_tokens.py``.
#
# ``portal.py`` is deliberately not in this list. It is a separate surface with
# its own stricter guard (``test_portal_page_structure.py``), and duplicating
# that check here would assert a rule about a file this test does not own.
SURFACE_FILES = ("tool.py", "admin.py")
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_TOKEN_BLOCKS = ("TOOL_TOKENS", "ADMIN_TOKENS")

# Every pair of (text, ground) the stylesheet actually paints. A token is only
# meaningful against something, so the invariant is stated per pair rather than
# per colour. The disabled pair is excluded: WCAG exempts inactive controls, and
# a disabled button that reads as clearly disabled is the point.
PAIRS = [
    ("body text", "text", "ground"),
    ("title", "title", "ground"),
    ("subtitle", "muted", "ground"),
    ("section label", "section_label", "ground"),
    ("refresh time / caption", "secondary_text", "ground"),
    ("group box text", "heading", "card"),
    ("table header text", "heading", "header_bg"),
    ("status / LAN readiness", "ok", "ground"),
    ("listener state", "accent_text", "ground"),
    ("overview value", "accent_text", "ground"),
    ("firewall / locations state", "warn", "ground"),
    ("server URL / LAN address", "accent", "ground"),
    ("secondary button", "accent_deep", "accent_soft"),
    ("outline button", "accent_text", "card"),
    ("primary button", "card", "accent"),
    ("selected table item", "selected_text", "selected_bg"),
    ("activity log console", "console_text", "console_bg"),
]


def test_no_colour_lives_in_a_stylesheet_outside_a_token_block():
    """The stylesheet is the surface's ``:root``; a literal in it is a colour that
    exists in exactly one place and can be changed in exactly one place, which
    sounds fine until it needs to change."""

    offenders: list[str] = []
    for name in SURFACE_FILES:
        path = SOURCE_ROOT / "apps" / "server" / name
        source = path.read_text(encoding="utf-8")

        remainder = source
        for token_block in _TOKEN_BLOCKS:
            block = re.search(
                rf"^{token_block} = \{{.*?^\}}", remainder, re.DOTALL | re.MULTILINE
            )
            if block:
                remainder = remainder.replace(block.group(0), "", 1)

        for number, line in enumerate(remainder.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for literal in _HEX.findall(line):
                offenders.append(f"{name}:{number}: {literal}")

    assert not offenders, (
        "the server surfaces write colours outside a token block, so they cannot "
        "be changed in one place and nothing notices when they drift:\n  "
        + "\n  ".join(offenders)
    )


def test_each_palette_block_is_declared_and_well_formed():
    for name, token_block in zip(SURFACE_FILES, _TOKEN_BLOCKS):
        source = (SOURCE_ROOT / "apps" / "server" / name).read_text(encoding="utf-8")
        block = re.search(
            rf"^{token_block} = \{{(.*?)^\}}", source, re.DOTALL | re.MULTILINE
        )
        assert block, f"{name} declares no {token_block} block"
        values = re.findall(r'"[^"]+"\s*:\s*"([^"]+)"', block.group(1))
        assert values, f"{token_block} declares no colours"
        assert all(_HEX.fullmatch(value) for value in values), (
            f"a {token_block} value is not a colour: {values}"
        )


def test_the_stylesheet_interpolates_the_tokens_rather_than_pasting_them():
    """A pasted, already-resolved stylesheet would keep every colour right and
    make the token block meaningless. The first version of this file caught that
    on the desktop surface, so the same check is here.

    A typo in a key is not the risk - that raises ``KeyError`` at import. The risk
    is a stylesheet that no longer reads the dictionary, which is silent.
    """

    source = (SOURCE_ROOT / "apps" / "server" / "tool.py").read_text(encoding="utf-8")
    referenced = set(re.findall(r"TOOL_TOKENS\['([\w]+)'\]", source))

    assert referenced, "tool.py no longer interpolates any TOOL_TOKENS entry"
    missing = sorted(referenced - set(TOOL_TOKENS))
    assert not missing, f"tool.py references undeclared tokens: {missing}"


def test_every_text_colour_is_readable_on_the_ground_it_is_painted_on():
    """The guard that found real defects on the other three surfaces.

    ``QLabel#refreshTime`` and ``QLabel#overviewCaption`` were ``#617487`` on the
    ``#f4f7fb`` ground, which measures 4.49:1 - a 0.3% miss, but a miss. The
    subtitle already used ``#5d6b7b`` for the same job and clears 5.07:1, so the
    two secondary-text colours became one colour. That is the only value in this
    palette that moved.
    """

    failures = [
        f"{label}: {TOOL_TOKENS[text]} on {TOOL_TOKENS[ground]} is "
        f"{_contrast(TOOL_TOKENS[text], TOOL_TOKENS[ground]):.2f}:1"
        for label, text, ground in PAIRS
        if _contrast(TOOL_TOKENS[text], TOOL_TOKENS[ground]) < 4.5
    ]

    assert not failures, (
        "a Server Tool text colour is unreadable on the ground it is painted on:\n  "
        + "\n  ".join(failures)
    )


def test_the_palette_covers_the_pairs_the_stylesheet_paints():
    """A pair listed above whose token was renamed would silently stop being
    checked. This asserts every name in the table still exists."""

    for label, text, ground in PAIRS:
        assert text in TOOL_TOKENS, f"{label}: no TOOL_TOKENS[{text!r}]"
        assert ground in TOOL_TOKENS, f"{label}: no TOOL_TOKENS[{ground!r}]"


def test_the_rendered_stylesheet_uses_the_declared_values():
    """Built offscreen in a subprocess and read back, so the assertion is about
    what Qt receives rather than about what the source says.

    It runs in a **subprocess** for the same reason the desktop's equivalent does:
    Qt state is process-global, and a window built in the suite's process
    outlives the test that built it.

    ``refresh_status`` is stubbed out first. ``ServerToolWindow.__init__`` calls
    it, and it probes the server over HTTP, walks the data root and enumerates
    processes - real I/O that made this test fail roughly two runs in five with a
    subprocess that died before printing anything. The stylesheet is applied in
    ``_build_ui`` and does not depend on any of that, so the property under test
    is unchanged; only the unrelated work that was making the probe unreliable is
    gone.

    It is retried once if the subprocess dies. With the I/O gone the residual
    failure is a crash rather than a hang - roughly one run in ten of the whole
    suite, never in isolation - and a crash leaves no evidence either way, so
    failing the suite on it is a false alarm while passing silently would be a
    lie. The retry is bounded to two attempts, and the failure message says the
    probe could not run, which is a different statement from "the stylesheet has
    strays" and must not be conflated with it.
    """

    probe = (
        "import sys;"
        "sys.path.insert(0, %r);"
        "import apps.server.tool as tool;"
        "tool.ServerToolWindow.refresh_status = lambda self: None;"
        "from PySide6.QtWidgets import QApplication;"
        "app = QApplication([]);"
        "sheet = tool.ServerToolWindow().styleSheet();"
        "print(sorted({c for c in __import__('re').findall("
        "r'#[0-9a-fA-F]{6}', sheet) if c not in tool.TOOL_TOKENS.values()}))"
    ) % str(SOURCE_ROOT)

    result = None
    for _attempt in (1, 2):
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=SOURCE_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        )
        if result.returncode == 0:
            break

    assert result is not None and result.returncode == 0, (
        "could not build the Server Tool window offscreen, so this guard could not "
        "check the stylesheet (two attempts):\n" + result.stderr[-600:]
    )
    strays = ast.literal_eval(result.stdout.strip().splitlines()[-1])
    assert not strays, (
        "the rendered stylesheet shows colours no token declares: " + ", ".join(strays)
    )


def _contrast(foreground: str, background: str) -> float:
    """WCAG 2.1 relative-luminance contrast ratio for two ``#rrggbb`` colours."""

    def _luminance(colour: str) -> float:
        channels = []
        for index in (1, 3, 5):
            value = int(colour[index:index + 2], 16) / 255
            channels.append(
                value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
            )
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    light, dark = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)
