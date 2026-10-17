from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from packages.application.stage2_api_client import Stage2ApiClient, Stage2ApiError


class Stage2Window(QMainWindow):
    """Customer entry point for the central Stage 2 API; never opens a database."""

    def __init__(self, client: Stage2ApiClient | None, *, role: str = "ADMIN"):
        super().__init__()
        self.client = client
        self.role = role
        self.setWindowTitle("HMS QR - Khách hàng, Đơn hàng và Lịch sản xuất")
        self.resize(1000, 650)
        tabs = QTabWidget()
        tabs.addTab(self._customers_page(), "KHÁCH HÀNG")
        tabs.addTab(self._purchase_orders_page(), "ĐƠN HÀNG / PO")
        tabs.addTab(self._schedule_page(), "LỊCH SẢN XUẤT")
        self.setCentralWidget(tabs)
        if self.client:
            self.refresh_customers()
            self.refresh_purchase_orders()

    def _customers_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm mã hoặc tên khách hàng")
        refresh = QPushButton("TÌM / LÀM MỚI")
        refresh.clicked.connect(self.refresh_customers)
        controls.addWidget(self.search)
        controls.addWidget(refresh)
        layout.addLayout(controls)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Mã", "Khách hàng", "Tên ngắn", "Điện thoại", "Trạng thái"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        form = QFormLayout()
        self.customer_code = QLineEdit()
        self.customer_name = QLineEdit()
        self.short_name = QLineEdit()
        self.phone = QLineEdit()
        form.addRow("Mã khách hàng", self.customer_code)
        form.addRow("Tên khách hàng *", self.customer_name)
        form.addRow("Tên ngắn", self.short_name)
        form.addRow("Điện thoại", self.phone)
        layout.addLayout(form)
        self.create_button = QPushButton("TẠO KHÁCH HÀNG")
        self.create_button.clicked.connect(self.create_customer)
        self.create_button.setEnabled(self.client is not None and self.role in {"ADMIN", "EDITOR"})
        layout.addWidget(self.create_button)
        return page

    def refresh_customers(self) -> None:
        if not self.client:
            return
        try:
            result = self.client.list_customers(search=self.search.text().strip() or None)
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Khách hàng", str(exc))
            return
        self.table.setRowCount(0)
        for customer in result["items"]:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [customer["customer_code"], customer["name"], customer.get("short_name") or "", customer.get("phone") or "", "Đang dùng" if customer["active"] else "Ngừng dùng"]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))

    def create_customer(self) -> None:
        if not self.client or self.role not in {"ADMIN", "EDITOR"}:
            return
        name = self.customer_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Khách hàng", "Nhập tên khách hàng.")
            return
        try:
            self.client.create_customer(name=name, customer_code=self.customer_code.text().strip(), short_name=self.short_name.text().strip(), phone=self.phone.text().strip())
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Khách hàng", str(exc))
            return
        self.customer_code.clear()
        self.customer_name.clear()
        self.short_name.clear()
        self.phone.clear()
        self.refresh_customers()

    def _purchase_orders_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.po_search = QLineEdit()
        self.po_search.setPlaceholderText("Lọc theo số PO")
        refresh = QPushButton("LÀM MỚI PO")
        refresh.clicked.connect(self.refresh_purchase_orders)
        controls.addWidget(self.po_search)
        controls.addWidget(refresh)
        layout.addLayout(controls)
        self.po_table = QTableWidget(0, 5)
        self.po_table.setHorizontalHeaderLabels(["Số PO", "Khách hàng", "Ngày PO", "Ngày giao", "Trạng thái"])
        self.po_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.po_table.itemSelectionChanged.connect(self.refresh_purchase_order_lines)
        layout.addWidget(self.po_table)
        form = QFormLayout()
        self.po_number = QLineEdit()
        self.po_customer = QComboBox()
        self.po_date = QDateEdit()
        self.po_date.setCalendarPopup(True)
        self.po_date.setDate(QDate.currentDate())
        self.delivery_date = QDateEdit()
        self.delivery_date.setCalendarPopup(True)
        self.delivery_date.setDate(self.po_date.date())
        form.addRow("Số PO *", self.po_number)
        form.addRow("Khách hàng *", self.po_customer)
        form.addRow("Ngày PO", self.po_date)
        form.addRow("Ngày giao", self.delivery_date)
        layout.addLayout(form)
        self.create_po_button = QPushButton("TẠO PO")
        self.create_po_button.clicked.connect(self.create_purchase_order)
        self.create_po_button.setEnabled(self.client is not None and self.role in {"ADMIN", "EDITOR"})
        layout.addWidget(self.create_po_button)
        layout.addWidget(QLabel("Dòng PO của PO đang chọn"))
        self.line_table = QTableWidget(0, 4)
        self.line_table.setHorizontalHeaderLabels(["Dòng", "Sản phẩm", "Số lượng", "Đơn vị"])
        self.line_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.line_table.itemSelectionChanged.connect(self.refresh_schedule)
        layout.addWidget(self.line_table)
        line_form = QFormLayout()
        self.line_product = QComboBox()
        self.line_quantity = QLineEdit()
        self.line_unit = QLineEdit("pcs")
        line_form.addRow("Sản phẩm *", self.line_product)
        line_form.addRow("Số lượng *", self.line_quantity)
        line_form.addRow("Đơn vị *", self.line_unit)
        layout.addLayout(line_form)
        self.create_line_button = QPushButton("THÊM DÒNG PO")
        self.create_line_button.clicked.connect(self.create_purchase_order_line)
        self.create_line_button.setEnabled(self.client is not None and self.role in {"ADMIN", "EDITOR"})
        layout.addWidget(self.create_line_button)
        return page

    def refresh_purchase_orders(self) -> None:
        if not self.client:
            return
        try:
            customers = self.client.list_customers(active=True)["items"]
            orders = self.client.list_purchase_orders()["items"]
            products = self.client.list_products()["items"]
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Đơn hàng / PO", str(exc))
            return
        customer_names = {customer["internal_id"]: customer["name"] for customer in customers}
        current = self.po_customer.currentData()
        self.po_customer.clear()
        for customer in customers:
            self.po_customer.addItem(f'{customer["customer_code"]} - {customer["name"]}', customer["internal_id"])
        if current:
            index = self.po_customer.findData(current)
            if index >= 0:
                self.po_customer.setCurrentIndex(index)
        current_product = self.line_product.currentData()
        self.line_product.clear()
        for product in products:
            self.line_product.addItem(f'{product["product_code"]} - {product["part_name"]}', product["internal_id"])
        if current_product:
            index = self.line_product.findData(current_product)
            if index >= 0:
                self.line_product.setCurrentIndex(index)
        search = self.po_search.text().strip().casefold()
        self.po_table.setRowCount(0)
        for order in orders:
            if search and search not in order["po_number"].casefold():
                continue
            row = self.po_table.rowCount()
            self.po_table.insertRow(row)
            values = [order["po_number"], customer_names.get(order["customer_id"], order["customer_id"]), order["po_date"], order.get("requested_delivery_date") or "", order["status"]]
            for column, value in enumerate(values):
                self.po_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.po_table.item(row, 0).setData(256, order["internal_id"])

    def create_purchase_order(self) -> None:
        if not self.client or self.role not in {"ADMIN", "EDITOR"}:
            return
        number = self.po_number.text().strip()
        customer_id = self.po_customer.currentData()
        if not number or not customer_id:
            QMessageBox.warning(self, "Đơn hàng / PO", "Nhập số PO và chọn khách hàng.")
            return
        try:
            self.client.create_purchase_order(
                po_number=number, customer_id=customer_id,
                po_date=self.po_date.date().toString("yyyy-MM-dd"),
                requested_delivery_date=self.delivery_date.date().toString("yyyy-MM-dd"),
            )
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Đơn hàng / PO", str(exc))
            return
        self.po_number.clear()
        self.refresh_purchase_orders()

    def _selected_purchase_order_id(self) -> str | None:
        row = self.po_table.currentRow()
        item = self.po_table.item(row, 0) if row >= 0 else None
        return item.data(256) if item else None

    def refresh_purchase_order_lines(self) -> None:
        if not self.client:
            return
        po_id = self._selected_purchase_order_id()
        self.line_table.setRowCount(0)
        if not po_id:
            return
        try:
            lines = self.client.list_purchase_order_lines(po_id)["items"]
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Dòng PO", str(exc))
            return
        product_labels = {self.line_product.itemData(index): self.line_product.itemText(index) for index in range(self.line_product.count())}
        for line in lines:
            row = self.line_table.rowCount()
            self.line_table.insertRow(row)
            values = [line["line_number"], product_labels.get(line["product_id"], line["product_id"]), line["ordered_quantity"], line["unit"]]
            for column, value in enumerate(values):
                self.line_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.line_table.item(row, 0).setData(256, line["internal_id"])
            self.line_table.item(row, 0).setData(257, line["product_id"])
            self.line_table.item(row, 0).setData(258, line["ordered_quantity"])

    def create_purchase_order_line(self) -> None:
        if not self.client or self.role not in {"ADMIN", "EDITOR"}:
            return
        po_id = self._selected_purchase_order_id()
        product_id = self.line_product.currentData()
        quantity = self.line_quantity.text().strip()
        unit = self.line_unit.text().strip()
        if not po_id or not product_id or not quantity or not unit:
            QMessageBox.warning(self, "Dòng PO", "Chọn PO, sản phẩm và nhập số lượng/đơn vị.")
            return
        try:
            line_number = self.line_table.rowCount() + 1
            self.client.create_purchase_order_line(po_id=po_id, product_id=product_id, line_number=line_number, ordered_quantity=quantity, unit=unit)
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Dòng PO", str(exc))
            return
        self.line_quantity.clear()
        self.refresh_purchase_order_lines()

    def _schedule_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Chọn một dòng PO trong tab ĐƠN HÀNG / PO, sau đó tạo lịch giao hoặc Production Run."))
        self.schedule_table = QTableWidget(0, 3)
        self.schedule_table.setHorizontalHeaderLabels(["Ngày giao", "Số lượng", "Trạng thái"])
        self.schedule_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.schedule_table)
        delivery_form = QFormLayout()
        self.schedule_date = QDateEdit(QDate.currentDate())
        self.schedule_date.setCalendarPopup(True)
        self.schedule_quantity = QLineEdit()
        delivery_form.addRow("Ngày giao", self.schedule_date)
        delivery_form.addRow("Số lượng giao *", self.schedule_quantity)
        layout.addLayout(delivery_form)
        self.create_schedule_button = QPushButton("THÊM LỊCH GIAO")
        self.create_schedule_button.clicked.connect(self.create_delivery_schedule)
        self.create_schedule_button.setEnabled(self.client is not None and self.role in {"ADMIN", "EDITOR"})
        layout.addWidget(self.create_schedule_button)
        self.run_table = QTableWidget(0, 4)
        self.run_table.setHorizontalHeaderLabels(["Mã Run", "Kế hoạch", "Hoàn thành", "Trạng thái"])
        self.run_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.run_table)
        run_form = QFormLayout()
        self.run_quantity = QLineEdit()
        self.run_start = QDateEdit(QDate.currentDate())
        self.run_start.setCalendarPopup(True)
        self.run_finish = QDateEdit(QDate.currentDate())
        self.run_finish.setCalendarPopup(True)
        run_form.addRow("Số lượng chạy *", self.run_quantity)
        run_form.addRow("Bắt đầu", self.run_start)
        run_form.addRow("Kết thúc", self.run_finish)
        layout.addLayout(run_form)
        self.create_run_button = QPushButton("TẠO PRODUCTION RUN")
        self.create_run_button.clicked.connect(self.create_production_run)
        self.create_run_button.setEnabled(self.client is not None and self.role in {"ADMIN", "EDITOR"})
        layout.addWidget(self.create_run_button)
        return page

    def _selected_line(self) -> tuple[str, str, str] | None:
        row = self.line_table.currentRow()
        item = self.line_table.item(row, 0) if row >= 0 else None
        if not item:
            return None
        return item.data(256), item.data(257), item.data(258)

    def refresh_schedule(self) -> None:
        if not self.client:
            return
        selected = self._selected_line()
        self.schedule_table.setRowCount(0)
        self.run_table.setRowCount(0)
        if not selected:
            return
        line_id, _product_id, _ordered_quantity = selected
        try:
            deliveries = self.client.list_delivery_schedules(line_id)["items"]
            runs = self.client.list_production_runs(line_id=line_id)["items"]
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Lịch sản xuất", str(exc))
            return
        for delivery in deliveries:
            row = self.schedule_table.rowCount()
            self.schedule_table.insertRow(row)
            for column, value in enumerate([delivery["planned_date"], delivery["planned_quantity"], delivery["status"]]):
                self.schedule_table.setItem(row, column, QTableWidgetItem(str(value)))
        for run in runs:
            row = self.run_table.rowCount()
            self.run_table.insertRow(row)
            for column, value in enumerate([run["run_code"], run["planned_quantity"], run["completed_quantity"], run["status"]]):
                self.run_table.setItem(row, column, QTableWidgetItem(str(value)))

    def create_delivery_schedule(self) -> None:
        if not self.client or self.role not in {"ADMIN", "EDITOR"}:
            return
        selected = self._selected_line()
        quantity = self.schedule_quantity.text().strip()
        if not selected or not quantity:
            QMessageBox.warning(self, "Lịch giao", "Chọn dòng PO và nhập số lượng giao.")
            return
        line_id, _product_id, ordered_quantity = selected
        try:
            self.client.create_delivery_schedule(
                line_id=line_id, ordered_quantity=ordered_quantity, planned_quantity=quantity,
                planned_date=self.schedule_date.date().toString("yyyy-MM-dd"),
            )
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Lịch giao", str(exc))
            return
        self.schedule_quantity.clear()
        self.refresh_schedule()

    def create_production_run(self) -> None:
        if not self.client or self.role not in {"ADMIN", "EDITOR"}:
            return
        selected = self._selected_line()
        quantity = self.run_quantity.text().strip()
        if not selected or not quantity:
            QMessageBox.warning(self, "Production Run", "Chọn dòng PO và nhập số lượng chạy.")
            return
        line_id, product_id, ordered_quantity = selected
        try:
            self.client.create_production_run(
                line_id=line_id, product_id=product_id, ordered_quantity=ordered_quantity,
                planned_quantity=quantity, planned_start=self.run_start.date().toString("yyyy-MM-dd"),
                planned_finish=self.run_finish.date().toString("yyyy-MM-dd"),
            )
        except Stage2ApiError as exc:
            QMessageBox.warning(self, "Production Run", str(exc))
            return
        self.run_quantity.clear()
        self.refresh_schedule()
