"""Serve the mobile web app.

There are three builds, all derived from ``web/index.html`` by
``scripts/build_mobile_web.py`` and all read from disk as bytes at request
time:

- ``index.html`` — the program. Served at ``/tracking/mobile``.
- ``vps.html`` — byte-identical to the source. Served at
  ``/tracking/mobile/vps``, outside the LAN, so it keeps the connection screen
  where a phone types the server address.
- ``lan.html`` — the same program minus the connection screen, with
  ``resolveServerOrigin()`` pinned to ``location.origin``. Served at
  ``/tracking/mobile/lan``, where the server is always same-origin.

They are separate files rather than a flag on one page so the two builds cannot
drift into each other: a phone on the factory Wi-Fi must never be offered a
connection screen that only makes sense outside the LAN.
``tests/stage6/test_mobile_web_builds.py`` regenerates both derived files and
fails unless the result is byte-identical to what is committed.

Bytes are served exactly as they sit on disk. Reading through ``read_text``
would apply universal-newline translation and hand the phone LF while Vercel
serves the CRLF file, so the two deployments would differ for no reason a
browser can see.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.responses import HTMLResponse

from config.paths import SOURCE_ROOT

MOBILE_PAGE_PATH = SOURCE_ROOT / "web" / "index.html"


def mobile_page() -> HTMLResponse:
    """Return the mobile web app, read fresh so edits need no server restart.

    The bytes are served exactly as they sit on disk. Reading through
    ``read_text`` would apply universal-newline translation and hand the phone
    LF while Vercel serves the CRLF file, so the two deployments would differ
    for no reason a browser can see.
    """

    try:
        page = MOBILE_PAGE_PATH.read_bytes()
    except OSError:
        return HTMLResponse(
            "<!doctype html><html lang='vi'><meta charset='utf-8'>"
            "<title>HMS QR</title><body style='font-family:sans-serif;padding:24px'>"
            "<h1>Không tìm thấy giao diện mobile</h1>"
            "<p>Thiếu tệp <code>web/index.html</code>. Khôi phục tệp này rồi thử lại.</p>"
            "</body></html>",
            status_code=503,
        )
    return HTMLResponse(page)

LAN_PAGE_PATH = SOURCE_ROOT / "web" / "lan.html"


def lan_page() -> HTMLResponse:
    """Return the LAN build of the mobile web app, read fresh from disk.

    The LAN build is served by the HMS QR server itself, so it is always
    same-origin and carries no way to type a server address. It is a separate
    file rather than a flag on ``index.html`` so the two builds cannot drift
    into each other: a phone on the factory Wi-Fi must never be offered a
    connection screen that only makes sense outside the LAN.
    """
    try:
        page = LAN_PAGE_PATH.read_bytes()
    except OSError:
        return HTMLResponse(
            "<!doctype html><html lang='vi'><meta charset='utf-8'>"
            "<title>HMS QR</title><body style='font-family:sans-serif;padding:24px'>"
            "<h1>Không tìm thấy giao diện mobile</h1>"
            "<p>Thiếu tệp <code>web/lan.html</code>. Khôi phục tệp này rồi thử lại.</p>"
            "</body></html>",
            status_code=503,
        )
    return HTMLResponse(page)


VPS_PAGE_PATH = SOURCE_ROOT / "web" / "vps.html"


def vps_page() -> HTMLResponse:
    """Return the VPS build of the mobile web app, read fresh from disk.

    The VPS build keeps the connection screen: a phone outside the factory LAN
    has to be told where the server lives, and the relay link it was given is
    exactly that address. Everything else is identical to the LAN build.
    """
    try:
        page = VPS_PAGE_PATH.read_bytes()
    except OSError:
        return HTMLResponse(
            "<!doctype html><html lang='vi'><meta charset='utf-8'>"
            "<title>HMS QR</title><body style='font-family:sans-serif;padding:24px'>"
            "<h1>Không tìm thấy giao diện mobile</h1>"
            "<p>Thiếu tệp <code>web/vps.html</code>. Khôi phục tệp này rồi thử lại.</p>"
            "</body></html>",
            status_code=503,
        )
    return HTMLResponse(page)
