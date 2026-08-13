"""First usable Vietnamese Product Master desktop window."""

from __future__ import annotations

import sys
from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QHBoxLayout, QHeaderView, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QTableView, QVBoxLayout, QWidget,
)

from packages.application.product_service import ProductService
from packages.domain.product import Product, ProductStatus, ProductValidationError
from packages.domain.repository import ProductPage
from apps.design_tokens import PY_SIDE_THEME


STATUS_LABELS = {
    ProductStatus.NEW: "Mới", ProductStatus.WAITING: "Chờ xử lý", ProductStatus.IN_PROGRESS: "Đang thực hiện",
    ProductStatus.WAITING_QC: "Chờ QC", ProductStatus.QC_PASS: "QC đạt", ProductStatus.QC_NG: "QC không đạt",
    ProductStatus.REWORK: "Làm lại", ProductStatus.PACKED: "Đã đóng gói", ProductStatus.DELIVERED: "Đã giao",
    ProductStatus.HOLD: "Tạm giữ", ProductStatus.CANCELLED: "Đã hủy",
}


class ProductTableModel(QAbstractTableModel):
    headers = ["Mã sản phẩm", "Công ty", "Tên chi tiết", "Số lượng", "Đơn vị", "Vật liệu", "Trạng thái"]

    def __init__(self, page: ProductPage | None = None) -> None:
        super().__init__()
        self.page = page or ProductPage((), 0, 1, 50)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.page.items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        product = self.page.items[index.row()]
        values = [product.product_code, product.company, product.part_name, str(product.quantity), product.unit,
                  product.material or "", STATUS_LABELS[product.status]]
        return values[index.column()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return super().headerData(section, orientation, role)

    def set_page(self, page: ProductPage) -> None:
        self.beginResetModel()
        self.page = page
        self.endResetModel()


class ProductForm(QWidget):
    def __init__(self, on_submit) -> None:
        super().__init__()
        self.on_submit = on_submit
        self.code = QLineEdit()
        self.company = QLineEdit()
        self.part_name = QLineEdit()
        self.quantity = QLineEdit()
        self.unit = QLineEdit("pcs")
        self.material = QLineEdit()
        self.status = QComboBox()
        for item in ProductStatus:
            self.status.addItem(STATUS_LABELS[item], item)
        submit = QPushButton("Lưu sản phẩm")
        submit.clicked.connect(self.submit)
        form = QFormLayout(self)
        for label, widget in (("Mã sản phẩm", self.code), ("Công ty", self.company), ("Tên chi tiết", self.part_name),
                              ("Số lượng", self.quantity), ("Đơn vị", self.unit), ("Vật liệu", self.material),
                              ("Trạng thái", self.status)):
            form.addRow(label, widget)
        form.addRow(submit)

    def submit(self) -> None:
        try:
            self.on_submit({"product_code": self.code.text() or None, "company": self.company.text(),
                            "part_name": self.part_name.text(), "quantity": Decimal(self.quantity.text()),
                            "unit": self.unit.text(), "material": self.material.text() or None,
                            "status": self.status.currentData()})
        except (ProductValidationError, ValueError) as exc:
            QMessageBox.warning(self, "Dữ liệu chưa hợp lệ", str(exc))


class ProductMasterWindow(QMainWindow):
    def __init__(self, service: ProductService, actor: str = "desktop-user") -> None:
        super().__init__()
        self.service = service
        self.actor = actor
        self.setWindowTitle("HMS QR — Quản lý sản phẩm")
        self.resize(1100, 680)
        self.setStyleSheet(PY_SIDE_THEME)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm mã, công ty, tên chi tiết, vật liệu...")
        self.filter_status = QComboBox()
        self.filter_status.addItem("Tất cả trạng thái", None)
        for item in ProductStatus:
            self.filter_status.addItem(STATUS_LABELS[item], item)
        refresh = QPushButton("Làm mới")
        refresh.clicked.connect(self.refresh)
        self.table = QTableView()
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.model = ProductTableModel()
        self.table.setModel(self.model)
        self.form = ProductForm(self.create_product)
        controls = QHBoxLayout()
        controls.addWidget(self.search)
        controls.addWidget(self.filter_status)
        controls.addWidget(refresh)
        body = QVBoxLayout()
        body.addLayout(controls)
        body.addWidget(self.table, 1)
        body.addWidget(self.form)
        container = QWidget()
        container.setLayout(body)
        self.setCentralWidget(container)
        self.search.returnPressed.connect(self.refresh)
        self.filter_status.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.model.set_page(self.service.list_products(search=self.search.text() or None,
                                                       status=self.filter_status.currentData()))

    def create_product(self, payload: dict[str, object]) -> None:
        self.service.create_product(actor=self.actor, **payload)
        self.form.code.clear(); self.form.company.clear(); self.form.part_name.clear(); self.form.quantity.clear(); self.form.material.clear()
        self.refresh()


def run(service: ProductService) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = ProductMasterWindow(service)
    window.show()
    return app.exec()


__all__ = ["ProductMasterWindow", "ProductTableModel", "run"]
