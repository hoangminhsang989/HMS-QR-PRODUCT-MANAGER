import os
import time
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QImage, QKeyEvent, QKeySequence, QMouseEvent, QStandardItemModel
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QStyleOptionViewItem, QTableView, QTableWidgetItem, QTableWidgetSelectionRange, QTabWidget

from apps.desktop.product_master_window import DEFAULT_CELL_SIZE_SETTINGS, ENTRY_HEADERS, FormulaItemDelegate, ProductImageViewer, ProductMasterWindow, ProductTableModel, SpreadsheetEntryGrid, SpreadsheetFilterDialog, SpreadsheetHeader, SpreadsheetSizeDialog, complete_formula_parentheses, cycle_formula_reference_lock, format_dimensions, product_code_value, product_qr_label_png, product_qr_value
from packages.application.product_service import ProductService
from packages.persistence.sqlite_product_repository import SQLiteProductRepository


def clear_entry_draft(delivery_date):
    settings = QSettings("HMS QR", "Quan Ly QR")
    settings.remove(f"worksheet/drafts/{delivery_date.isoformat()}")
    settings.sync()


def test_desktop_product_master_window_smoke(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    window = ProductMasterWindow(service)
    assert "Quản lý sản phẩm" in window.windowTitle()
    assert isinstance(window.model, ProductTableModel)
    window.close()
    app.processEvents()


def test_desktop_hides_requested_product_master_action_buttons(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "hidden-actions.sqlite")))
    window.show()
    app.processEvents()

    visible_buttons = {button.text() for button in window.findChildren(QPushButton) if button.isVisible()}
    assert "MỞ TRACKING SẢN PHẨM" not in visible_buttons
    assert not {
        "Làm mới", "COPY DANH SÁCH ĐANG LỌC", "KHÁCH HÀNG / PO", "Thêm 10 dòng",
        "Chọn ảnh cho dòng", "Xóa vùng nhập", "COPY VÙNG CHỌN", "Lưu các dòng nhập",
    } & visible_buttons
    assert not window.search.isVisible()
    assert not window.filter_status.isVisible()
    window.close()


def test_desktop_product_files_are_not_a_primary_tab(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "files-tab.sqlite")))
    tabs = window.findChild(QTabWidget)

    assert not any(tabs.tabText(index) == "ẢNH & TỆP" for index in range(tabs.count()))
    assert window.files_panel is not None
    window.close()


def test_desktop_auto_saves_completed_worksheet_row_and_has_tracking_tab(tmp_path):
    app = QApplication.instance() or QApplication([])
    clear_entry_draft(__import__("datetime").date.today())
    service = ProductService(SQLiteProductRepository(tmp_path / "autosave.sqlite"))
    window = ProductMasterWindow(service)
    for header, value in (("Khách hàng", "HMS"), ("Tên sản phẩm", "Tự lưu"), ("Số lượng", "2")):
        window.entry_grid.item(0, ENTRY_HEADERS.index(header)).setText(value)

    window._pending_entry_rows.add(0)
    window.save_completed_entry_rows()

    assert service.list_products().total == 1
    tabs = window.findChild(QTabWidget)
    tracking_index = next(index for index in range(tabs.count()) if tabs.tabText(index) == "THEO DÕI TIẾN TRÌNH CHI TIẾT")
    assert window.table.parentWidget() is tabs.widget(tracking_index)
    window.close()
    clear_entry_draft(__import__("datetime").date.today())


def test_desktop_closing_window_cancels_pending_auto_save_timers(tmp_path):
    app = QApplication.instance() or QApplication([])
    clear_entry_draft(__import__("datetime").date.today())
    service = ProductService(SQLiteProductRepository(tmp_path / "timer-close.sqlite"))
    window = ProductMasterWindow(service)
    for header, value in (("Khách hàng", "HMS"), ("Tên sản phẩm", "Tự lưu"), ("Số lượng", "2")):
        window.entry_grid.item(0, ENTRY_HEADERS.index(header)).setText(value)
    window.schedule_entry_save(window.entry_grid.item(0, 0))
    assert window._entry_auto_save_timer.isActive()

    window.close()
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)

    assert service.list_products().total == 0
    assert not window._entry_auto_save_timer.isActive()
    assert not window._draft_save_timer.isActive()
    clear_entry_draft(__import__("datetime").date.today())


def test_desktop_shows_verified_server_connection_and_can_recheck(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    service.verify_server_readiness = __import__("unittest.mock", fromlist=["Mock"]).Mock()
    window = ProductMasterWindow(service, actor="admin", server_url="http://192.168.2.15:8010", account_role="ADMIN")

    assert "ĐÃ KẾT NỐI" in window.connection_status.text()
    assert "192.168.2.15:8010" in window.connection_status.text()
    assert "admin (ADMIN)" in window.connection_status.text()
    window.check_server_connection()
    service.verify_server_readiness.assert_called_once()
    window.close()


def test_viewer_desktop_disables_data_changes_and_hides_admin_storage(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "viewer.sqlite"))
    window = ProductMasterWindow(service, account_role="VIEWER")

    assert not window.save_entry_action.isEnabled()
    assert window.entry_grid.editTriggers() == window.entry_grid.EditTrigger.NoEditTriggers
    assert not window.files_panel.add_image_button.isEnabled()
    assert not any(window.findChild(QTabWidget).tabText(index) == "CẤU HÌNH LƯU TRỮ" for index in range(window.findChild(QTabWidget).count()))
    window.close()


def test_desktop_product_list_is_visible_and_copy_uses_active_filter(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "list.sqlite"))
    service.create_product(actor="admin", company="HMS", part_name="Part A", quantity=Decimal("2"), unit="pcs")
    window = ProductMasterWindow(service)

    assert window.table.isVisible() is False
    window.show()
    app.processEvents()
    tabs = window.findChild(QTabWidget)
    tabs.setCurrentIndex(next(index for index in range(tabs.count()) if tabs.tabText(index) == "THEO DÕI TIẾN TRÌNH CHI TIẾT"))
    assert window.table.isVisible()
    assert window.product_result_count.text() == "1 sản phẩm"
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    window.copy_to_excel()
    assert "Part A" in QApplication.clipboard().text()
    window.close()


def test_desktop_worksheet_copy_exports_selected_rows(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "worksheet-copy.sqlite")))
    company_column = ENTRY_HEADERS.index("Khách hàng")
    product_column = ENTRY_HEADERS.index("Tên sản phẩm")
    window.entry_grid.item(0, company_column).setText("HMS")
    window.entry_grid.item(0, product_column).setText("Part A")
    window.entry_grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, product_column), True)

    window.copy_selected_entry_rows()

    copied = QApplication.clipboard().text()
    assert "Khách Hàng" in copied
    assert "HMS" in copied
    assert "Part A" in copied
    window.close()


def test_desktop_worksheet_saves_partial_rows_with_blank_customer_and_zero_quantity(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    selected_date = __import__("datetime").date.today()
    clear_entry_draft(selected_date)
    service = ProductService(SQLiteProductRepository(tmp_path / "worksheet-validation.sqlite"))
    window = ProductMasterWindow(service)
    window.entry_grid.item(0, ENTRY_HEADERS.index("Khách hàng")).setText("HMS")
    window.entry_grid.item(0, ENTRY_HEADERS.index("Số lượng")).setText("2")
    window.entry_grid.item(1, ENTRY_HEADERS.index("Khách hàng")).setText("Missing quantity")
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)

    window.save_entry_rows()

    products = service.list_products(page_size=10).items
    assert len(products) == 2
    incomplete = next(product for product in products if product.company == "Missing quantity")
    assert incomplete.quantity == Decimal("0")
    window.close()


def test_desktop_worksheet_does_not_save_generated_only_blank_rows(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    selected_date = __import__("datetime").date.today()
    clear_entry_draft(selected_date)
    service = ProductService(SQLiteProductRepository(tmp_path / "worksheet-empty.sqlite"))
    window = ProductMasterWindow(service)
    window.entry_grid.item(0, ENTRY_HEADERS.index("Trạng thái S/P")).setText("Mới")
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)

    window.save_entry_rows()

    assert service.list_products().total == 0
    window.close()
    clear_entry_draft(selected_date)


def test_desktop_tracking_action_requires_authenticated_server_and_selection(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "tracking-action.sqlite"))
    window = ProductMasterWindow(service)
    message = __import__("unittest.mock", fromlist=["Mock"]).Mock()
    monkeypatch.setattr(QMessageBox, "information", message)

    window.open_selected_product_tracking()

    assert "Chọn một sản phẩm" in message.call_args.args[2]
    window.close()


def test_desktop_opens_tracking_for_selected_product(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "tracking-selected.sqlite"))
    product = service.create_product(actor="admin", company="HMS", part_name="Tracked", quantity=Decimal("2"), unit="pcs")
    service.access_token = "session-token"
    captured = {}

    class FakeTrackingClient:
        def __init__(self, server_url, *, access_token):
            captured["server_url"] = server_url
            captured["access_token"] = access_token

        def list_tracking(self, *, search):
            captured["search"] = search
            return []

    monkeypatch.setattr("apps.desktop.product_master_window.TrackingApiClient", FakeTrackingClient)
    window = ProductMasterWindow(service, server_url="http://192.168.2.15:8010")
    window.table.selectRow(0)

    window.open_selected_product_tracking()

    assert captured == {
        "server_url": "http://192.168.2.15:8010",
        "access_token": "session-token",
        "search": product.product_code,
    }
    assert window.tracking_window.windowTitle().endswith(product.product_code)
    window.tracking_window.close()
    window.close()


def test_desktop_dimension_symbol_attaches_to_next_measurement():
    assert format_dimensions(["Ø", "14.5", "2.8"]) == "Ø14.5 x 2.8"
    assert format_dimensions(["100", "50", "20"]) == "100 x 50 x 20"


def test_desktop_entry_generates_no_code_without_product_name(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    window = ProductMasterWindow(service)
    window.entry_grid.item(0, ENTRY_HEADERS.index("Tên sản phẩm")).setText("")
    for header, value in (("Khách hàng", "CAP"), ("Số lượng", "10")):
        window.entry_grid.item(0, ENTRY_HEADERS.index(header)).setText(value)
    assert window.entry_grid.item(0, ENTRY_HEADERS.index("Mã sản phẩm")).text() == f"C-NO-{window.selected_delivery_date:%y%m%d}-R001"
    window.close()


def test_desktop_entry_date_navigator_accepts_double_click_number_input(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window.selected_delivery_date = __import__("datetime").date(2026, 3, 31)
    assert window.eventFilter(window.delivery_date_labels["month"], QEvent(QEvent.Type.MouseButtonDblClick))
    editor = window.delivery_date_editors["month"]
    assert editor.value() == 3
    assert editor.geometry() == window.delivery_date_labels["month"].geometry()
    editor.setValue(2)
    window._commit_entry_delivery_date("month")
    assert window.selected_delivery_date == __import__("datetime").date(2026, 2, 28)
    window.close()


def test_desktop_entry_preview_code_is_preserved_when_saved(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    clear_entry_draft(__import__("datetime").date.today())
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    window = ProductMasterWindow(service)
    for header, value in (("Khách hàng", "CAP"), ("Tên sản phẩm", "JIG"), ("Số lượng", "1")):
        window.entry_grid.item(0, ENTRY_HEADERS.index(header)).setText(value)
    preview_code = window.entry_grid.item(0, ENTRY_HEADERS.index("Mã sản phẩm")).text()
    assert preview_code == f"C-J-{window.selected_delivery_date:%y%m%d}-R001"
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)

    window.save_entry_rows()

    assert service.list_products().items[0].product_code == preview_code
    window.close()
    clear_entry_draft(window.selected_delivery_date)
    app.processEvents()
    window.close()
    app.processEvents()


def test_desktop_ctrl_s_saves_entry_rows_from_window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    selected_date = __import__("datetime").date.today()
    clear_entry_draft(selected_date)
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    window = ProductMasterWindow(service)
    for header, value in (("Khách hàng", "HMS"), ("Tên sản phẩm", "Lưu bằng phím tắt"), ("Số lượng", "2")):
        window.entry_grid.item(0, ENTRY_HEADERS.index(header)).setText(value)
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)

    assert window.save_entry_action.shortcut() == QKeySequence.StandardKey.Save
    assert window.save_entry_action.shortcutContext() == Qt.ShortcutContext.WindowShortcut
    window.save_entry_action.trigger()

    assert service.list_products().total == 1
    assert service.list_products().items[0].part_name == "Lưu bằng phím tắt"
    window.close()
    clear_entry_draft(selected_date)
    app.processEvents()


def test_spreadsheet_filter_opens_only_from_its_triangle():
    app = QApplication.instance() or QApplication([])
    table = QTableView()
    table.setModel(QStandardItemModel(1, 1, table))
    header = SpreadsheetHeader(table)
    table.setHorizontalHeader(header)
    table.resize(200, 120)
    header.resizeSection(0, 100)
    table.show()
    app.processEvents()
    opened_columns = []
    header.filterRequested.connect(opened_columns.append)

    icon = header.filter_icon_rect(0)
    beside_icon = icon.topLeft() - QPoint(1, 0)
    header.mouseReleaseEvent(QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease, QPointF(beside_icon), QPointF(beside_icon), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    ))
    assert opened_columns == []

    header.mouseReleaseEvent(QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease, QPointF(icon.center()), QPointF(icon.center()), Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    ))
    assert opened_columns == [0]
    table.close()
    app.processEvents()


def test_desktop_status_column_is_frozen_at_right(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    app.processEvents()
    status_column = ENTRY_HEADERS.index("Trạng thái S/P")
    status = window.entry_grid.item(0, status_column)
    status.setText("Mới")
    status.setBackground(Qt.GlobalColor.green)
    window.sync_frozen_status_column()

    frozen = window.status_grid.item(0, 0)
    assert window.entry_grid.isColumnHidden(status_column)
    assert frozen.text() == "Mới"
    frozen.setSelected(True)
    window.select_status_from_frozen_column(frozen)
    assert window.entry_grid.currentRow() == 0
    assert window.entry_grid.currentColumn() == status_column
    window.close()


def test_desktop_frozen_status_has_outer_scrollbar_and_excel_zoom(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    original_width = window.entry_grid.columnWidth(0)
    original_height = window.entry_grid.rowHeight(0)
    original_status_width = window.status_grid.width()
    configured_characters = window._cell_size_defaults["column_chars"]["Khách hàng"]
    assert window.entry_grid.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert window.worksheet_scrollbar.orientation() == Qt.Orientation.Vertical

    window.set_entry_zoom(120)
    assert window.entry_zoom_label.text() == "120%"
    assert window.entry_grid.columnWidth(0) > original_width
    assert window.entry_grid.rowHeight(0) > original_height
    assert window.status_grid.width() > original_status_width
    assert window._cell_size_defaults["column_chars"]["Khách hàng"] == configured_characters
    window.set_entry_zoom(100)
    assert window.entry_grid.columnWidth(0) == original_width
    assert window.entry_grid.rowHeight(0) == original_height
    window.close()


def test_desktop_ctrl_wheel_zoom_request_updates_zoom_slider(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window.entry_grid.zoomRequested.emit(10)
    assert window.entry_zoom_slider.value() == 110
    window.entry_grid.zoomRequested.emit(-10)
    assert window.entry_zoom_slider.value() == 100
    window.close()


def test_desktop_default_cell_sizes_use_character_standards(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window._cell_size_defaults = {
        "column_chars": {header: 12 for header in ENTRY_HEADERS},
        "row_height": 48,
    }
    window._cell_size_defaults["column_chars"]["Khách hàng"] = 15
    for header in ("Kích thước X", "Kích thước Y", "Kích thước Z"):
        window._cell_size_defaults["column_chars"][header] = 6
    window.apply_default_cell_sizes()

    window.entry_grid.setItem(0, ENTRY_HEADERS.index("Khách hàng"), QTableWidgetItem("Khách hàng mười lăm"))
    window.entry_grid.setItem(0, ENTRY_HEADERS.index("Kích thước X"), QTableWidgetItem("123456"))
    window.apply_default_cell_sizes()
    company = window.entry_grid.columnWidth(ENTRY_HEADERS.index("Khách hàng"))
    dimension = window.entry_grid.columnWidth(ENTRY_HEADERS.index("Kích thước X"))
    assert company > dimension
    assert window.entry_grid.columnWidth(ENTRY_HEADERS.index("Kích thước Y")) == dimension
    assert window.entry_grid.rowHeight(0) == 48
    window.close()


def test_desktop_configured_column_width_stays_fixed_and_manual_resize_updates_setting():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    grid.setItemDelegate(FormulaItemDelegate(grid))
    grid.set_column_character_limits({header: 15 for header in ENTRY_HEADERS})
    column = ENTRY_HEADERS.index("Khách hàng")
    fixed_width = grid.columnWidth(column)
    grid.setItem(0, column, QTableWidgetItem("Nội dung dài hơn rất nhiều so với chuẩn"))
    assert grid.columnWidth(column) == fixed_width

    grid.setColumnWidth(column, 250)
    assert grid.columnWidth(column) == 250
    assert grid._column_character_limits["Khách hàng"] > 15


def test_desktop_dimension_columns_start_at_configured_default_characters(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window._cell_size_defaults = {
        "column_chars": dict(DEFAULT_CELL_SIZE_SETTINGS["column_chars"]),
        "row_height": DEFAULT_CELL_SIZE_SETTINGS["row_height"],
    }
    window.apply_default_cell_sizes()
    widths = [window.entry_grid.columnWidth(ENTRY_HEADERS.index(header)) for header in ("Kích thước X", "Kích thước Y", "Kích thước Z")]
    assert widths[0] == widths[1] == widths[2]
    assert window._cell_size_defaults["column_chars"]["Kích thước X"] == 8

    x_column = ENTRY_HEADERS.index("Kích thước X")
    window.entry_grid.setColumnWidth(x_column, 160)
    assert window._cell_size_defaults["column_chars"]["Kích thước X"] > 8
    window.close()


def test_desktop_cell_size_apply_accepts_and_updates_width(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    dialog = SpreadsheetSizeDialog(window._cell_size_defaults, DEFAULT_CELL_SIZE_SETTINGS, window)
    dialog.settingsApplied.connect(window.apply_cell_size_settings)
    dialog.column_characters["Kích thước X"].setValue(9)
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Apply).click()
    assert dialog.result() == dialog.DialogCode.Rejected
    assert window.entry_grid.columnWidth(ENTRY_HEADERS.index("Kích thước X")) > window.entry_grid.columnWidth(ENTRY_HEADERS.index("Kích thước Y"))
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel).click()
    assert dialog.result() == dialog.DialogCode.Rejected
    window.close()


def test_desktop_cell_size_dialog_restores_factory_defaults():
    app = QApplication.instance() or QApplication([])
    settings = {"column_chars": {header: 12 for header in ENTRY_HEADERS}, "row_height": 48}
    dialog = SpreadsheetSizeDialog(settings, DEFAULT_CELL_SIZE_SETTINGS)
    dialog._restore_defaults()
    assert dialog.column_characters["Tên sản phẩm"].value() == 45
    assert dialog.column_characters["Kích thước X"].value() == 8
    assert dialog.row_height.value() == 65


def test_desktop_long_unbroken_text_wraps_and_expands_row_height():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    column = ENTRY_HEADERS.index("Khách hàng")
    grid.set_column_character_limits({header: 6 for header in ENTRY_HEADERS})
    width = grid.columnWidth(column)
    grid.setItem(0, column, QTableWidgetItem("BIGSTONE111111222222333333"))
    wrapped_height = grid.rowHeight(0)
    assert grid.columnWidth(column) == width
    assert wrapped_height > 24

    grid.setColumnWidth(column, 400)
    assert grid.rowHeight(0) < wrapped_height


def test_desktop_delegate_enables_wrap_for_unbroken_text():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    grid.setItemDelegate(FormulaItemDelegate(grid))
    grid.setWordWrap(True)
    item = QTableWidgetItem("BIGSTONE111111222222333333")
    grid.setItem(0, 0, item)
    option = QStyleOptionViewItem()
    grid.itemDelegate().initStyleOption(option, grid.model().index(0, 0))
    assert option.features & QStyleOptionViewItem.ViewItemFeature.WrapText


def test_desktop_entry_grid_autosum(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window.entry_grid.setItem(0, 3, QTableWidgetItem("10"))
    window.entry_grid.setItem(1, 3, QTableWidgetItem("20"))
    window.entry_grid.clearSelection()
    window.entry_grid.setRangeSelected(QTableWidgetSelectionRange(0, 3, 1, 3), True)
    window.insert_auto_sum()
    assert window.entry_grid.formula_for_item(window.entry_grid.item(2, 3)) == "=SUM(D1:D2)"
    assert window.entry_grid.item(2, 3).text() == "30"
    window.close()
    app.processEvents()


def test_desktop_entry_grid_has_excel_headers_and_formula_autocomplete(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))

    assert window.entry_grid.horizontalHeaderItem(0).text().startswith("A\n")
    assert window.entry_grid.horizontalHeaderItem(3).text().startswith("D\n")
    window.formula_bar.setText("=")
    window.formula_bar.textEdited.emit("=")
    assert window.formula_bar.completer().completionPrefix() == ""
    assert window.formula_bar.completer().completionCount() == len(window.formula_bar.completer().model().stringList())
    window.formula_bar.setText("=SUM")
    window.formula_bar.textEdited.emit("=SUM")
    assert window.formula_bar.completer().completionPrefix() == "SUM"
    assert "SUM" in window.formula_bar.completer().model().stringList()

    window.close()
    app.processEvents()


def test_desktop_formula_bar_inserts_selected_cell_reference(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window.entry_grid.setItem(0, 0, QTableWidgetItem("10"))
    window.entry_grid.setItem(1, 0, QTableWidgetItem("20"))
    window.entry_grid.setCurrentCell(0, 3)

    window.formula_bar.setText("=SUM(")
    window.formula_bar.textEdited.emit("=SUM(")
    window.entry_grid.clearSelection()
    window.entry_grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 0), True)
    window.insert_formula_reference(window.entry_grid.item(0, 0))
    window.formula_bar.setText(f"{window.formula_bar.text()})")
    window.apply_formula_bar()

    assert window.entry_grid.formula_for_item(window.entry_grid.item(0, 3)) == "=SUM(A1:A2)"
    assert window.entry_grid.item(0, 3).text() == "30"
    assert window.cell_address.text() == "D1"

    window.close()
    app.processEvents()


def test_desktop_ctrl_reference_selection_inserts_range_in_formula_bar(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window.entry_grid.setCurrentCell(0, 3)
    window.formula_bar.setText("=SUM(")
    window.formula_bar.textEdited.emit("=SUM(")

    assert window.entry_grid.formula_reference_mode is True
    window.entry_grid.formulaReferenceSelected.emit(0, 0, 1, 1)

    assert window.formula_bar.text() == "=SUM(A1:B2"
    window.close()
    app.processEvents()


def test_desktop_escape_cancels_pending_formula_bar_reference_edit(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    target = window.entry_grid.item(0, 3)
    target.setText("Giữ nguyên")
    window.entry_grid.setCurrentCell(0, 3)
    window.formula_bar.setText("=SUM(")
    window.formula_bar.textEdited.emit("=SUM(")
    window.entry_grid.formulaReferenceSelected.emit(0, 0, 1, 1)

    assert window.entry_grid.formula_reference_mode is True
    assert window.formula_bar.text() == "=SUM(A1:B2"
    assert window.eventFilter(window.formula_bar, QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier,
    )) is True
    assert window.entry_grid.formula_reference_mode is False
    assert window._formula_edit_target is None
    assert window.formula_bar.text() == "Giữ nguyên"
    assert target.text() == "Giữ nguyên"
    window.close()
    app.processEvents()


def test_desktop_formula_entry_completes_unmatched_parentheses(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window.entry_grid.setItem(0, 0, QTableWidgetItem("10"))
    window.entry_grid.setCurrentCell(0, 3)
    window.formula_bar.setText("=SUM(A1")
    window.formula_bar.textEdited.emit("=SUM(A1")
    window.apply_formula_bar()

    assert window.entry_grid.formula_for_item(window.entry_grid.item(0, 3)) == "=SUM(A1)"
    assert complete_formula_parentheses('=IF(A1="(", SUM(A1)') == '=IF(A1="(", SUM(A1))'
    assert complete_formula_parentheses("=SUM(A1))") == "=SUM(A1))"
    window.close()
    app.processEvents()


def test_desktop_f4_cycles_formula_reference_locks():
    app = QApplication.instance() or QApplication([])
    editor = QLineEdit("=SUM(A1)")
    editor.setCursorPosition(6)

    assert cycle_formula_reference_lock(editor) is True
    assert editor.text() == "=SUM($A$1)"
    assert cycle_formula_reference_lock(editor) is True
    assert editor.text() == "=SUM(A$1)"
    assert cycle_formula_reference_lock(editor) is True
    assert editor.text() == "=SUM($A1)"
    assert cycle_formula_reference_lock(editor) is True
    assert editor.text() == "=SUM(A1)"


def test_desktop_f4_cycles_reference_in_formula_bar(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    window.formula_bar.setText("=A1")
    window.formula_bar.setCursorPosition(2)

    assert window.eventFilter(window.formula_bar, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F4, Qt.KeyboardModifier.NoModifier)) is True
    assert window.formula_bar.text() == "=$A$1"
    window.close()
    app.processEvents()


def test_desktop_ctrl_formula_range_selection_appends_reference_in_cell_editor():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(3, 3)
    grid.setItem(2, 2, QTableWidgetItem("=SUM("))
    grid.setCurrentCell(2, 2)
    grid.editItem(grid.item(2, 2))
    editor = grid.findChild(QLineEdit)
    assert editor is not None
    editor.setText("=SUM(")

    grid._append_in_cell_formula_reference(0, 0, 1, 1)

    assert editor.text() == "=SUM(A1:B2"


def test_desktop_fill_formula_range_translates_relative_and_absolute_references():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(3, 4)
    grid.setItem(0, 0, QTableWidgetItem("2"))
    grid.setItem(0, 1, QTableWidgetItem("3"))
    grid.setItem(0, 2, QTableWidgetItem("=A1+B1+$A$1+A$1+$A1"))

    grid.fill_formula_range((0, 2, 0, 2), (2, 2))

    assert grid.formula_for_item(grid.item(1, 2)) == "=A2+B2+$A$1+A$1+$A2"
    assert grid.formula_for_item(grid.item(2, 2)) == "=A3+B3+$A$1+A$1+$A3"
    grid.undo()
    assert grid.item(1, 2) is None


def test_desktop_fill_formula_range_translates_columns():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 4)
    grid.setItem(0, 0, QTableWidgetItem("2"))
    grid.setItem(0, 1, QTableWidgetItem("=A1+$A1+A$1+$A$1"))

    grid.fill_formula_range((0, 1, 0, 1), (0, 3))

    assert grid.formula_for_item(grid.item(0, 2)) == "=B1+$A1+B$1+$A$1"
    assert grid.formula_for_item(grid.item(0, 3)) == "=C1+$A1+C$1+$A$1"


def test_desktop_fill_formula_range_marks_references_before_first_column_as_ref_error():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 2)
    grid.setItem(0, 1, QTableWidgetItem("=A1"))

    grid.fill_formula_range((0, 1, 0, 1), (0, 0))

    assert grid.formula_for_item(grid.item(0, 0)) == "=#REF!"


def test_desktop_fill_formula_range_uses_dominant_drag_direction():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(4, 5)
    grid.setItem(0, 1, QTableWidgetItem("=A1"))

    grid.fill_formula_range((0, 1, 0, 1), (2, 4))

    assert grid.formula_for_item(grid.item(0, 2)) == "=B1"
    assert grid.formula_for_item(grid.item(0, 4)) == "=D1"
    assert grid.item(1, 1) is None


def test_desktop_formula_handle_double_click_fills_adjacent_rows():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(5, 3)
    for row, value in enumerate(("2", "3", "4")):
        grid.setItem(row, 0, QTableWidgetItem(value))
    grid.setItem(0, 1, QTableWidgetItem("=A1*2"))

    grid.autofill_formula_down((0, 1, 0, 1))

    assert grid.formula_for_item(grid.item(1, 1)) == "=A2*2"
    assert grid.formula_for_item(grid.item(2, 1)) == "=A3*2"
    assert grid.item(3, 1) is None


def test_desktop_fill_handle_extends_numeric_series_downward():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(8, 1)
    for row, value in enumerate(("1", "2", "3")):
        grid.setItem(row, 0, QTableWidgetItem(value))

    grid.fill_formula_range((0, 0, 2, 0), (6, 0))

    assert [grid.item(row, 0).text() for row in range(7)] == ["1", "2", "3", "4", "5", "6", "7"]


def test_desktop_f2_edits_current_cell_and_delete_clears_it():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 1)
    grid.setItem(0, 0, QTableWidgetItem("Giá trị"))
    grid.setCurrentCell(0, 0)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier))
    editor = grid.findChild(QLineEdit)
    assert editor is not None
    assert editor.cursorPosition() == len("Giá trị")
    grid.closePersistentEditor(grid.item(0, 0))
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier))
    assert grid.item(0, 0).text() == ""


def test_desktop_ctrl_a_selects_used_range_then_entire_worksheet():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(4, 4)
    grid.setItem(1, 1, QTableWidgetItem("A"))
    grid.setItem(2, 2, QTableWidgetItem("B"))

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier))
    assert grid._selection_bounds() == (1, 1, 2, 2)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier))
    assert grid._selection_bounds() == (0, 0, 3, 3)


def test_desktop_ctrl_arrow_navigates_to_contiguous_data_edges():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(5, 5)
    for column in (0, 1, 2):
        grid.setItem(1, column, QTableWidgetItem(str(column)))
    grid.setCurrentCell(1, 0)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (1, 2)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (1, 4)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (1, 2)


def test_desktop_ctrl_shift_arrow_extends_selection_to_data_edge():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(5, 5)
    for column in (0, 1, 2):
        grid.setItem(1, column, QTableWidgetItem(str(column)))
    grid.setCurrentCell(1, 0)

    grid.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Right,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    ))
    assert (grid.currentRow(), grid.currentColumn()) == (1, 2)
    assert grid._selection_bounds() == (1, 0, 1, 2)


def test_desktop_repeated_ctrl_shift_arrow_preserves_initial_selection_anchor():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(5, 5)
    for column in (0, 1, 2):
        grid.setItem(1, column, QTableWidgetItem(str(column)))
    for row in (1, 2, 3):
        grid.setItem(row, 2, QTableWidgetItem(str(row)))
    grid.setCurrentCell(1, 0)
    modifiers = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, modifiers))
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, modifiers))
    assert (grid.currentRow(), grid.currentColumn()) == (3, 2)
    assert grid._selection_bounds() == (1, 0, 3, 2)


def test_desktop_shift_arrow_extends_selection_one_cell_at_a_time():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(4, 4)
    grid.setCurrentCell(1, 1)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier))
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (2, 2)
    assert grid._selection_bounds() == (1, 1, 2, 2)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (2, 1)
    assert grid._selection_bounds() == (1, 1, 2, 1)


def test_desktop_home_and_ctrl_home_end_navigate_worksheet():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(5, 5)
    grid.setItem(2, 1, QTableWidgetItem("first"))
    grid.setItem(4, 3, QTableWidgetItem("last"))
    grid.setCurrentCell(2, 4)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (2, 0)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.ControlModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (0, 0)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (4, 3)


def test_desktop_ctrl_shift_home_end_extends_selection_to_worksheet_bounds():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(5, 5)
    grid.setItem(4, 3, QTableWidgetItem("last"))
    grid.setCurrentCell(2, 2)

    grid.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Home,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    ))
    assert (grid.currentRow(), grid.currentColumn()) == (0, 0)
    assert grid._selection_bounds() == (0, 0, 2, 2)

    grid.setCurrentCell(1, 1)
    grid.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_End,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    ))
    assert (grid.currentRow(), grid.currentColumn()) == (4, 3)
    assert grid._selection_bounds() == (1, 1, 4, 3)


def test_desktop_shift_space_and_ctrl_space_select_active_row_or_column():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(4, 5)
    grid.setCurrentCell(2, 3)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.ShiftModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (2, 0)
    assert grid._selection_bounds() == (2, 0, 2, 4)

    grid.setCurrentCell(1, 3)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (0, 3)
    assert grid._selection_bounds() == (0, 3, 3, 3)


def test_desktop_shift_home_end_extends_selection_across_active_row():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(4, 5)
    grid.setCurrentCell(2, 3)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.ShiftModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (2, 0)
    assert grid._selection_bounds() == (2, 0, 2, 3)

    grid.setCurrentCell(1, 1)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.ShiftModifier))
    assert (grid.currentRow(), grid.currentColumn()) == (1, 4)
    assert grid._selection_bounds() == (1, 1, 1, 4)


def test_desktop_ctrl_plus_and_minus_insert_and_delete_selected_rows():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(3, 2)
    for row, value in enumerate(("first", "middle", "last")):
        grid.setItem(row, 0, QTableWidgetItem(value))
    grid.setCurrentCell(1, 0)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier))
    assert grid.rowCount() == 4
    assert grid.item(2, 0).text() == "middle"
    assert grid.item(3, 0).text() == "last"

    grid.setRangeSelected(QTableWidgetSelectionRange(1, 0, 2, 1), True)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Minus, Qt.KeyboardModifier.ControlModifier))
    assert grid.rowCount() == 2
    assert [grid.item(row, 0).text() for row in range(2)] == ["first", "last"]


def test_desktop_ctrl_semicolon_enters_date_and_time_into_editable_selection():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(2, 2)
    grid.today_provider = lambda: __import__("datetime").date(2026, 9, 18)
    grid.current_time_provider = lambda: "14:30"
    grid.setItem(0, 1, QTableWidgetItem("locked"))
    grid.item(0, 1).setFlags(grid.item(0, 1).flags() & ~Qt.ItemFlag.ItemIsEditable)
    grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, 1), True)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Semicolon, Qt.KeyboardModifier.ControlModifier))
    assert grid.item(0, 0).text() == "2026-09-18"
    assert grid.item(0, 1).text() == "locked"

    grid.setCurrentCell(1, 0)
    grid.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Semicolon,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    ))
    assert grid.item(1, 0).text() == "14:30"


def test_desktop_ctrl_d_copies_top_selected_row_and_translates_formulas():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(3, 3)
    grid.setItem(0, 0, QTableWidgetItem("5"))
    grid.setItem(0, 1, QTableWidgetItem("=A1"))
    grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 2, 1), True)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier))
    assert grid.item(1, 0).text() == "5"
    assert grid.formula_for_item(grid.item(1, 1)) == "=A2"
    assert grid.formula_for_item(grid.item(2, 1)) == "=A3"


def test_desktop_ctrl_r_copies_left_selected_column_and_translates_formulas():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(3, 3)
    grid.setItem(0, 0, QTableWidgetItem("5"))
    grid.setItem(1, 0, QTableWidgetItem("=A1"))
    grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 2), True)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier))
    assert grid.item(0, 1).text() == "5"
    assert grid.formula_for_item(grid.item(1, 1)) == "=B1"
    assert grid.formula_for_item(grid.item(1, 2)) == "=C1"


def test_desktop_formula_cells_display_standard_error_codes():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(2, 2)
    grid.setItem(0, 0, QTableWidgetItem("=1/0"))

    assert grid.item(0, 0).text() == "#DIV/0!"
    assert "Không thể chia cho 0" in grid.item(0, 0).toolTip()


def test_desktop_entry_grid_allows_blank_customer_and_zero_quantity_but_warns_for_invalid_quantity():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(2, len(ENTRY_HEADERS))
    customer = ENTRY_HEADERS.index("Khách hàng")
    quantity = ENTRY_HEADERS.index("Số lượng")
    grid.setItem(0, quantity, QTableWidgetItem("zero"))

    assert grid.item(0, customer) is None
    assert grid.item(0, quantity).toolTip() == "Số lượng phải là số không âm."

    grid.item(0, quantity).setText("0")
    assert grid.item(0, customer) is None
    assert grid.item(0, quantity).toolTip() == ""


def test_desktop_ctrl_enter_fills_selected_editable_cells():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(2, 2)
    grid.setItem(0, 0, QTableWidgetItem("Cũ"))
    grid.setItem(0, 1, QTableWidgetItem("Cũ"))
    locked = QTableWidgetItem("Khóa")
    locked.setFlags(locked.flags() & ~Qt.ItemFlag.ItemIsEditable)
    grid.setItem(1, 0, locked)
    grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)

    assert grid.fill_selected_cells("=SUM(A1") == 3
    assert [grid.formula_for_item(grid.item(row, column)) for row, column in ((0, 0), (0, 1), (1, 1))] == ["=SUM(A1", "=SUM(A1", "=SUM(A1"]
    assert grid.item(1, 0).text() == "Khóa"


def test_desktop_ctrl_enter_uses_active_cell_value_when_grid_has_focus():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(2, 2)
    grid.setItem(0, 0, QTableWidgetItem("=1+1"))
    grid.setCurrentCell(0, 0)
    grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)

    grid.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier,
    ))
    assert [grid.formula_for_item(grid.item(row, column)) for row in range(2) for column in range(2)] == [
        "=1+1", "=1+1", "=1+1", "=1+1",
    ]


def test_desktop_number_display_format_preserves_raw_values_for_copy_and_undo():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 1)
    item = QTableWidgetItem("1234.5")
    grid.setItem(0, 0, item)
    grid.setCurrentCell(0, 0)
    grid._begin_history_transaction()
    grid.apply_display_format(item, "#,##0.00")
    grid._commit_history_transaction()

    assert item.text() == "1,234.50"
    assert grid.value_for_item(item) == "1234.5"
    grid.copy_to_clipboard()
    assert QApplication.clipboard().text() == "1234.5"
    grid.undo()
    assert grid.item(0, 0).text() == "1234.5"


def test_desktop_number_display_format_keeps_formula_bar_on_raw_value(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    item = QTableWidgetItem("42")
    window.entry_grid.setItem(0, 0, item)
    window.entry_grid.setCurrentCell(0, 0)

    window.format_selected_numbers("0.00")
    window.update_formula_bar(0, 0)
    assert item.text() == "42.00"
    assert window.formula_bar.text() == "42"
    window.close()
    app.processEvents()


def test_desktop_formula_uses_raw_value_from_formatted_numeric_cells():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 2)
    source = QTableWidgetItem("1234.5")
    grid.setItem(0, 0, source)
    grid.setItem(0, 1, QTableWidgetItem("=A1+0.5"))
    grid.apply_display_format(source, "#,##0.00")
    grid.recalculate_formulas()

    assert source.text() == "1,234.50"
    assert grid.item(0, 1).text() == "1235"


def test_desktop_date_display_format_preserves_iso_raw_value():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 1)
    item = QTableWidgetItem("2026-09-19")
    grid.setItem(0, 0, item)

    grid.apply_display_format(item, "dd/MM/yyyy")
    assert item.text() == "19/09/2026"
    assert grid.value_for_item(item) == "2026-09-19"
    grid.apply_display_format(item, "General")
    assert item.text() == "2026-09-19"


def test_desktop_cell_format_applies_display_font_and_border_to_selection(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    for column in range(2):
        window.entry_grid.setItem(0, column, QTableWidgetItem("1234.5"))
    window.entry_grid.setCurrentCell(0, 0)
    window.entry_grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, 1), True)

    window.apply_cell_format({
        "display_format": "#,##0.00", "bold": True, "italic": True, "underline": False, "border": True,
    })
    for column in range(2):
        item = window.entry_grid.item(0, column)
        assert item.text() == "1,234.50"
        assert window.entry_grid.value_for_item(item) == "1234.5"
        assert item.font().bold() and item.font().italic() and not item.font().underline()
        assert item.data(Qt.ItemDataRole.UserRole + 20) is True
    window.close()
    app.processEvents()


def test_desktop_ctrl_1_requests_cell_format_dialog():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 1)
    requested = []
    grid.cellFormatRequested.connect(lambda: requested.append(True))

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier))
    assert requested == [True]


def test_desktop_ctrl_0_hides_selected_columns_and_undo_restores_them():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(2, len(ENTRY_HEADERS))
    status_column = ENTRY_HEADERS.index("Trạng thái S/P")
    grid.setColumnHidden(status_column, True)
    grid.setCurrentCell(0, 1)
    grid.setRangeSelected(QTableWidgetSelectionRange(0, 1, 1, 2), True)
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier))
    assert grid.isColumnHidden(1)
    assert grid.isColumnHidden(status_column)
    grid.undo()
    assert not grid.isColumnHidden(1)
    assert grid.isColumnHidden(status_column)


def test_desktop_ctrl_shift_0_reveals_user_columns_but_not_status_column():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    status_column = ENTRY_HEADERS.index("Trạng thái S/P")
    grid.setColumnHidden(1, True)
    grid.setColumnHidden(2, True)
    grid.setColumnHidden(status_column, True)
    grid.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_0,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    ))
    assert not grid.isColumnHidden(1) and not grid.isColumnHidden(2)
    assert grid.isColumnHidden(status_column)


def test_desktop_ctrl_9_hides_active_row_and_undo_restores_it():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(3, len(ENTRY_HEADERS))
    grid.setCurrentCell(1, 0)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_9, Qt.KeyboardModifier.ControlModifier))
    assert grid.isRowHidden(1)
    grid.undo()
    assert not grid.isRowHidden(1)
    grid.redo()
    assert grid.isRowHidden(1)


def test_desktop_ctrl_shift_9_reveals_all_hidden_rows():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(3, len(ENTRY_HEADERS))
    grid.setRowHidden(0, True)
    grid.setRowHidden(2, True)

    grid.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_9,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    ))
    assert not grid.isRowHidden(0)
    assert not grid.isRowHidden(2)


def test_desktop_go_to_address_moves_only_for_valid_in_grid_a1_references():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(3, 4)
    grid.setCurrentCell(0, 0)

    assert grid.go_to_address("$D$3") is True
    assert (grid.currentRow(), grid.currentColumn()) == (2, 3)
    assert grid.go_to_address("E3") is False
    assert grid.go_to_address("A0") is False
    assert grid.go_to_address("not an address") is False
    assert (grid.currentRow(), grid.currentColumn()) == (2, 3)


def test_desktop_find_and_replace_worksheet_cells():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(2, 2)
    grid.setItem(0, 0, QTableWidgetItem("Bolt M10"))
    grid.setItem(0, 1, QTableWidgetItem("bolt M12"))
    grid.setItem(1, 0, QTableWidgetItem("Nut M10"))
    grid.setCurrentCell(1, 1)

    assert grid.find_next("bolt") is True
    assert (grid.currentRow(), grid.currentColumn()) == (0, 0)
    assert grid.replace_current("Bolt", "Vít", match_case=True) is True
    assert grid.replace_all("m10", "M8") == 2
    assert [grid.item(0, 0).text(), grid.item(1, 0).text()] == ["Vít M8", "Nut M8"]


def test_desktop_f3_repeats_last_find_in_both_directions():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 3)
    for column in (0, 2):
        grid.setItem(0, column, QTableWidgetItem("bolt"))
    grid.setCurrentCell(0, 1)

    assert grid.find_next("bolt") is True
    assert grid.currentColumn() == 2
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F3, Qt.KeyboardModifier.NoModifier))
    assert grid.currentColumn() == 0
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F3, Qt.KeyboardModifier.ShiftModifier))
    assert grid.currentColumn() == 2


def test_desktop_fill_handle_extends_numeric_series_across_columns():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 7)
    for column, value in enumerate(("10", "15", "20")):
        grid.setItem(0, column, QTableWidgetItem(value))

    grid.fill_formula_range((0, 0, 0, 2), (0, 6))

    assert [grid.item(0, column).text() for column in range(7)] == ["10", "15", "20", "25", "30", "35", "40"]


def test_desktop_fill_handle_extends_date_series_and_text_number_series():
    app = QApplication.instance() or QApplication([])
    dates = SpreadsheetEntryGrid(5, 1)
    for row, value in enumerate(("16/09/2026", "17/09/2026")):
        dates.setItem(row, 0, QTableWidgetItem(value))
    dates.fill_formula_range((0, 0, 1, 0), (4, 0))
    assert [dates.item(row, 0).text() for row in range(5)] == ["16/09/2026", "17/09/2026", "18/09/2026", "19/09/2026", "20/09/2026"]

    codes = SpreadsheetEntryGrid(1, 5)
    for column, value in enumerate(("SP-001", "SP-002")):
        codes.setItem(0, column, QTableWidgetItem(value))
    codes.fill_formula_range((0, 0, 0, 1), (0, 4))
    assert [codes.item(0, column).text() for column in range(5)] == ["SP-001", "SP-002", "SP-003", "SP-004", "SP-005"]


def test_desktop_fill_handle_extends_single_date_by_one_day():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(4, 1)
    grid.setItem(0, 0, QTableWidgetItem("2026-12-31"))

    grid.fill_formula_range((0, 0, 0, 0), (3, 0))

    assert [grid.item(row, 0).text() for row in range(4)] == ["2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"]


def test_desktop_fill_handle_ctrl_copy_repeats_numeric_source_instead_of_series():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(6, 1)
    for row, value in enumerate(("1", "2", "3")):
        grid.setItem(row, 0, QTableWidgetItem(value))

    grid.fill_formula_range((0, 0, 2, 0), (5, 0), copy_only=True)

    assert [grid.item(row, 0).text() for row in range(6)] == ["1", "2", "3", "1", "2", "3"]


def test_desktop_fill_handle_extends_weekdays_and_months():
    app = QApplication.instance() or QApplication([])
    weekdays = SpreadsheetEntryGrid(5, 1)
    weekdays.setItem(0, 0, QTableWidgetItem("Thứ Sáu"))
    weekdays.fill_formula_range((0, 0, 0, 0), (4, 0))
    assert [weekdays.item(row, 0).text() for row in range(5)] == ["Thứ Sáu", "Thứ Bảy", "Chủ Nhật", "Thứ Hai", "Thứ Ba"]

    months = SpreadsheetEntryGrid(1, 5)
    months.setItem(0, 0, QTableWidgetItem("November"))
    months.fill_formula_range((0, 0, 0, 0), (0, 4))
    assert [months.item(0, column).text() for column in range(5)] == ["November", "December", "January", "February", "March"]


def test_desktop_entry_grid_paste_expands_rows():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 2)
    QApplication.clipboard().setText("A\tB\nC\tD\nE\tF")
    grid.setCurrentCell(0, 0)
    grid.paste_from_clipboard()

    assert grid.rowCount() == 3
    assert grid.item(2, 0).text() == "E"
    assert grid.item(2, 1).text() == "F"


def test_desktop_entry_grid_prioritizes_excel_cell_text_over_clipboard_image():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(2, 2)
    mime = QMimeData()
    mime.setText("A\tB\nC\tD")
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.red)
    mime.setImageData(image)
    QApplication.clipboard().setMimeData(mime)
    grid.setCurrentCell(0, 0)

    grid.paste_from_clipboard()

    assert [[grid.item(row, column).text() for column in range(2)] for row in range(2)] == [["A", "B"], ["C", "D"]]


def test_desktop_entry_grid_uses_requested_product_columns(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    clear_entry_draft(__import__("datetime").date.today())
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    window = ProductMasterWindow(service)
    headers = [window.entry_grid.horizontalHeaderItem(column).text().split("\n", 1)[1]
               for column in range(window.entry_grid.columnCount())]

    assert headers == [
        "Khách Hàng", "Ảnh Sản Phẩm", "Tên Sản Phẩm", "Số Lượng", "Đơn Vị", "Vật Liệu",
        "Người Đặt", "Xử Lý Bề Mặt", "Đặt Ngoài", "X", "Y", "Z", "Ghi Chú",
        "Mã QR", "Mã Sản Phẩm", "Trạng Thái S/P",
    ]
    assert isinstance(window.entry_grid.horizontalHeader(), SpreadsheetHeader)
    assert window.entry_grid.horizontalHeader().font().bold()
    window.selected_delivery_date = __import__("datetime").date(2026, 9, 26)
    window._update_entry_delivery_date_labels()
    values = ["HMS", "", "Chi tiết A", "12", "pcs", "Thép", "Anh Nam", "Sơn", "Công ty Gia công A", "100", "50", "20", "Gấp", "", "", "Mới"]
    for column, value in enumerate(values):
        window.entry_grid.setItem(0, column, QTableWidgetItem(value))
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    window.save_entry_rows()
    product = service.list_products().items[0]
    assert (product.requester, product.surface_treatment, product.outsourced, product.outsourced_company, product.size, product.delivery_schedule) == (
        "Anh Nam", "Sơn", True, "Công ty Gia công A", "100 x 50 x 20", __import__("datetime").date(2026, 9, 26)
    )
    window.close()
    clear_entry_draft(window.selected_delivery_date)
    app.processEvents()


def test_desktop_product_and_qr_codes_are_generated_from_row_data(tmp_path):
    app = QApplication.instance() or QApplication([])
    clear_entry_draft(__import__("datetime").date.today())
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    company_column = ENTRY_HEADERS.index("Khách hàng")
    code_column = ENTRY_HEADERS.index("Mã sản phẩm")
    qr_column = ENTRY_HEADERS.index("Mã QR")
    status_column = ENTRY_HEADERS.index("Trạng thái S/P")
    assert window.entry_grid.item(0, code_column).text() == ""

    for column, value in ((company_column, "Công ty HMS"), (ENTRY_HEADERS.index("Tên sản phẩm"), "Trục dẫn hướng"),
                          (ENTRY_HEADERS.index("Số lượng"), "1"),
                           (ENTRY_HEADERS.index("Kích thước X"), "220"), (ENTRY_HEADERS.index("Kích thước Y"), "47.1"),
                           (ENTRY_HEADERS.index("Kích thước Z"), "10")):
        window.entry_grid.setItem(0, column, QTableWidgetItem(value))
    expected_code = window.entry_grid.item(0, code_column).text()
    assert expected_code
    assert window.entry_grid.item(0, code_column).text() == expected_code
    assert window.entry_grid.item(0, qr_column).text() == f"SP:{expected_code}|KH:Công ty HMS"
    assert window.entry_grid.item(0, qr_column).data(Qt.ItemDataRole.UserRole + 21)
    assert window.entry_grid.item(0, status_column).text() == "Mới"
    assert window.entry_grid.item(0, status_column).background().color().name() == "#dceeff"
    assert product_code_value("Công ty HMS", "Trục dẫn hướng", ("220", "47.1", "10"), window.selected_delivery_date.isoformat(), 0) == expected_code
    assert product_code_value("Công ty HMS", "Sản phẩm khác", ("1", "2", "3"), "2026-12-31", 0) == "CTH-SPK-261231-R001"
    assert product_code_value("Công ty HMS", "", ("", "", ""), "2026-12-31", 1) == "CTH-NO-261231-R002"
    assert not (window.entry_grid.item(0, qr_column).flags() & Qt.ItemFlag.ItemIsEditable)
    assert not (window.entry_grid.item(0, code_column).flags() & Qt.ItemFlag.ItemIsEditable)
    assert product_qr_value(expected_code, "  Công   ty HMS ") == f"SP:{expected_code}|KH:Công ty HMS"
    window.close()
    clear_entry_draft(window.selected_delivery_date)
    app.processEvents()

    window.close()
    app.processEvents()


def test_desktop_product_qr_label_is_50x30_mm_at_1500_dpi():
    label = QImage()
    label.loadFromData(product_qr_label_png("SP:CTH-NODATE-R001|KH:Công ty HMS", "CTH-NODATE-R001", "Trục dẫn hướng", "220 x 47.1 x 10", __import__("datetime").date(2026, 9, 18)), "PNG")

    assert label.size().width() == 2953
    assert label.size().height() == 1772


def test_desktop_double_click_qr_copies_label_image_to_clipboard(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    company_column = ENTRY_HEADERS.index("Khách hàng")
    qr_column = ENTRY_HEADERS.index("Mã QR")
    for column, value in ((company_column, "Công ty HMS"), (ENTRY_HEADERS.index("Tên sản phẩm"), "Trục dẫn hướng"),
                          (ENTRY_HEADERS.index("Số lượng"), "1")):
        window.entry_grid.setItem(0, column, QTableWidgetItem(value))

    window._qr_copy_scale = 100
    window.handle_entry_grid_double_click(window.entry_grid.item(0, qr_column))

    assert QApplication.clipboard().image().size() == QImage(591, 354, QImage.Format.Format_ARGB32).size()
    assert 'width:141.73pt;height:85.04pt' in QApplication.clipboard().mimeData().html()
    assert any(label.text() == "Đã copy tem QR (100%)" for label in window.entry_grid.viewport().findChildren(QLabel))
    window.close()
    app.processEvents()


def test_desktop_qr_copy_scale_resizes_clipboard_label(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    qr_column = ENTRY_HEADERS.index("Mã QR")
    for column, value in ((ENTRY_HEADERS.index("Khách hàng"), "Công ty HMS"), (ENTRY_HEADERS.index("Tên sản phẩm"), "Trục dẫn hướng"),
                          (ENTRY_HEADERS.index("Số lượng"), "1")):
        window.entry_grid.setItem(0, column, QTableWidgetItem(value))

    window._qr_copy_scale = 150
    window.copy_qr_label(window.entry_grid.item(0, qr_column))

    assert QApplication.clipboard().image().size() == QImage(886, 531, QImage.Format.Format_ARGB32).size()
    assert 'width:212.60pt;height:127.56pt' in QApplication.clipboard().mimeData().html()
    window.close()
    app.processEvents()


def test_desktop_excel_style_toolbar_formats_selected_cell(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    item = QTableWidgetItem("Định dạng")
    window.entry_grid.setItem(0, 0, item)
    window.entry_grid.setCurrentCell(0, 0)

    window.format_selected_cells("underline")
    window.format_selected_cells("border")
    assert item.font().underline()
    assert item.data(Qt.ItemDataRole.UserRole + 20) is True
    window.format_selected_cells("clear")
    assert not item.font().underline()
    assert item.data(Qt.ItemDataRole.UserRole + 20) is None

    window.close()
    app.processEvents()


def test_desktop_ctrl_b_i_u_formats_selected_cells(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    item = QTableWidgetItem("Định dạng")
    window.entry_grid.setItem(0, 0, item)
    window.entry_grid.setCurrentCell(0, 0)

    for key, attribute in ((Qt.Key.Key_B, "bold"), (Qt.Key.Key_I, "italic"), (Qt.Key.Key_U, "underline")):
        window.entry_grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.ControlModifier))
        assert getattr(item.font(), attribute)()

    window.close()
    app.processEvents()


def test_desktop_ctrl_5_toggles_strikethrough_without_changing_raw_value(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    item = QTableWidgetItem("1234.5")
    window.entry_grid.setItem(0, 0, item)
    window.entry_grid.apply_display_format(item, "#,##0.00")
    window.entry_grid.setCurrentCell(0, 0)

    window.entry_grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_5, Qt.KeyboardModifier.ControlModifier))
    assert item.font().strikeOut()
    assert window.entry_grid.value_for_item(item) == "1234.5"
    window.entry_grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_5, Qt.KeyboardModifier.ControlModifier))
    assert not item.font().strikeOut()

    window.close()
    app.processEvents()


def test_desktop_ctrl_backtick_toggles_formula_view_without_changing_formula():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 2)
    grid.setItem(0, 0, QTableWidgetItem("3"))
    grid.setItem(0, 1, QTableWidgetItem("=A1*2"))
    formula_item = grid.item(0, 1)
    assert formula_item.text() == "6"

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_QuoteLeft, Qt.KeyboardModifier.ControlModifier))
    assert formula_item.text() == "=A1*2"
    assert grid.formula_for_item(formula_item) == "=A1*2"
    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_QuoteLeft, Qt.KeyboardModifier.ControlModifier))
    assert formula_item.text() == "6"


def test_desktop_alt_equals_inserts_auto_sum_for_selected_column(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    for row, value in enumerate(("3", "4")):
        window.entry_grid.setItem(row, 3, QTableWidgetItem(value))
    window.entry_grid.setRangeSelected(QTableWidgetSelectionRange(0, 3, 1, 3), True)

    window.entry_grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Equal, Qt.KeyboardModifier.AltModifier))
    assert window.entry_grid.formula_for_item(window.entry_grid.item(2, 3)) == "=SUM(D1:D2)"

    window.close()
    app.processEvents()


def test_desktop_ctrl_x_copies_and_clears_only_editable_selected_cells():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 2)
    editable = QTableWidgetItem("copy me")
    locked = QTableWidgetItem("preserve me")
    locked.setFlags(locked.flags() & ~Qt.ItemFlag.ItemIsEditable)
    grid.setItem(0, 0, editable)
    grid.setItem(0, 1, locked)
    grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, 1), True)

    grid.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier))
    assert QApplication.clipboard().text() == "copy me\tpreserve me"
    assert editable.text() == ""
    assert locked.text() == "preserve me"


def test_desktop_ctrl_shift_v_pastes_formula_text_as_values():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, 2)
    QApplication.clipboard().setText("=A1\tplain")
    grid.setCurrentCell(0, 0)

    grid.keyPressEvent(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_V,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    ))
    assert grid.item(0, 0).text() == "=A1"
    assert grid.item(0, 0).data(grid.RAW_FORMULA_ROLE) is None
    assert grid.formula_for_item(grid.item(0, 0)) == "=A1"
    assert grid.item(0, 1).text() == "plain"


def test_desktop_entry_grid_filters_and_sorts_column_values(tmp_path):
    app = QApplication.instance() or QApplication([])
    clear_entry_draft(__import__("datetime").date.today())
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    for row, values in enumerate((("HMS", "20"), ("ABC", "10"), ("HMS", "30"))):
        window.entry_grid.setItem(row, 0, QTableWidgetItem(values[0]))
        window.entry_grid.setItem(row, 3, QTableWidgetItem(values[1]))
    window._column_filters[0] = {"HMS"}
    window.apply_column_filters()
    assert not window.entry_grid.isRowHidden(0)
    assert window.entry_grid.isRowHidden(1)
    assert not window.entry_grid.isRowHidden(2)

    dialog = SpreadsheetFilterDialog("Khách hàng", ["ABC", "HMS"], {"HMS"}, window)
    dialog.search.setText("HM")
    assert dialog.values.item(0).isHidden()
    assert not dialog.values.item(1).isHidden()
    window.sort_entry_grid(3, Qt.SortOrder.AscendingOrder)
    assert window.entry_grid.item(0, 3).text() == "10"

    dialog.close()
    window.close()
    clear_entry_draft(window.selected_delivery_date)
    app.processEvents()


def test_desktop_entry_grid_sorts_numeric_and_iso_date_values_without_losing_metadata(tmp_path):
    app = QApplication.instance() or QApplication([])
    clear_entry_draft(__import__("datetime").date.today())
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    quantity_column = ENTRY_HEADERS.index("Số lượng")
    date_column = ENTRY_HEADERS.index("Ghi chú")
    for row, (quantity, delivery_date, internal_id) in enumerate((
        ("10", "2026-10-01", "product-ten"), ("2", "2026-01-01", "product-two"),
        ("1,234.50", "2026-06-15", "product-large"),
    )):
        window.entry_grid.item(row, quantity_column).setText(quantity)
        date_item = window.entry_grid.item(row, date_column)
        date_item.setText(delivery_date)
        date_item.setData(Qt.ItemDataRole.UserRole + 30, internal_id)

    window.sort_entry_grid(quantity_column, Qt.SortOrder.AscendingOrder)
    assert [window.entry_grid.item(row, quantity_column).text() for row in range(3)] == ["2", "10", "1,234.50"]
    assert window.entry_grid.item(0, date_column).data(Qt.ItemDataRole.UserRole + 30) == "product-two"

    window.sort_entry_grid(date_column, Qt.SortOrder.DescendingOrder)
    assert [window.entry_grid.item(row, date_column).text() for row in range(3)] == ["2026-10-01", "2026-06-15", "2026-01-01"]
    window.close()
    clear_entry_draft(window.selected_delivery_date)
    app.processEvents()


def test_desktop_entry_grid_loads_products_saved_for_selected_list_date(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    selected_date = __import__("datetime").date(2026, 9, 26)
    clear_entry_draft(__import__("datetime").date.today())
    clear_entry_draft(selected_date)
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    window = ProductMasterWindow(service)
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    window.selected_delivery_date = selected_date
    window._update_entry_delivery_date_labels()
    for row, name in enumerate(("Chi tiết ngày 26 A", "Chi tiết ngày 26 B")):
        window.entry_grid.item(row, ENTRY_HEADERS.index("Khách hàng")).setText("HMS")
        window.entry_grid.item(row, ENTRY_HEADERS.index("Tên sản phẩm")).setText(name)
        window.entry_grid.item(row, ENTRY_HEADERS.index("Số lượng")).setText("1")
    for header, value in zip(("Kích thước X", "Kích thước Y", "Kích thước Z"), ("100", "50", "20")):
        window.entry_grid.item(0, ENTRY_HEADERS.index(header)).setText(value)
    window.save_entry_rows()

    assert service.list_products().total == 2
    assert [window.entry_grid.item(row, ENTRY_HEADERS.index("Tên sản phẩm")).text() for row in range(2)] == [
        "Chi tiết ngày 26 A", "Chi tiết ngày 26 B",
    ]
    assert [window.entry_grid.item(0, ENTRY_HEADERS.index(header)).text()
            for header in ("Kích thước X", "Kích thước Y", "Kích thước Z")] == ["100", "50", "20"]
    window.change_entry_delivery_date("day", 1)
    assert window.entry_grid.item(0, ENTRY_HEADERS.index("Tên sản phẩm")).text() == ""
    window.change_entry_delivery_date("day", -1)
    assert [window.entry_grid.item(row, ENTRY_HEADERS.index("Tên sản phẩm")).text() for row in range(2)] == [
        "Chi tiết ngày 26 A", "Chi tiết ngày 26 B",
    ]
    window.entry_grid.item(0, ENTRY_HEADERS.index("Số lượng")).setText("3")
    window.save_entry_rows()
    assert service.list_products().total == 2
    assert service.list_products(sort_by="product_code", descending=False).items[0].quantity == 3
    window.close()
    clear_entry_draft(selected_date)
    app.processEvents()


def test_desktop_entry_grid_keeps_incomplete_draft_when_changing_list_date(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite"))
    selected_date = __import__("datetime").date(2026, 9, 16)
    settings = QSettings("HMS QR", "Quan Ly QR")
    settings.remove(f"worksheet/drafts/{selected_date.isoformat()}")
    settings.sync()
    window = ProductMasterWindow(service)
    window.selected_delivery_date = selected_date
    window._update_entry_delivery_date_labels()
    window.entry_grid.item(0, ENTRY_HEADERS.index("Tên sản phẩm")).setText("Dữ liệu chưa đủ")
    window.change_entry_delivery_date("day", 1)
    assert window.entry_grid.item(0, ENTRY_HEADERS.index("Tên sản phẩm")).text() == ""
    window.change_entry_delivery_date("day", -1)
    assert window.entry_grid.item(0, ENTRY_HEADERS.index("Tên sản phẩm")).text() == "Dữ liệu chưa đủ"
    window.close()
    settings.remove(f"worksheet/drafts/{selected_date.isoformat()}")
    settings.sync()
    app.processEvents()


def test_desktop_entry_grid_wraps_text_without_expanding_columns(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    name_column = ENTRY_HEADERS.index("Tên sản phẩm")
    x_column = ENTRY_HEADERS.index("Kích thước X")
    initial_width = window.entry_grid.columnWidth(x_column)

    name = QTableWidgetItem("Tên sản phẩm có nội dung rất dài cần xuống dòng")
    size = QTableWidgetItem("12345678901234567890")
    window.entry_grid.setItem(0, name_column, name)
    window.entry_grid.setItem(0, x_column, size)

    assert name.textAlignment() == int(Qt.AlignmentFlag.AlignCenter)
    assert name.data(Qt.ItemDataRole.UserRole + 22) is True
    assert size.textAlignment() == int(Qt.AlignmentFlag.AlignCenter)
    assert size.data(Qt.ItemDataRole.UserRole + 22) is True
    assert window.entry_grid.columnWidth(x_column) == initial_width

    window.close()
    app.processEvents()


def test_desktop_double_click_product_image_opens_viewer(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = ProductMasterWindow(ProductService(SQLiteProductRepository(tmp_path / "desktop.sqlite")))
    image = QImage(12, 12, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.red)
    output = QByteArray()
    buffer = QBuffer(output)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    item = QTableWidgetItem()
    item.setData(Qt.ItemDataRole.UserRole, bytes(output))
    image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
    window.entry_grid.setItem(0, image_column, item)
    opened = []
    monkeypatch.setattr(ProductImageViewer, "exec", lambda self: opened.append(self.windowTitle()))

    window.open_product_image(item)
    assert opened == ["Ảnh sản phẩm"]
    window.open_product_image(QTableWidgetItem("Không phải ảnh"))
    assert opened == ["Ảnh sản phẩm"]

    window.close()
    app.processEvents()


def test_desktop_paste_images_distributes_them_to_consecutive_rows():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    images = []
    for color in (Qt.GlobalColor.red, Qt.GlobalColor.blue, Qt.GlobalColor.green):
        image = QImage(12, 12, QImage.Format.Format_RGB32)
        image.fill(color)
        images.append(image)

    grid.paste_images(images, 0)
    image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
    assert grid.rowCount() == 3
    assert all(grid.item(row, image_column).data(Qt.ItemDataRole.UserRole) for row in range(3))
    assert grid.rowHeight(2) == 62


def test_desktop_pasted_image_png_preserves_original_pixel_dimensions():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    image = QImage(2400, 1600, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.blue)

    grid.paste_images([image], 0)

    stored = QImage()
    stored.loadFromData(grid.item(0, ENTRY_HEADERS.index("Ảnh sản phẩm")).data(Qt.ItemDataRole.UserRole), "PNG")
    assert stored.size() == image.size()


def test_desktop_excel_image_fallback_replaces_single_clipboard_image(monkeypatch):
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    image = QImage(12, 12, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.red)
    fallback = []
    for color in (Qt.GlobalColor.blue, Qt.GlobalColor.green):
        item = QImage(12, 12, QImage.Format.Format_RGB32)
        item.fill(color)
        fallback.append(item)
    monkeypatch.setattr(grid, "_clipboard_images", lambda _mime: [image])
    monkeypatch.setattr(grid, "_excel_selected_images", lambda: fallback)
    QApplication.clipboard().setImage(image)
    grid.setCurrentCell(0, 0)
    grid.paste_from_clipboard()

    image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
    assert grid.rowCount() == 2
    assert all(grid.item(row, image_column).data(Qt.ItemDataRole.UserRole) for row in range(2))


def test_desktop_delete_clears_selected_values_and_product_image():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
    text_item = QTableWidgetItem("Xóa tôi")
    image_item = QTableWidgetItem()
    image_item.setData(Qt.ItemDataRole.UserRole, b"image-data")
    generated_item = QTableWidgetItem("QR khóa")
    generated_item.setFlags(generated_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    grid.setItem(0, 0, text_item)
    grid.setItem(0, image_column, image_item)
    grid.setItem(0, ENTRY_HEADERS.index("Mã QR"), generated_item)
    grid.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, image_column), True)
    grid.clear_selected_cells()

    assert text_item.text() == ""
    assert image_item.data(Qt.ItemDataRole.UserRole) is None
    generated_item.setText("QR khóa")
    grid.clearSelection()
    qr_column = ENTRY_HEADERS.index("Mã QR")
    grid.setRangeSelected(QTableWidgetSelectionRange(0, qr_column, 0, qr_column), True)
    grid.clear_selected_cells()
    assert generated_item.text() == "QR khóa"


def test_desktop_undo_redo_restores_text_and_image_cells():
    app = QApplication.instance() or QApplication([])
    grid = SpreadsheetEntryGrid(1, len(ENTRY_HEADERS))
    image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
    grid.setItem(0, 0, QTableWidgetItem("Ban đầu"))
    grid.reset_history()

    grid.item(0, 0).setText("Đã sửa")
    grid.undo()
    assert grid.item(0, 0).text() == "Ban đầu"
    grid.redo()
    assert grid.item(0, 0).text() == "Đã sửa"

    image = QImage(12, 12, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.red)
    grid.paste_images([image], 0)
    assert grid.item(0, image_column).data(Qt.ItemDataRole.UserRole)
    grid.undo()
    assert grid.item(0, image_column) is None
    grid.redo()
    assert grid.item(0, image_column).data(Qt.ItemDataRole.UserRole)
