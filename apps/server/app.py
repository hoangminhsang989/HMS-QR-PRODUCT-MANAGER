"""Minimal importable server application boundary."""

APP_NAME = "hms-qr-server"


def create_app() -> dict[str, str]:
    """Return a dependency-free app descriptor for the foundation smoke test."""
    return {"name": APP_NAME, "status": "foundation"}
