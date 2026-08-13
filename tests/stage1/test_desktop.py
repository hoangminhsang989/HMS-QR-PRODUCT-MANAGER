import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from apps.desktop.product_master_window import ProductMasterWindow, ProductTableModel
from packages.application.product_service import ProductService
from packages.persistence.sqlite_product_repository import SQLiteProductRepository


def test_desktop_product_master_window_smoke(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    window = ProductMasterWindow(service)
    assert "Quản lý sản phẩm" in window.windowTitle()
    assert isinstance(window.model, ProductTableModel)
    window.close()
    app.processEvents()
