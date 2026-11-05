"""The portal page renders as one coherent document.

Removing the VietQR payment tab deleted a nav button, a whole ``tab-pane`` and a
JavaScript function from one 3000-line f-string. Nothing renders that page and
looks at its structure, so a deletion that leaves an unclosed ``div``, a nav
button pointing at a pane that no longer exists, or a pane with no way to reach
it would ship silently - the HTML would still render, just wrong.

These tests render the real page and check the invariants that a tab deletion
can break.
"""
from __future__ import annotations

import re
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]


_EMPTY_STATS = {
    "products": 0, "pos": 0, "tracking": 0, "operators": 0, "machining": 7,
    "in_prod": 0, "qc": 0, "packed": 0, "deliv": 0,
}


def _rendered(monkeypatch) -> str:
    import apps.server.portal as portal

    monkeypatch.setattr(portal, "get_public_tunnel_url", lambda: None)
    monkeypatch.setattr(portal, "get_local_ip", lambda: "127.0.0.1")
    monkeypatch.setattr(portal, "get_stats", lambda: dict(_EMPTY_STATS))
    monkeypatch.setattr(portal, "get_live_events", lambda: [])
    return portal.render_portal_html()


def _nav_targets(html: str) -> set[str]:
    """Tabs reachable from a nav button.

    Scoped to the ``onclick`` attributes rather than the whole document, because
    ``switchTab`` builds the same string in its own source while looking the
    button up - a document-wide match counts that literal as a tab.
    """

    targets = set()
    for attribute in re.findall(r"onclick=\"([^\"]*)\"", html):
        match = re.match(r"switchTab\('([^']+)'\)$", attribute)
        if match:
            targets.add(match.group(1))
    return targets


def _pane_ids(html: str) -> set[str]:
    """``tab-live`` carries ``class="tab-pane active"``, so the class is a prefix."""

    return set(re.findall(r'<div id="([^"]+)" class="tab-pane[^"]*"', html))


def _inline_script(html: str) -> str:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "portal has no inline script"
    return "\n".join(scripts)


def test_portal_renders_without_raising(monkeypatch):
    html = _rendered(monkeypatch)
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "</html>" in html


def test_every_nav_tab_points_at_a_pane_that_exists(monkeypatch):
    """A button whose pane was deleted opens nothing - a silent dead tab."""

    html = _rendered(monkeypatch)
    missing = _nav_targets(html) - _pane_ids(html)
    assert missing == set(), f"nav buttons with no pane: {sorted(missing)}"


def test_every_pane_has_a_nav_button_to_reach_it(monkeypatch):
    """A pane no button opens is unreachable - content the operator never sees."""

    html = _rendered(monkeypatch)
    orphaned = _pane_ids(html) - _nav_targets(html)
    assert orphaned == set(), f"panes with no nav button: {sorted(orphaned)}"


def test_the_portal_has_the_tabs_it_is_supposed_to_have(monkeypatch):
    """The tab set is the contract: the four functional tabs.

    The payment tab went with the QR payment code, and the license tab went with
    the license system - nothing in the product ever consumed a license.
    """

    html = _rendered(monkeypatch)
    assert _nav_targets(html) == {
        "tab-live",
        "tab-qr",
        "tab-excel",
        "tab-connect",
    }


def test_the_removed_payment_tab_is_not_reachable(monkeypatch):
    html = _rendered(monkeypatch)
    assert "tab-payment" not in html
    assert "createPayment" not in html
    assert "payment-qr-img" not in html


def test_the_removed_license_tab_is_not_reachable(monkeypatch):
    html = _rendered(monkeypatch)
    assert "tab-license" not in html
    assert "activateLicense" not in html
    assert "license-key" not in html


def test_div_tags_are_balanced(monkeypatch):
    """An unclosed div from a deleted pane swallows the rest of the page."""

    html = _rendered(monkeypatch)
    opens = len(re.findall(r"<div\b", html))
    closes = len(re.findall(r"</div>", html))
    assert opens == closes, f"{opens} <div> vs {closes} </div>"


def test_the_inline_script_parses(monkeypatch):
    """A syntax error kills every function on the page while HTML still renders."""

    import subprocess
    import tempfile

    html = _rendered(monkeypatch)
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "portal has no inline script"
    with tempfile.TemporaryDirectory() as tmp:
        for index, body in enumerate(scripts):
            path = Path(tmp) / f"portal-{index}.js"
            path.write_text(body, encoding="utf-8")
            result = subprocess.run(
                ["node", "--check", str(path)], capture_output=True, text=True
            )
            assert result.returncode == 0, (
                f"portal inline script {index} does not parse: {result.stderr}"
            )


def test_switch_tab_does_not_depend_on_the_global_event(monkeypatch):
    """``switchTab`` must work when called, not only when clicked.

    It used to activate ``event.currentTarget``. That implicit global exists only
    inside an inline onclick handler, so the five nav buttons worked while any
    programmatic call threw ``ReferenceError: event is not defined`` - proven by
    driving the rendered page in a real browser. The button is now found by the
    tab it opens, which is the same element the handler's currentTarget was.
    """

    html = _rendered(monkeypatch)
    body = _inline_script(html)
    assert "event.currentTarget" not in body, (
        "switchTab still activates the implicit global event"
    )
    assert "getAttribute('onclick')" in body, (
        "switchTab no longer resolves the button it was invoked from"
    )


def test_no_token_value_is_hardcoded_in_presentation(monkeypatch):
    """A token pass that stops halfway is invisible to every other guard.

    The portal was moved onto its ``:root`` token set twice - 2026-11-01 when it
    came off the dark palette, and 2026-11-03 when the mobile web did. Both times
    the pass was *almost* complete, and both times it stopped in the middle of a
    single component: the Cloudflare card's "TOÀN CẦU + CAMERA" badge was
    tokenized while the ``<h3>`` two lines below it kept ``color:#047857``; the
    tunnel-status bar's failure branch used ``var(--danger)`` while its success
    branch three lines above kept ``'#047857'``; the progress legend's swatches
    became tokens while the ``<b>`` beside each swatch kept the literal.

    Nothing catches that. A guard that reads the CSS sees a tokenised stylesheet;
    a guard that counts tokens sees all of them declared; the page renders fine.
    The value is simply duplicated in a place no token reaches, so changing
    ``--success`` later would silently leave the old colour behind.

    This asserts that no value declared in ``:root`` appears in *presentation* -
    a ``style=""`` attribute or a CSS rule outside the token block. It is
    deliberately not the whole document: ``<meta name="theme-color">``,
    ``<input type="color" value="...">`` and the colour-picker's SVG ``fill``
    cannot reference a custom property, and forcing them to would be wrong.
    """

    html = _rendered(monkeypatch)

    root = re.search(r":root\s*\{(.*?)\}", html, re.DOTALL)
    assert root, "portal has no :root token block"
    token_values = set(re.findall(r"#[0-9a-fA-F]{6}\b", root.group(1)))
    assert token_values, "portal :root declares no colour tokens"

    style_block = html[html.index("<style>"):html.index("</style>")]
    css_outside_root = re.sub(r":root\s*\{.*?\}", "", style_block, flags=re.DOTALL)

    offenders: list[str] = []
    for declaration in re.findall(r'style="([^"]*)"', html):
        for value in sorted(token_values):
            if value in declaration:
                offenders.append(f"style attribute uses {value}: {declaration[:90]}")
    for value in sorted(token_values):
        if value in css_outside_root:
            offenders.append(f"a CSS rule outside :root hardcodes {value}")

    assert not offenders, (
        "portal presentation duplicates a :root token value, so the token is not "
        "the only place that colour lives:\n  " + "\n  ".join(offenders)
    )


def test_the_two_surfaces_declare_the_same_value_for_every_shared_token(monkeypatch):
    """Two surfaces disagreeing about one colour is how a third palette starts.

    It has happened twice here. On 2026-11-01 the portal had drifted to a dark
    palette of its own (``--bg: #0d1520``, ``--accent: #00d2b4``) that
    ``DESIGN.md`` never covered - the same failure that took the admin page, and
    the same shape: a surface escapes the authority because nothing compares it
    to the authority. Then "Đã giao" shipped as **two different purples**,
    ``#6d28d9`` in the portal and ``#5b21b6`` in the mobile web, because the two
    surfaces had no shared declaration to disagree with.

    ``DESIGN.md`` names the mobile web as the authority for the shared tokens:
    the portal's ``:root`` "carries the same light tokens as the mobile web - it
    is not a third palette". This asserts exactly that, and it is the guard that
    was missing both times.

    Two clauses, because catching a *contradiction* is not the same as catching a
    *replacement*:

    1. every token the portal declares must also exist on the mobile web, so the
       shared core cannot quietly empty out and leave two disjoint palettes that
       technically "never disagree";
    2. every shared token must carry the same value, so one status cannot become
       two colours.

    The mobile web legitimately carries more than the portal does - shadows,
    chip borders, the camera laser, the scrim - so only the portal's side is
    required to be a subset. Today that is 22 of the web's 42, and they agree on
    all 22.
    """

    portal_root = _token_block(_rendered(monkeypatch))
    web_root = _token_block(
        (SOURCE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    )

    assert portal_root, "portal declares no :root tokens"
    assert web_root, "web/index.html declares no :root tokens"

    portal_only = sorted(set(portal_root) - set(web_root))
    assert not portal_only, (
        "the portal declares tokens the mobile web does not, so the shared core "
        f"can diverge without either side noticing: {portal_only}"
    )

    contradictions = [
        f"--{name}: portal={portal_root[name]!r} vs web={web_root[name]!r}"
        for name in sorted(set(portal_root) & set(web_root))
        if portal_root[name] != web_root[name]
    ]
    assert not contradictions, (
        "the two surfaces disagree about a shared colour, so one status is two "
        "colours across the product:\n  " + "\n  ".join(contradictions)
    )


def _token_block(html: str) -> dict[str, str]:
    """``--name: value`` for the ``:root`` block, whitespace-normalised."""

    root = re.search(r":root\s*\{(.*?)\}", html, re.DOTALL)
    if not root:
        return {}
    return {
        name: " ".join(value.split())
        for name, value in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", root.group(1))
    }
