"""Run the central Server with current-user DPAPI secrets for Task Scheduler."""

from __future__ import annotations

import os

import uvicorn

from apps.server.tool import LAN_PORT, production_server_environment


def main() -> None:
    os.environ.update(production_server_environment())
    uvicorn.run(
        "apps.server.app:app",
        host="0.0.0.0",
        port=LAN_PORT,
        ssl_certfile=os.environ.get("HMS_QR_TLS_CERT") or None,
        ssl_keyfile=os.environ.get("HMS_QR_TLS_KEY") or None,
    )


if __name__ == "__main__":
    main()
