"""Desktop application boundary."""

from .product_master_window import ProductMasterWindow

APP_NAME = "hms-qr-desktop"


def create_app() -> dict[str, str]:
    return {"name": APP_NAME, "status": "foundation", "feature": "product_master", "theme": "hms-dark-industrial"}


__all__ = ["ProductMasterWindow", "create_app"]
