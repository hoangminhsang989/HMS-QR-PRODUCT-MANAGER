"""Standalone release: no external CDN or network dependency in shipped web assets."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

import pytest

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


# Every asset that lives in both trees, because Vercel serves web/ at the root
# while the LAN server mounts apps/static/. The scanner was the only one ever
# compared; the three images were simply trusted, so a refreshed icon could
# reach one deployment and not the other with nothing noticing.
MIRRORED_ASSETS = (
    "jsqr.min.js",
    "icon-192.png",
    "icon-512.png",
    "favicon.png",
)


@pytest.mark.parametrize("name", MIRRORED_ASSETS)
def test_every_mirrored_asset_is_identical_in_both_trees(name: str):
    """One asset, two copies: Vercel's and the LAN server's must be the same bytes.

    These are the only files the split root duplicates, and they are duplicated
    for a reason - Vercel serves ``web/`` at the domain root, the LAN server
    mounts ``apps/static/`` under ``/static``. Nothing keeps the two copies in
    step except this test. A stale icon is cosmetic, which is exactly why it
    survives: nobody notices an old favicon, so the drift is found months later
    when someone asks why the two deployments do not match.
    """

    vercel = SOURCE_ROOT / "web" / "static" / name
    lan = SOURCE_ROOT / "apps" / "static" / name
    assert vercel.is_file(), f"web/static/{name} is missing"
    assert lan.is_file(), f"apps/static/{name} is missing"
    assert vercel.read_bytes() == lan.read_bytes(), (
        f"{name} differs between web/static/ (Vercel) and apps/static/ (LAN). "
        "Copy one over the other so both deployments ship the same bytes."
    )


def _cached_assets(path: Path) -> set[str]:
    """The ``STATIC_ASSETS`` array of one service worker."""

    source = path.read_text(encoding="utf-8")
    block = re.search(r"STATIC_ASSETS\s*=\s*\[(.*?)\]", source, re.DOTALL)
    assert block, f"{path.name} declares no STATIC_ASSETS"
    return set(re.findall(r"'([^']+)'", block.group(1)))


def test_the_two_service_workers_cache_the_same_assets():
    """Two service workers, one asset list, and only the bytes were ever checked.

    ``apps/static/sw.js`` says of itself: "Same shape as ``web/sw.js``, which is
    the Vercel deployment's copy. The only difference is where the manifest
    lives". That is a claim about *content*, and until now nothing verified it -
    the mirrored-asset test above compares the four images and the scanner
    byte-for-byte, but a worker's asset list is code, and two copies of code drift
    the moment one is edited.

    Drifting here is quiet in the specific way this product has already been
    bitten: a service worker that fails to install simply does not, and the page
    keeps working until the network drops. Adding an asset to one list and not the
    other leaves one deployment caching less than the other, and the first person
    to notice is someone offline on a LAN tablet.

    The one difference is real and is normalised rather than removed: the Vercel
    copy lists ``/manifest.json`` at the domain root, the LAN copy lists
    ``/static/manifest.json`` because the LAN server mounts its assets there.
    """

    vercel = _cached_assets(SOURCE_ROOT / "web" / "sw.js")
    lan = _cached_assets(SOURCE_ROOT / "apps" / "static" / "sw.js")

    normalised = {path.replace("/manifest.json", "/static/manifest.json") for path in vercel}
    assert normalised == lan, (
        "the two service workers cache different assets, so one deployment "
        "silently has less offline than the other:\n"
        f"  only in web/sw.js          : {sorted(normalised - lan)}\n"
        f"  only in apps/static/sw.js  : {sorted(lan - normalised)}"
    )


def test_every_cached_asset_exists_in_the_tree_that_caches_it():
    """A worker that lists a file which is not there fails to install, and a
    service worker that fails to install is invisible until the network drops.

    The two trees need different path handling for the same reason the asset lists
    differ: Vercel serves ``web/`` at the domain root, so ``/static/icon-192.png``
    is ``web/static/icon-192.png`` and ``/manifest.json`` is ``web/manifest.json``.
    The LAN server mounts ``apps/static/`` under ``/static``, so the same URL is
    ``apps/static/icon-192.png`` and its manifest is ``apps/static/manifest.json``.
    """

    trees = (
        (SOURCE_ROOT / "web" / "sw.js", SOURCE_ROOT / "web", ""),
        (SOURCE_ROOT / "apps" / "static" / "sw.js", SOURCE_ROOT / "apps" / "static", "static/"),
    )
    for path, root, prefix in trees:
        for asset in sorted(_cached_assets(path)):
            on_disk = root / asset.lstrip("/").removeprefix(prefix)
            assert on_disk.is_file(), f"{path.name} caches {asset} but {on_disk} does not exist"


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


WORKERS = (
    SOURCE_ROOT / "web" / "sw.js",
    SOURCE_ROOT / "apps" / "static" / "sw.js",
)


@pytest.mark.parametrize("worker", WORKERS, ids=lambda path: path.as_posix())
def test_service_worker_caches_only_local_assets(worker):
    """Both deployments' workers, not only the Vercel one.

    ``apps/server/app.py`` serves ``apps/static/sw.js`` at ``/sw.js``, so that
    is the worker a phone on the factory Wi-Fi actually gets - the one that
    needs offline support most. It kept ``cache.addAll`` long after
    ``web/sw.js`` was fixed, because this guard read only the Vercel file.
    """
    assert worker.is_file(), f"{worker.name} must exist for its deployment"
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
