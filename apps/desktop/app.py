"""Minimal importable desktop application boundary."""

APP_NAME = "hms-qr-desktop"


def create_app() -> dict[str, str]:
    return {"name": APP_NAME, "status": "foundation"}
