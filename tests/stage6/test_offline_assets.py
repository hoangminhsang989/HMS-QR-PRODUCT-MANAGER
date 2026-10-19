"""Standalone release: no external CDN or network dependency in shipped web assets."""

from __future__ import annotations

import hashlib
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
MOBILE_PAGE = SOURCE_ROOT / "web" / "index.html"
JSQR_SHA256 = "32214c74ee92d37de6d88276987690d996ce757668e82ca1709dba5e0be9fcce"


def test_bundled_jsqr_matches_verified_checksum():
    asset = SOURCE_ROOT / "apps" / "static" / "jsqr.min.js"
    assert asset.is_file()
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    assert digest == JSQR_SHA256


def test_vercel_copy_of_jsqr_matches_the_server_copy():
    """The Vercel deployment and the LAN server must ship the same scanner."""

    assert (SOURCE_ROOT / "web" / "static" / "jsqr.min.js").read_bytes() == (
        SOURCE_ROOT / "apps" / "static" / "jsqr.min.js"
    ).read_bytes()


def test_mobile_page_loads_jsqr_from_local_static():
    page = MOBILE_PAGE.read_text(encoding="utf-8")
    assert "/static/jsqr.min.js" in page
    assert "cdn.jsdelivr.net" not in page
    assert "https://cdn." not in page


def test_mobile_page_has_no_hardcoded_api_origin():
    """The API origin is resolved at runtime so a new tunnel URL needs no redeploy."""

    page = MOBILE_PAGE.read_text(encoding="utf-8")
    assert "const api = '/tracking';" not in page
    assert "hms-server-origin" in page
    assert "fetch('/api" not in page
    assert "fetch('/files" not in page


def test_service_worker_caches_only_local_assets():
    worker = SOURCE_ROOT / "web" / "sw.js"
    assert worker.is_file(), "web/sw.js must exist for the Vercel deployment"
    text = worker.read_text(encoding="utf-8")
    assert "/static/jsqr.min.js" in text
    assert "https://" not in text
    # cache.addAll( aborts the whole install when one asset 404s, which is how
    # the Vercel copy silently lost offline support before.
    assert "cache.addAll(" not in text


def test_no_shipped_web_asset_references_external_cdn():
    roots = [SOURCE_ROOT / "apps", SOURCE_ROOT / "web"]
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".html", ".js"} or "node_modules" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "cdn.jsdelivr.net" not in text, f"external CDN reference in {path}"
            assert "unpkg.com" not in text, f"external CDN reference in {path}"
            assert "googleapis.com" not in text, f"external CDN reference in {path}"
