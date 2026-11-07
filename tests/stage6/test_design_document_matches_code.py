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


def test_the_documented_desktop_axes_match_the_desktop_code():
    """``desktop_typography``, ``desktop_rounded`` and ``desktop_spacing`` against
    ``apps/design_tokens.py``.

    ``desktop_spacing`` was missing outright until this guard was written: the code
    has declared ``SPACING = {2, 4, 6, 8, 12, 16, 24, 32}`` since before the
    front-matter existed, and DESIGN.md's body has said "spacing scale
    2/4/6/8/12/16/24/32px" all along, but the machine-readable block never carried
    it. Same shape as the colour drift, one axis over: a reader who trusted the
    front-matter over the prose would have found no desktop spacing scale at all.

    The other two are checked here too because nothing checked them anywhere. They
    happened to be right - Segoe UI 13px and a 4px control radius - but the radius
    axis had already drifted once, so "happens to be right" is not a reason to
    leave it unguarded.
    """

    tokens = (SOURCE_ROOT / "apps" / "design_tokens.py").read_text(encoding="utf-8")

    # --- typography -------------------------------------------------------
    typography = _top_block("desktop_typography")
    family = re.search(r'fontFamily:\s*"([^"]+)"', typography)
    size = re.search(r'fontSize:\s*"(\d+)px"', typography)
    assert family and size, "DESIGN.md's desktop_typography block is incomplete"

    code_family = set(re.findall(r"font-family:\s*'([^']+)'", tokens))
    code_size = set(re.findall(r"font-size:\s*(\d+)px", tokens))
    assert code_family and code_size, "apps/design_tokens.py declares no desktop type"

    assert {family.group(1)} == code_family, (
        f"DESIGN.md says the desktop face is {family.group(1)!r} but the code "
        f"declares {sorted(code_family)}"
    )
    assert size.group(1) in code_size, (
        f"DESIGN.md says the desktop body is {size.group(1)}px but the code "
        f"declares {sorted(code_size)}px"
    )

    # --- control radius ---------------------------------------------------
    radius = _top_block("desktop_rounded")
    documented_radius = re.search(r'control:\s*"(\d+)px"', radius)
    assert documented_radius, "DESIGN.md's desktop_rounded block has no control radius"
    code_radius = set(re.findall(r"border-radius:\s*(\d+)px", tokens))
    assert documented_radius.group(1) in code_radius, (
        f"DESIGN.md says the desktop control radius is {documented_radius.group(1)}px "
        f"but the code declares {sorted(code_radius)}px"
    )

    # --- spacing ----------------------------------------------------------
    spacing = _top_block("desktop_spacing")
    documented_spacing = set(re.findall(r'"(\d+)":\s*"\d+px"', spacing))
    assert documented_spacing, (
        "DESIGN.md declares no desktop_spacing, though apps/design_tokens.py has "
        "SPACING and DESIGN.md's body describes the scale"
    )
    code_spacing = set(re.findall(r'"(\d+)"\s*:\s*\d+', re.search(
        r"^SPACING = \{([^}]*)\}", tokens, re.MULTILINE
    ).group(1)))

    assert documented_spacing == code_spacing, (
        "DESIGN.md's desktop spacing scale and apps/design_tokens.py disagree:\n"
        f"  declared but not in code: {sorted(documented_spacing - code_spacing, key=int)}\n"
        f"  in code but not declared: {sorted(code_spacing - documented_spacing, key=int)}"
    )


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


def test_the_documents_palette_count_matches_the_token_blocks_that_exist():
    """DESIGN.md used to claim "four palettes" and list three.

    The sentence counted correctly and omitted the LAN admin page, which has
    declared ``ADMIN_TOKENS`` since 2026-11-05. ``apps/server/admin.py`` then
    compounded it by describing its own palette as "a fifth one in the product"
    when it is the fourth. Both read as reassuring, which is what makes this the
    same class as a docstring citing a section that does not exist: a claim that
    is wrong in a way that sounds settled.

    The invariant is that the enumeration names every token block the code
    declares, and the stated count equals how many there are. A palette added to
    the code without being named here is exactly how the Server Tool and the admin
    page both escaped notice the first time.
    """

    matter = _front_matter()
    text = DESIGN.read_text(encoding="utf-8")

    # The palettes the code actually declares, keyed by the token block that
    # carries them. The mobile web and the portal share one set, so they are one
    # entry - that sharing is asserted elsewhere, not here.
    declared_blocks = {
        "desktop": (SOURCE_ROOT / "apps" / "design_tokens.py").read_text(encoding="utf-8"),
        "Server Tool": (SOURCE_ROOT / "apps" / "server" / "tool.py").read_text(encoding="utf-8"),
        "LAN admin page": (SOURCE_ROOT / "apps" / "server" / "admin.py").read_text(encoding="utf-8"),
    }
    for name, block in (("TOKENS", declared_blocks["desktop"]),
                        ("TOOL_TOKENS", declared_blocks["Server Tool"]),
                        ("ADMIN_TOKENS", declared_blocks["LAN admin page"])):
        assert re.search(rf"^{name} = \{{", block, re.MULTILINE), (
            f"the code no longer declares {name}, so this guard's map is stale"
        )

    total = len(declared_blocks) + 1  # +1 for the shared web/portal set

    sentence = re.search(
        r"The product now carries \*\*(\w+) palettes\*\*(.*?)(?:\n\n|\.\s)", text, re.DOTALL
    )
    assert sentence, "DESIGN.md no longer states how many palettes the product carries"
    words = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    stated = words.get(sentence.group(1).lower())
    assert stated is not None, f"unrecognised palette count: {sentence.group(1)!r}"
    assert stated == total, (
        f"DESIGN.md says the product carries {stated} palettes but the code "
        f"declares {total} token blocks"
    )

    # Every named palette must actually be named in the enumeration that follows.
    enumeration = sentence.group(2)
    for name in declared_blocks:
        assert name in enumeration, (
            f"DESIGN.md counts {total} palettes but its enumeration never names "
            f"the {name} palette, so a reader cannot tell which ones it means"
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


def test_the_spacing_scale_either_is_adopted_or_says_so():
    """The web's ``spacing`` block declared a scale the web does not implement.

    DESIGN.md listed xs 4px through xl 24px as though it described the web. The
    web declares **no** ``--space-*`` token at all and writes its spacing as
    fourteen distinct literals, ten of which are outside that scale - 2, 3, 5, 6,
    9, 10, 11, 14, 20 and 60px. Nothing compared the two, so a scale that was
    never adopted sat in the machine-readable block looking like one that was.

    Creating the tokens is a product decision that is still open, so this guard
    does not make it. What it does is refuse to let the document be ambiguous
    about which state we are in: while the web writes off-scale literals, the
    front-matter must carry the NOT YET ADOPTED marker; the moment someone
    removes that marker - because they adopted the scale - the guard demands the
    web actually uses only the declared values.

    So the marker is not a note to readers, it is the thing under test. Removing
    it without doing the work fails here, and doing the work without removing it
    fails here too.
    """

    matter = _front_matter()
    spacing = _block("spacing")
    assert spacing, "DESIGN.md declares no spacing block"

    web = (SOURCE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    style = web[web.index("<style>"):web.index("</style>")]
    literals: set[str] = set()
    for declaration in re.findall(
        r"\b(?:gap|row-gap|column-gap|padding|margin|padding-\w+|margin-\w+)\s*:\s*([^;}]+)",
        style,
    ):
        for pixels in re.findall(r"(\d+)px", declaration):
            literals.add(f"{pixels}px")
    off_scale = sorted(literals - set(spacing.values()), key=lambda s: int(s[:-2]))

    adopted = "NOT YET ADOPTED" not in matter
    if adopted:
        assert not off_scale, (
            "DESIGN.md's spacing scale is marked adopted, but the web writes "
            f"spacing values outside it: {off_scale}. Either adopt the scale or "
            "restore the NOT YET ADOPTED marker."
        )
    else:
        assert off_scale, (
            "DESIGN.md's spacing scale is still marked NOT YET ADOPTED, but the "
            "web now uses only declared values. Remove the marker, and this "
            "guard will hold the web to the scale from then on."
        )


def _spacing_literals(css: str) -> set[str]:
    """Every distinct pixel value written as gap, padding or margin."""

    found: set[str] = set()
    for declaration in re.findall(
        r"\b(?:gap|row-gap|column-gap|padding|margin|padding-\w+|margin-\w+)\s*:\s*([^;}]+)",
        css,
    ):
        for pixels in re.findall(r"(\d+)px", declaration):
            found.add(f"{pixels}px")
    return found


def test_the_recorded_spacing_gap_matches_the_two_surfaces():
    """The paragraph that records the spacing gap recorded numbers that did not.

    DESIGN.md said the web used "fourteen distinct values, nine of them off-scale
    (2, 6, 9, 10, 11, 14, 20, 30, 40)" and the portal "twenty, fifteen off-scale
    (1, 2, 3, 5, 6, 7, 9, 10, 11, 14, 18, 20, 22, 30, 60)". Both were wrong. The
    web's list named ``30px`` and ``40px``, which are ``width``, ``height`` and
    shadow values rather than spacing, and omitted ``3px``, ``5px`` and ``60px``,
    which are spacing. The portal's named seven values that are not spacing at
    all. Measured: the web uses fourteen distinct, ten off-scale; the portal twelve
    distinct, eight off-scale.

    A paragraph whose stated purpose is to record a gap honestly is worse than one
    that says nothing when its numbers do not reconcile, and nothing checked them.
    This measures both surfaces and compares every count and every listed value,
    so the record stays a record.

    The two counts are checked separately from the two lists because a list can be
    right while its count is wrong, and that is the harder half to notice.
    """

    text = DESIGN.read_text(encoding="utf-8")
    scale = set(_block("spacing").values())

    web_css = (SOURCE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    web_css = web_css[web_css.index("<style>"):web_css.index("</style>")]
    portal_src = (SOURCE_ROOT / "apps" / "server" / "portal.py").read_text(encoding="utf-8")
    portal_css = portal_src[portal_src.index("<style>"):portal_src.index("</style>")]

    measured = {
        "web": _spacing_literals(web_css),
        "portal": _spacing_literals(portal_css),
    }

    sentence = re.search(
        r"The web uses (\w+) distinct values, (\w+) of them off-scale \(([^)]*)\); "
        r"the portal uses (\w+), (\w+) off-scale \(([^)]*)\)",
        text,
    )
    assert sentence, (
        "DESIGN.md no longer records the spacing gap in the form this guard reads"
    )
    words = {
        "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
        "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    }

    claimed = {}
    for index, surface in ((1, "web"), (4, "portal")):
        distinct = words.get(sentence.group(index).lower())
        off_scale = words.get(sentence.group(index + 1).lower())
        assert distinct is not None and off_scale is not None, (
            f"unrecognised count for {surface}: {sentence.group(index)!r}"
        )
        listed = {f"{value.strip()}px" for value in sentence.group(index + 2).split(",")}
        claimed[surface] = (distinct, off_scale, listed)

    for surface, css in measured.items():
        distinct, off_scale, listed = claimed[surface]
        actual_distinct = len(css)
        actual_off = css - scale
        assert distinct == actual_distinct, (
            f"DESIGN.md says the {surface} uses {distinct} distinct spacing values "
            f"but it uses {actual_distinct}: {sorted(css, key=lambda s: int(s[:-2]))}"
        )
        assert off_scale == len(actual_off), (
            f"DESIGN.md says {off_scale} of the {surface}'s spacing values are "
            f"off-scale but {len(actual_off)} are: "
            f"{sorted(actual_off, key=lambda s: int(s[:-2]))}"
        )
        assert listed == actual_off, (
            f"the {surface}'s off-scale spacing values do not match the record:\n"
            f"  recorded but not spacing: {sorted(listed - actual_off)}\n"
            f"  spacing but not recorded: {sorted(actual_off - listed)}"
        )


def test_the_recorded_tokenisation_counts_match_the_two_surfaces():
    """The same paragraph recorded three more counts that were wrong.

    It said the portal used "five sizes off the declared scale — 10, 14, 17, 19
    and 28px"; the portal uses four, because ``10px`` appears nowhere. It said the
    web read a ``--shadow-*`` token for "7 of its 13 box-shadows"; the web has ten
    and reads a token in four. It said the portal read one for "0 of 7"; the zero
    is right and the seven is not - there are four.

    Each is measured here rather than trusted, for the same reason as the spacing
    paragraph: a count that is wrong in a passage whose purpose is to record a gap
    makes the record worse than nothing.

    The radius count in the same section is deliberately not folded in. The portal
    does declare nine distinct radii, but two of them - ``2px`` and ``5px`` - live
    in inline ``style`` attributes and JS template strings rather than the
    ``<style>`` block, so the claim is true only under the whole-file reading.
    Measuring the stylesheet alone gives seven. Which reading is correct is a
    question about what "declares" means, and that is a decision, not an
    assumption - so it is recorded here rather than pinned.
    """

    text = DESIGN.read_text(encoding="utf-8")

    web_css = (SOURCE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    web_css = web_css[web_css.index("<style>"):web_css.index("</style>")]
    portal_src = (SOURCE_ROOT / "apps" / "server" / "portal.py").read_text(encoding="utf-8")
    portal_css = portal_src[portal_src.index("<style>"):portal_src.index("</style>")]

    # --- portal type: off-scale font sizes
    type_scale = set()
    for match in re.finditer(r"^[ \t]+fontSize:\s*\"([^\"]+)\"", _top_block("typography"), re.MULTILINE):
        type_scale.add(match.group(1))
    assert type_scale, "DESIGN.md declares no type scale"
    portal_sizes = {
        f"{value}px" for value in re.findall(r"font-size:\s*(\d+)px", portal_css)
    }
    portal_off = portal_sizes - type_scale

    sentence = re.search(
        r"The portal uses (\w+) sizes off the declared scale — ([^.]+?)\. The web does not\.",
        text,
    )
    assert sentence, "DESIGN.md no longer records the portal's off-scale sizes"
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
    claimed = words.get(sentence.group(1).lower())
    assert claimed is not None, f"unrecognised count: {sentence.group(1)!r}"
    listed = {
        f"{value.strip().removesuffix('px')}px"
        for value in re.split(r",|\band\b", sentence.group(2))
        if value.strip()
    }
    assert claimed == len(portal_off), (
        f"DESIGN.md says {claimed} of the portal's font sizes are off-scale but "
        f"{len(portal_off)} are: {sorted(portal_off, key=lambda s: int(s[:-2]))}"
    )
    assert listed == portal_off, (
        f"the portal's off-scale font sizes do not match the record:\n"
        f"  recorded but not used: {sorted(listed - portal_off)}\n"
        f"  used but not recorded: {sorted(portal_off - listed)}"
    )

    # --- shadow tokenisation, both surfaces
    def counted(css: str) -> tuple[int, int]:
        declarations = re.findall(r"box-shadow\s*:\s*([^;}]+)", css)
        tokenised = [d for d in declarations if "var(--shadow" in d]
        return len(tokenised), len(declarations)

    web_tokens, web_total = counted(web_css)
    portal_tokens, portal_total = counted(portal_css)

    shadow = re.search(
        r"The web reads a `--shadow-\*` token for (\d+) of its (\d+) box-shadows; "
        r"the portal reads one for \*\*(\d+) of (\d+)\*\*",
        text,
    )
    assert shadow, "DESIGN.md no longer records the shadow tokenisation counts"
    assert (web_tokens, web_total) == (int(shadow.group(1)), int(shadow.group(2))), (
        f"DESIGN.md says the web reads a shadow token for {shadow.group(1)} of "
        f"{shadow.group(2)} box-shadows, but it is {web_tokens} of {web_total}"
    )
    assert (portal_tokens, portal_total) == (int(shadow.group(3)), int(shadow.group(4))), (
        f"DESIGN.md says the portal reads a shadow token for {shadow.group(3)} of "
        f"{shadow.group(4)} box-shadows, but it is {portal_tokens} of {portal_total}"
    )


def test_the_documented_shadows_are_the_shadows_the_web_declares():
    """The shadow axis was declared in the front-matter and never checked.

    ``DESIGN.md`` carries a ``shadows`` block with three exact strings, and
    ``web/index.html`` declares ``--shadow-sm/md/lg`` with the same three. All
    three match today, which is exactly why nothing noticed they were unguarded:
    an axis that happens to agree is indistinguishable from one that is enforced,
    right up until someone edits one side.

    Each value is compared whole rather than by its numbers, because a shadow is
    a compound value - ``0 4px 12px rgba(...)`` - and matching the offsets while
    missing the opacity is the kind of half-agreement that reads as agreement.
    """

    web = (SOURCE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    root = re.search(r":root\s*\{(.*?)\}", web, re.DOTALL)
    assert root, "web/index.html has no :root token block"
    declared = dict(re.findall(r"--shadow-(\w+)\s*:\s*([^;]+);", root.group(1)))
    assert declared, "web/index.html declares no --shadow-* custom properties"

    documented = _block("shadows")
    assert documented, "DESIGN.md declares no shadows block"
    assert set(documented) == set(declared), (
        f"the document and the web name different shadows: "
        f"document only {sorted(set(documented) - set(declared))}, "
        f"web only {sorted(set(declared) - set(documented))}"
    )
    for name, value in sorted(documented.items()):
        assert declared[name].strip() == value, (
            f"shadows.{name} differs: DESIGN.md declares {value!r} but the web "
            f"declares {declared[name].strip()!r}"
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
