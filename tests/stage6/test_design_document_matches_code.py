"""``DESIGN.md`` claims to be the design system. Nothing checked that it was.

Its YAML front-matter declares two palettes - ``colors`` for the web and portal,
``desktop_colors`` for the PySide6 desktop - plus typography, radii, spacing and
shadows. It reads as the authority, and the body of the document even tells
agents to "read the right one for the surface they are editing".

Every colour guard in this tree compares code against code: ``:root`` against
presentation, ``TOKENS`` against the files that use it, one surface against
another. **None of them read the document.** So when the code grew and the
document did not, nothing said so.

That had already happened, twice over, by the time this file was written:

- ``desktop_colors`` declared 12 colours while ``apps/design_tokens.py`` had
  grown to 27. The eleven status cell grounds, the QR copy confirmation chip,
  the formula hint label and ``surface_alt`` were all missing - most of them
  added in the sessions that fixed the desktop's palette, none of which thought
  to update the document that describes it.
- ``:root`` carried ``--violet: #5b21b6`` - the "Đã giao" colour - and ``colors``
  did not declare it, which is the same drift that let that one status ship as
  two different purples on two surfaces.

The document is now in step, and this keeps it there. Both directions are
asserted, because a document that declares a colour the code does not use is as
wrong as code that uses a colour the document does not declare.

Only the two palettes the front-matter actually claims are checked. The Server
Tool and the LAN admin page are deliberately outside it: they are described in
the body of DESIGN.md with their own token blocks, and folding them into the
front-matter would be the product decision the body explicitly defers.
"""

from __future__ import annotations

from pathlib import Path
import re

from apps.design_tokens import STATUS_COLORS, TOKENS


SOURCE_ROOT = Path(__file__).resolve().parents[2]
DESIGN = SOURCE_ROOT / "DESIGN.md"
PORTAL = SOURCE_ROOT / "apps" / "server" / "portal.py"

_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def _front_matter() -> str:
    source = DESIGN.read_text(encoding="utf-8")
    assert source.startswith("---"), "DESIGN.md has no YAML front-matter"
    end = source.index("\n---", 3)
    return source[:end]


def _block(name: str) -> dict[str, str]:
    """A flat ``key: "value"`` mapping from one top-level front-matter block."""

    matter = _front_matter()
    match = re.search(rf"^{name}:\n((?:  \S.*\n)+)", matter, re.MULTILINE)
    assert match, f"DESIGN.md front-matter has no {name} block"
    return dict(re.findall(r'^  (\w+): "([^"]+)"', match.group(1), re.MULTILINE))


def _portal_root_values() -> set[str]:
    source = PORTAL.read_text(encoding="utf-8")
    start = source.index(":root")
    block = source[start:source.index("}", source.index("--on-accent", start)) + 1]
    return {value.casefold() for value in _HEX.findall(block)}


def test_the_front_matter_declares_the_palettes_it_claims():
    """Otherwise every assertion below is checking nothing."""

    web = _block("colors")
    desktop = _block("desktop_colors")
    status = _block("desktop_status_colors")

    assert web, "DESIGN.md front-matter declares no web colours"
    assert desktop, "DESIGN.md front-matter declares no desktop colours"
    assert status, "DESIGN.md front-matter declares no desktop status colours"
    # ``background_gradient`` and ``primary_dim`` are effects, not colours, and
    # are allowed to be non-hex for the same reason ``rgba()`` is not scanned
    # anywhere else in this tree. Every value that *is* a colour must be one.
    for block, values in (("colors", web), ("desktop_colors", desktop), ("desktop_status_colors", status)):
        for key, value in values.items():
            if value.startswith("#"):
                assert _HEX.fullmatch(value), f"{block}.{key} is not a #rrggbb colour: {value}"


def test_the_document_and_the_desktop_code_declare_the_same_palette():
    """``desktop_colors`` and ``desktop_status_colors`` against
    ``apps/design_tokens.py``.

    The document had drifted by fifteen colours - the eleven status grounds, the
    QR confirmation chip, the hint label and ``surface_alt`` - every one of them
    added by a fix that changed the code and left the description behind. That is
    the failure this closes: a fix that grows the palette must grow the document
    too, or the next agent reads a description that is missing half the truth.
    """

    declared = {
        value.casefold()
        for block in ("desktop_colors", "desktop_status_colors")
        for value in _block(block).values()
    }
    in_code = {
        value.casefold()
        for value in list(TOKENS.values()) + list(STATUS_COLORS.values())
    }

    assert declared == in_code, (
        "DESIGN.md's desktop palette and apps/design_tokens.py disagree:\n"
        f"  declared but not in code: {sorted(declared - in_code)}\n"
        f"  in code but not declared: {sorted(in_code - declared)}"
    )


def test_the_document_and_the_web_code_declare_the_same_palette():
    """``colors`` against the portal's ``:root``.

    ``--violet`` was the drift: the "Đã giao" colour lived in ``:root`` on both
    web surfaces and in neither the document nor, for a while, in agreement with
    the desktop's green. A colour that only one surface declares is how one
    status becomes two colours.
    """

    declared = {value.casefold() for value in _block("colors").values() if _HEX.fullmatch(value)}
    in_code = _portal_root_values()

    assert declared == in_code, (
        "DESIGN.md's web palette and the portal :root disagree:\n"
        f"  declared but not in :root: {sorted(declared - in_code)}\n"
        f"  in :root but not declared: {sorted(in_code - declared)}"
    )


def test_the_two_documented_palettes_are_distinct():
    """The document describes two palettes on purpose - DESIGN.md's body says the
    desktop and the web are "deliberately different palettes" and warns agents
    never to "fix" one toward the other. If the two blocks ever collapsed into
    one set of values, that warning would be describing something that no longer
    exists, and a future merge would look already-done.

    This is a **message-clarity check, not independent coverage**, and it is worth
    saying so plainly: collapsing the document's desktop palette necessarily
    breaks the document-versus-code match above as well, so the failure is caught
    either way. What this adds is the sentence that explains *why* it is wrong,
    instead of a diff that just says two sets of colours differ. The RED run that
    produced it confirmed this - the injected collapse failed on the match
    assertion, not this one.
    """

    web = {value.casefold() for value in _block("colors").values() if _HEX.fullmatch(value)}
    desktop = {value.casefold() for value in _block("desktop_colors").values() if _HEX.fullmatch(value)}

    assert web != desktop, (
        "DESIGN.md's web and desktop palettes are now identical, but its body "
        "describes them as deliberately different"
    )
    # A little overlap is expected (white surfaces, shared neutrals); wholesale
    # identity is not.
    assert len(web & desktop) < len(web) / 2, (
        f"the two palettes share {len(web & desktop)} of {len(web)} web colours, "
        "which is more overlap than 'deliberately different' allows"
    )


def _top_block(name: str) -> str:
    """Everything under a top-level front-matter key, up to the next one.

    The regex a flat ``^  key: "value"`` scan uses stops dead on this document's
    nested blocks - ``typography`` indents its ``fontSize`` four spaces, under a
    ``body:`` key - which is why the first version of this helper reported the
    type scale as empty and flagged every font size on both surfaces as
    undeclared. The scale was right; the parser was not.
    """

    matter = _front_matter()
    start = matter.index(f"\n{name}:") + 1
    rest = matter[start:]
    following = re.search(r"^\S", rest[rest.index("\n"):], re.MULTILINE)
    return rest[: rest.index("\n") + 1 + (following.start() if following else len(rest))]


def test_the_webs_font_sizes_are_exactly_the_declared_type_scale():
    """The one axis that was already right, so it is worth locking in.

    The front-matter's ``typography`` block declares six sizes - 11, 12, 13, 15,
    16 and 18px - and ``web/index.html`` uses **exactly those six and no others**.
    Nothing asserted that, and the radius axis had already drifted, so an
    unguarded match is not evidence of a stable one.

    Only the web is checked. The portal uses five sizes off the scale (10, 14,
    17, 19 and 28px) and the spacing scale is off by more still; both are recorded
    in DESIGN.md as decisions to make rather than guessed at here, exactly as the
    radius gaps are.
    """

    declared = set(re.findall(r'fontSize:\s*"(\d+)px"', _top_block("typography")))
    assert declared, "DESIGN.md's typography block declares no font sizes"

    web = (SOURCE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    used = set(re.findall(r"font-size:\s*(\d+)px", web))

    assert used == declared, (
        "the web's font sizes and DESIGN.md's type scale disagree:\n"
        f"  declared but unused: {sorted(declared - used)}\n"
        f"  used but undeclared: {sorted(used - declared)}"
    )


def test_every_status_the_desktop_colours_is_declared_in_the_document():
    """``desktop_status_colors`` is keyed by ``ProductStatus`` member name for the
    same reason ``STATUS_COLORS`` is: a lookup by name cannot silently miss. The
    document used to be the stale one here too, so the key set is checked against
    the enum rather than against the code's dict.
    """

    from packages.domain.product import ProductStatus

    documented = set(_block("desktop_status_colors"))
    real = {member.name for member in ProductStatus}

    assert documented == real, (
        "DESIGN.md's desktop status colours and ProductStatus disagree:\n"
        f"  real statuses not documented: {sorted(real - documented)}\n"
        f"  documented names that are not real statuses: {sorted(documented - real)}"
    )


def test_the_documented_card_radius_is_the_radius_the_web_declares():
    """The colour axis was not the only one that had drifted.

    ``DESIGN.md``'s front-matter declared ``rounded.card: "14px"`` while
    ``web/index.html`` declares ``--radius: 16px`` and ``.card`` reads
    ``var(--radius)``. The document contradicted **its own body**, which says the
    cards carry "16px radius" - so the front-matter was the wrong one, and the
    code was right. A reader who trusted the machine-readable block over the prose
    would have concluded the cards are 14px.

    This pins the one radius the document makes a specific claim about to the
    custom property the web actually uses. The radius axis has no token guard
    beyond this, and that gap is recorded in DESIGN.md rather than papered over:
    the same file also carries six hardcoded ``border-radius: 14px`` rules that
    bypass ``--radius``, and the portal declares nine distinct radii with no
    radius token at all. Both are the "a value duplicated where no token reaches"
    defect on a different axis, and both are product decisions to make, not
    assumptions to bake in.
    """

    web = (SOURCE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    declared = dict(re.findall(r"(--radius)\s*:\s*([0-9]+)px", web))
    assert declared, "web/index.html declares no --radius custom property"

    documented = _block("rounded")["card"]
    assert documented == f"{declared['--radius']}px", (
        f"DESIGN.md declares rounded.card {documented} but the web's --radius is "
        f"{declared['--radius']}px, and .card reads var(--radius) - so the "
        "front-matter contradicts both the code and DESIGN.md's own body, which "
        'says the cards carry "16px radius"'
    )
