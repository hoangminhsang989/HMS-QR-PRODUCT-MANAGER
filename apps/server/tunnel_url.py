"""Print the Cloudflare quick-tunnel URL once cloudflared has published it.

``cloudflared tunnel --url`` writes the assigned ``*.trycloudflare.com`` hostname
to its log as soon as the tunnel is up. The launcher polls this helper so the URL
lands in a file the phone can read, instead of scrolling past in a console window.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def read_tunnel_url(log_path: Path) -> str | None:
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None


def wait_for_tunnel_url(log_path: Path, *, attempts: int = 30, delay: float = 1.0) -> str | None:
    for _ in range(attempts):
        url = read_tunnel_url(log_path)
        if url:
            return url
        time.sleep(delay)
    return None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m apps.server.tunnel_url <cloudflared.log> [output.txt]", file=sys.stderr)
        return 2
    log_path = Path(argv[1])
    url = wait_for_tunnel_url(log_path)
    if not url:
        print("Khong tim thay URL tunnel trong " + str(log_path), file=sys.stderr)
        return 1
    if len(argv) > 2:
        Path(argv[2]).write_text(url + "\n", encoding="utf-8")
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
