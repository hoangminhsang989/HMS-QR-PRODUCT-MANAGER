"""Serve the mobile web app.

The page itself lives in ``web/index.html`` so the LAN server and the Vercel
deployment serve byte-identical HTML. ``web/index.html`` is the single source of
truth; this module only reads and returns it.
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
