"""Standalone release: no external CDN or network dependency in shipped web assets."""

from __future__ import annotations

import hashlib
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
JSQR_SHA256 = "32214c74ee92d37de6d88276987690d996ce757668e82ca1709dba5e0be9fcce"


def test_bundled_jsqr_matches_verified_checksum():
    asset = SOURCE_ROOT / "apps" / "static" / "jsqr.min.js"
    assert asset.is_file()
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    assert digest == JSQR_SHA256


def test_mobile_page_loads_jsqr_from_local_static():
    page = (SOURCE_ROOT / "apps" / "mobile" / "web.py").read_text(encoding="utf-8")
    assert "/static/jsqr.min.js" in page
    assert "cdn.jsdelivr.net" not in page
    assert "https://cdn." not in page


def test_service_worker_caches_only_local_assets():
    worker = (SOURCE_ROOT / "apps" / "static" / "sw.js").read_text(encoding="utf-8")
    assert "/static/jsqr.min.js" in worker
    assert "https://" not in worker


def test_no_shipped_web_asset_references_external_cdn():
    for path in (SOURCE_ROOT / "apps").rglob("*"):
        if path.suffix not in {".html", ".js"} or "node_modules" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "cdn.jsdelivr.net" not in text, f"external CDN reference in {path}"
        assert "unpkg.com" not in text, f"external CDN reference in {path}"
        assert "googleapis.com" not in text, f"external CDN reference in {path}"
