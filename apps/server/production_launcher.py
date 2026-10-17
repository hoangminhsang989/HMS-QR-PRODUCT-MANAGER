"""Run the central Server with current-user DPAPI secrets for Task Scheduler."""

from __future__ import annotations

import os

import uvicorn

from apps.server.tool import LAN_PORT, production_server_environment


def main() -> None:
    os.environ.update(production_server_environment())
    uvicorn.run("apps.server.app:app", host="0.0.0.0", port=LAN_PORT)


if __name__ == "__main__":
    main()
