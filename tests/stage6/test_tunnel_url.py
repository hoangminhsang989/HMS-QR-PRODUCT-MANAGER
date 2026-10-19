"""Cloudflare quick-tunnel URL capture for the mobile web app.

The launcher needs the assigned ``*.trycloudflare.com`` hostname in a file the
phone can read, because ``cloudflared`` only prints it to a log that otherwise
scrolls past in a console window.
"""
from __future__ import annotations

from pathlib import Path

from apps.server.tunnel_url import URL_PATTERN, read_tunnel_url, wait_for_tunnel_url


def test_url_pattern_matches_the_cloudflared_banner():
    banner = (
        "2026-10-19T10:00:04Z INF +----------------------------+\n"
        "2026-10-19T10:00:04Z INF |  https://quiet-frog-42.trycloudflare.com  |\n"
        "2026-10-19T10:00:04Z INF +----------------------------+\n"
    )
    assert URL_PATTERN.search(banner).group(0) == "https://quiet-frog-42.trycloudflare.com"


def test_read_tunnel_url_ignores_unrelated_log_lines(tmp_path):
    log = tmp_path / "cloudflared.log"
    log.write_text(
        "2026-10-19T10:00:00Z INF Starting tunnel\n"
        "2026-10-19T10:00:04Z INF Requesting new quick tunnel\n"
        "2026-10-19T10:00:05Z INF |  https://loud-cat-7.trycloudflare.com  |\n"
        "2026-10-19T10:00:06Z INF Connection registered\n",
        encoding="utf-8",
    )
    assert read_tunnel_url(log) == "https://loud-cat-7.trycloudflare.com"


def test_read_tunnel_url_reports_nothing_when_the_log_is_absent(tmp_path):
    assert read_tunnel_url(tmp_path / "missing.log") is None


def test_read_tunnel_url_reports_nothing_before_the_tunnel_is_up(tmp_path):
    log = tmp_path / "cloudflared.log"
    log.write_text("2026-10-19T10:00:00Z INF Starting tunnel\n", encoding="utf-8")
    assert read_tunnel_url(log) is None


def test_wait_for_tunnel_url_returns_once_the_hostname_appears(tmp_path):
    log = tmp_path / "cloudflared.log"
    log.write_text("2026-10-19T10:00:00Z INF Starting tunnel\n", encoding="utf-8")

    import threading

    def publish_later():
        import time

        time.sleep(0.2)
        with log.open("a", encoding="utf-8") as handle:
            handle.write("2026-10-19T10:00:03Z INF |  https://late-ox-9.trycloudflare.com  |\n")

    threading.Thread(target=publish_later, daemon=True).start()
    assert wait_for_tunnel_url(log, attempts=10, delay=0.1) == "https://late-ox-9.trycloudflare.com"


def test_wait_for_tunnel_url_gives_up_rather_than_hanging(tmp_path):
    log = tmp_path / "cloudflared.log"
    log.write_text("nothing here yet\n", encoding="utf-8")
    assert wait_for_tunnel_url(log, attempts=2, delay=0.05) is None
