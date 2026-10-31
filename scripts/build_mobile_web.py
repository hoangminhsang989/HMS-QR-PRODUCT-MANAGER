"""Derive the LAN and VPS mobile-web builds from ``web/index.html``.

Why this exists
---------------

``index.html`` is the program. The other two files in ``web/`` are the same
program with one difference, and both are served from disk byte-for-byte:

* ``vps.html`` is identical to ``index.html`` - a phone outside the LAN has to be
  told where the server lives, which is exactly what the connection screen in
  ``index.html`` is for.
* ``lan.html`` drops the connection screen. That page is served by the HMS QR
  server itself, so the origin is always the server, and reading
  ``localStorage['hms-server-origin']`` there would let an address typed on the
  VPS build point the LAN page at a different machine - the confusion the two
  builds exist to remove.

Both were previously produced by hand. Every theme, copy or CSS change to
``index.html`` therefore had to be re-applied by hand to two more files, and the
task board records three separate rounds of exactly that. A forgotten round is
silent: the LAN and VPS pages just keep the old look, and no guard noticed,
because a guard can only read what is on disk.

So the derivation is mechanical now, and ``tests/stage6/test_mobile_web_builds.py``
regenerates both files into a temporary directory and fails unless the result is
byte-identical to what is committed. Drift becomes a test failure with a
one-command fix instead of a bug a user has to screenshot.

Line endings are normalised on the way in and out. Git for Windows ships with
``core.autocrlf=true`` at the *system* level, so a fresh clone checks these files
out as CRLF even though the repository stores them as LF, and this repository
carries no ``.gitattributes`` to say otherwise. Deriving by exact line match
against a CRLF source finds none of its markers and dies with "found 0", which
is indistinguishable from the source having been edited. Normalising first makes
the derivation depend on the content rather than on how the checkout happened.

Usage
-----

    python -m scripts.build_mobile_web [--check]

Without ``--check`` the two derived files are rewritten in place. With
``--check`` nothing is written and the exit code is non-zero when they differ,
which is what the guard uses.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


WEB_DIR = Path(__file__).resolve().parents[1] / "web"
SOURCE = "index.html"
DERIVED = ("vps.html", "lan.html")

# The LAN build keeps the login dialog and drops only the connection dialog, so
# the comment that introduced both is narrowed to the one that remains.
LAN_HEADER_COMMENT = "  <!-- LOGIN -->"

# The LAN page is served by the server itself, so the origin is the server and
# the stored-origin fallback is deliberately absent.
LAN_ORIGIN_REPLACEMENT = """    // LAN build: this page is served by the HMS QR server itself, so the origin
    // is the server. localStorage is deliberately NOT read here - an address
    // typed on the VPS build must never be able to point the LAN page at a
    // different machine, which is exactly the confusion the two builds exist
    // to remove.
    function resolveServerOrigin() { return location.origin; }"""

LAN_ACCOUNT_PILL_REPLACEMENT = """      // The LAN build is served by the server itself, so the origin is always
      // resolved and the pill never needs hiding.
      pill.hidden = false;"""


class BuildError(RuntimeError):
    """A marker the derivation depends on is missing or ambiguous."""


def _normalize(text: str) -> str:
    """Collapse CRLF and lone CR to LF so line matching is checkout-independent."""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def _find_one(lines: list[str], marker: str, what: str) -> int:
    hits = [index for index, line in enumerate(lines) if line == marker]
    if len(hits) != 1:
        raise BuildError(
            f"{what}: expected exactly one line {marker!r} in {SOURCE}, found {len(hits)}"
        )
    return hits[0]


def _drop_one_blank_after(lines: list[str], index: int) -> list[str]:
    """Consume the single blank line that followed a removed block.

    Every block this derivation removes is followed by exactly one blank line,
    and the derived build drops it with the block. Keeping it would leave a
    double blank where a statement used to be.
    """

    if index < len(lines) and lines[index] == "":
        return lines[:index] + lines[index + 1 :]
    return lines


def _remove_html_block(lines: list[str], start: str, end: str, what: str) -> list[str]:
    """Drop ``start`` through the first following line equal to ``end``."""

    first = _find_one(lines, start, what)
    for index in range(first + 1, len(lines)):
        if lines[index] == end:
            return _drop_one_blank_after(lines[:first] + lines[index + 1 :], first)
    raise BuildError(f"{what}: no closing {end!r} after {start!r}")


def _remove_js_function(lines: list[str], name: str) -> list[str]:
    """Drop a top-level ``function name(...) { ... }`` by brace matching."""

    prefix = f"    function {name}("
    hits = [index for index, line in enumerate(lines) if line.startswith(prefix)]
    if len(hits) != 1:
        raise BuildError(
            f"expected exactly one definition of {name}(), found {len(hits)}"
        )
    first = hits[0]
    depth = 0
    for index in range(first, len(lines)):
        depth += lines[index].count("{") - lines[index].count("}")
        if depth == 0 and index > first:
            return _drop_one_blank_after(lines[:first] + lines[index + 1 :], first)
        if depth == 0 and index == first and "{" not in lines[index]:
            raise BuildError(f"{name}() definition has no opening brace")
    raise BuildError(f"{name}() definition never closes")


def _replace_block(lines: list[str], start: str, end: str, replacement: str, what: str) -> list[str]:
    """Replace ``start`` through the first following ``end`` with ``replacement``."""

    first = _find_one(lines, start, what)
    for index in range(first + 1, len(lines)):
        if lines[index] == end:
            merged = lines[:first] + replacement.split("\n") + lines[index + 1 :]
            return _drop_one_blank_after(merged, first + len(replacement.split("\n")))
    raise BuildError(f"{what}: no closing {end!r} after {start!r}")


def _replace_line(lines: list[str], marker: str, replacement: str, what: str) -> list[str]:
    """Replace the single line equal to ``marker`` with ``replacement``."""

    hits = [index for index, line in enumerate(lines) if line == marker]
    if len(hits) != 1:
        raise BuildError(f"{what}: expected exactly one line {marker!r}, found {len(hits)}")
    index = hits[0]
    return lines[:index] + replacement.split("\n") + lines[index + 1 :]


def build_lan(source_text: str) -> str:
    """Return ``lan.html``: ``index.html`` without the connection screen."""

    lines = _normalize(source_text).split("\n")

    # The chip that opens the connection dialog.
    lines = _remove_html_block(
        lines,
        "      <div class='pill-btn' onclick='openConnection()'>",
        "      </div>",
        "connection chip",
    )

    # The connection dialog itself, leaving the login dialog's comment behind.
    lines = _replace_block(
        lines,
        "  <!-- CONNECTION / LOGIN -->",
        "  </div>",
        LAN_HEADER_COMMENT,
        "connection dialog",
    )

    # The stored-origin fallback and the whole read-modify-write around it.
    lines = _replace_block(
        lines,
        "    const ORIGIN_KEY = 'hms-server-origin';",
        "    }",
        LAN_ORIGIN_REPLACEMENT,
        "origin resolution",
    )

    for name in (
        "renderConnection",
        "openConnection",
        "closeConnection",
        "saveConnection",
        "clearConnection",
    ):
        lines = _remove_js_function(lines, name)

    # The account pill is only hidden while there is no server to talk to.
    lines = _replace_line(
        lines,
        "      pill.hidden = !serverOrigin;",
        LAN_ACCOUNT_PILL_REPLACEMENT,
        "account pill visibility",
    )

    # The one call that drove the removed renderer.
    hits = [index for index, line in enumerate(lines) if line == "    renderConnection();"]
    if len(hits) != 1:
        raise BuildError(f"expected exactly one renderConnection() call, found {len(hits)}")
    lines = lines[: hits[0]] + lines[hits[0] + 1 :]

    return "\n".join(lines)


def build(source_text: str) -> dict[str, str]:
    """Return every derived build keyed by filename."""

    return {
        "vps.html": source_text,
        "lan.html": build_lan(source_text),
    }


def _read(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise BuildError(f"{path.name} carries a UTF-8 BOM; the builds are BOM-free")
    return _normalize(raw.decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="report differences without writing (used by the test guard)",
    )
    arguments = parser.parse_args(argv)

    try:
        source_text = _read(WEB_DIR / SOURCE)
        derived = build(source_text)
    except BuildError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 2

    changed: list[str] = []
    for name in DERIVED:
        current = _normalize((WEB_DIR / name).read_bytes().decode("utf-8"))
        if current != derived[name]:
            changed.append(name)

    if not changed:
        print(f"[OK] {', '.join(DERIVED)} already match {SOURCE}")
        return 0

    if arguments.check:
        for name in changed:
            print(f"[FAIL] {name} differs from what {SOURCE} derives", file=sys.stderr)
        print("Run: python -m scripts.build_mobile_web", file=sys.stderr)
        return 1

    for name in changed:
        path = WEB_DIR / name
        path.write_bytes(derived[name].encode("utf-8"))
        print(f"[OK] regenerated {name} from {SOURCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
