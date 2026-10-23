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
