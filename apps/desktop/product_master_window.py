"""First usable Vietnamese Product Master desktop window."""

from __future__ import annotations

import mimetypes
import base64
import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta
from calendar import monthrange
from io import BytesIO
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QAbstractTableModel, QByteArray, QBuffer, QEvent, QIODevice, QMimeData, QModelIndex, QPoint, QRect, QSettings, QStringListModel, Qt, Signal, QTimer
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QFontMetrics, QImage, QKeySequence, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QColorDialog, QFileDialog, QLineEdit, QMainWindow, QMessageBox, QPushButton, QTableView,
    QAbstractItemDelegate, QCompleter, QStyledItemDelegate, QTableWidget, QTableWidgetItem, QTableWidgetSelectionRange, QVBoxLayout,
    QCheckBox, QDialog, QDialogButtonBox, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QInputDialog, QListWidget, QListWidgetItem, QMenu, QScrollArea, QScrollBar, QSlider, QSpinBox, QStyle, QStyleOptionViewItem, QToolTip, QWidget, QTabWidget,
)

from packages.application.product_service import ProductService
from packages.application.tracking_api_client import TrackingApiClient
from packages.application.stage2_api_client import Stage2ApiClient
from .tracking_window import TrackingWindow
from .stage2_window import Stage2Window
from .version import APP_VERSION
from packages.domain.product import Product, ProductStatus, ProductValidationError, format_quantity
from packages.domain.repository import ProductPage
from apps.design_tokens import PY_SIDE_THEME
from apps.desktop.file_panels import AdminStoragePanel, ProductFilesPanel
from packages.excel.desktop_formula_engine import FormulaEngine, FormulaError
import qrcode


STATUS_LABELS = {
    ProductStatus.NEW: "Mới", ProductStatus.WAITING: "Chờ xử lý", ProductStatus.IN_PROGRESS: "Đang thực hiện",
    ProductStatus.WAITING_QC: "Chờ QC", ProductStatus.QC_PASS: "QC đạt", ProductStatus.QC_NG: "QC không đạt",
    ProductStatus.REWORK: "Làm lại", ProductStatus.PACKED: "Đã đóng gói", ProductStatus.DELIVERED: "Đã giao",
    ProductStatus.HOLD: "Tạm giữ", ProductStatus.CANCELLED: "Đã hủy",
}

ENTRY_HEADERS = [
    "Khách hàng", "Ảnh sản phẩm", "Tên sản phẩm", "Số lượng", "Đơn vị",
    "Vật liệu", "Người đặt", "Xử lý bề mặt", "Đặt ngoài", "Kích thước X", "Kích thước Y",
    "Kích thước Z", "Ghi chú", "Mã QR", "Mã sản phẩm", "Trạng thái S/P",
]

ENTRY_HEADER_LABELS = {
    "Khách hàng": "Khách Hàng", "Ảnh sản phẩm": "Ảnh Sản Phẩm", "Tên sản phẩm": "Tên Sản Phẩm",
    "Số lượng": "Số Lượng", "Đơn vị": "Đơn Vị", "Vật liệu": "Vật Liệu", "Người đặt": "Người Đặt",
    "Xử lý bề mặt": "Xử Lý Bề Mặt", "Đặt ngoài": "Đặt Ngoài", "Kích thước X": "X",
    "Kích thước Y": "Y", "Kích thước Z": "Z", "Ghi chú": "Ghi Chú", "Mã QR": "Mã QR",
    "Mã sản phẩm": "Mã Sản Phẩm", "Trạng thái S/P": "Trạng Thái S/P",
}

DEFAULT_CELL_SIZE_SETTINGS = {
    "column_chars": {
        "Khách hàng": 15,
        "Ảnh sản phẩm": 15,
        "Tên sản phẩm": 45,
        "Số lượng": 10,
        "Đơn vị": 8,
        "Vật liệu": 15,
        "Người đặt": 15,
        "Xử lý bề mặt": 20,
        "Đặt ngoài": 15,
        "Kích thước X": 8,
        "Kích thước Y": 8,
        "Kích thước Z": 8,
        "Ghi chú": 30,
        "Mã QR": 15,
        "Mã sản phẩm": 20,
        "Trạng thái S/P": 20,
    },
    "row_height": 65,
}

STATUS_COLORS = {
    "Mới": "#dceeff", "Chờ xử lý": "#fff1bf", "Đang thực hiện": "#cfe9ff", "Chờ QC": "#eadcff",
    "QC đạt": "#c7f2d3", "QC không đạt": "#ffd0d0", "Làm lại": "#ffdca8", "Đã đóng gói": "#d9e5f5",
    "Đã giao": "#b8e8c7", "Tạm giữ": "#ffe0a3", "Đã hủy": "#e4e4e4",
}
VALIDATION_WARNING_COLOR = "#fff1bf"


def product_qr_value(product_code: str, company: str) -> str:
    """Stable QR payload for a product and its customer, independent of an order."""
    code = product_code.strip().upper()
    customer = " ".join(unicodedata.normalize("NFKC", company).split())
    return f"SP:{code}|KH:{customer}" if code and customer else ""


def qr_png(payload: str) -> bytes:
    output = BytesIO()
    # A one-module quiet zone is sufficient inside the bordered product label.
    code = qrcode.QRCode(border=1, box_size=24, error_correction=qrcode.constants.ERROR_CORRECT_L)
    code.add_data(payload)
    code.make(fit=True)
    code.make_image(fill_color="black", back_color="white").save(output, format="PNG")
    return output.getvalue()


def product_qr_label_png(payload: str, product_code: str, part_name: str, dimensions: str, delivery_date: date) -> bytes:
    """Render a 50 x 30 mm product label at 1500 DPI with balanced QR and details panels."""
    logical_width, logical_height = 591, 354
    width, height = 2953, 1772  # 50 x 30 mm at 1500 DPI.
    render_scale = width / logical_width
    left_width = round(logical_width * 0.60)
    label = QImage(width, height, QImage.Format.Format_ARGB32)
    label.fill(Qt.GlobalColor.white)
    dots_per_meter = round(1500 / 0.0254)
    label.setDotsPerMeterX(dots_per_meter)
    label.setDotsPerMeterY(dots_per_meter)
    qr = QImage()
    qr.loadFromData(qr_png(payload), "PNG")
    painter = QPainter(label)
    try:
        painter.scale(render_scale, height / logical_height)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(QPen(QColor("#111111"), 2))
        painter.drawRect(1, 1, logical_width - 2, logical_height - 2)
        qr_size = min(left_width - 8, 270)
        qr_target = qr.scaled(qr_size, qr_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        painter.drawImage((left_width - qr_target.width()) // 2, 3, qr_target)

        painter.setPen(QColor("#111111"))
        font = QFont()
        font.setBold(True)
        # The painter scales all layout coordinates to 1500 DPI, including this logical pixel size.
        font.setPixelSize(16)
        painter.setFont(font)
        painter.drawText(
            QRect(12, 276, logical_width - 24, logical_height - 288),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            part_name or "-",
        )

        text_rect = QRect(left_width + 14, 20, width - left_width - 28, 246)
        painter.setPen(QColor("#111111"))
        font.setPixelSize(16)
        font.setBold(True)
        painter.setFont(font)
        row_height = 78
        painter.drawText(QRect(text_rect.x(), text_rect.y(), text_rect.width(), row_height), Qt.TextFlag.TextWordWrap, f"MÃ SP:\n{product_code}")
        painter.drawText(QRect(text_rect.x(), text_rect.y() + row_height + 4, text_rect.width(), row_height), Qt.TextFlag.TextWordWrap, f"KÍCH THƯỚC:\n{dimensions or '-'}")
        painter.drawText(
            QRect(text_rect.x(), text_rect.y() + (row_height + 4) * 2, text_rect.width(), row_height),
            Qt.TextFlag.TextWordWrap,
            f"NGÀY GIAO HÀNG:\n{delivery_date:%d/%m/%Y}",
        )
    finally:
        painter.end()
    output = QByteArray()
    buffer = QBuffer(output)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    label.save(buffer, "PNG", 100)
    return bytes(output)


def product_code_value(company: str, part_name: str, dimensions: tuple[str, str, str], delivery: str, row: int) -> str:
    """Build the worksheet business code from customer, product, date, and row."""
    del dimensions

    def initials(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).replace("Đ", "D").replace("đ", "d")
        words = re.findall(r"[A-Z0-9]+", normalized.encode("ascii", "ignore").decode("ascii").upper())
        return "".join(word[0] for word in words) or "NO"

    try:
        delivery_date = date.fromisoformat(delivery)
        date_part = delivery_date.strftime("%y%m%d")
    except (TypeError, ValueError):
        date_part = "NODATE"
    return f"{initials(company)}-{initials(part_name)}-{date_part}-R{row + 1:03d}"


def format_dimensions(values: tuple[str, ...] | list[str]) -> str:
    """Join dimensions while attaching a symbol-only cell to its numeric value."""
    parts = [str(value).strip() for value in values if str(value).strip()]
    rendered: list[str] = []
    for index, value in enumerate(parts):
        # A standalone symbol such as Ø belongs to the following measurement:
        # Ø | 14.5 | 2.8 becomes Ø14.5 x 2.8.
        if not any(character.isdigit() for character in value) and index + 1 < len(parts):
            rendered.append(f"{value}{parts[index + 1]}")
            parts[index + 1] = ""
        elif value:
            rendered.append(value)
    return " x ".join(rendered)

FORMULA_FUNCTIONS = [
    "ABS", "AND", "AVERAGE", "CHOOSE", "CONCATENATE", "COUNT", "COUNTA", "COUNTIF", "COUNTIFS",
    "DATE", "DAY", "DAYS", "EXACT", "FIND", "HLOOKUP", "IF", "IFERROR", "IFS", "INDEX", "INT",
    "ISBLANK", "ISNUMBER", "ISTEXT", "LEFT", "LEN", "LOWER", "MATCH", "MAX", "MID", "MIN", "MOD",
    "MONTH", "NOT", "OR", "POWER", "RIGHT", "ROUND", "ROUNDDOWN", "ROUNDUP", "SQRT", "SUBSTITUTE",
    "SUM", "SUMIF", "SUMIFS", "SWITCH", "TEXTJOIN", "TODAY", "TRIM", "UPPER", "VLOOKUP", "XLOOKUP", "YEAR",
]

FORMULA_HINTS = {
    "SUM": "SUM(number1, [number2], ...): Tính tổng.",
    "AVERAGE": "AVERAGE(number1, ...): Tính trung bình.",
    "IF": "IF(condition, value_if_true, value_if_false): Điều kiện.",
    "IFERROR": "IFERROR(value, value_if_error): Thay giá trị lỗi.",
    "XLOOKUP": "XLOOKUP(value, lookup_array, return_array, [if_not_found]): Tra cứu.",
    "VLOOKUP": "VLOOKUP(value, table, column, [exact]): Tra cứu theo cột.",
    "SUMIFS": "SUMIFS(sum_range, criteria_range1, criteria1, ...): Tổng nhiều điều kiện.",
    "COUNTIFS": "COUNTIFS(criteria_range1, criteria1, ...): Đếm nhiều điều kiện.",
    "TEXTJOIN": "TEXTJOIN(delimiter, ignore_empty, text1, ...): Ghép văn bản.",
    "DATE": "DATE(year, month, day): Tạo ngày YYYY-MM-DD.",
}


def complete_formula_parentheses(text: str) -> str:
    """Close only unmatched function parentheses outside Excel text literals."""
    if not text.startswith("="):
        return text
    depth = 0
    in_text = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            if in_text and index + 1 < len(text) and text[index + 1] == '"':
                index += 1
            else:
                in_text = not in_text
        elif not in_text:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
        index += 1
    return f"{text}{')' * depth}" if depth > 0 else text


def cycle_formula_reference_lock(editor: QLineEdit) -> bool:
    """Cycle the A1 reference at the cursor through Excel's four lock forms."""
    if not editor.text().startswith("="):
        return False
    cursor = editor.cursorPosition()
    for match in re.finditer(r"\$?[A-Z]{1,3}\$?\d+", editor.text(), re.IGNORECASE):
        if match.start() <= cursor <= match.end():
            reference = match.group()
            column = re.sub(r"[\d$]", "", reference)
            row = re.sub(r"[A-Z$]", "", reference, flags=re.IGNORECASE)
            forms = (f"{column}{row}", f"${column}${row}", f"{column}${row}", f"${column}{row}")
            try:
                replacement = forms[(forms.index(reference.upper()) + 1) % len(forms)]
            except ValueError:
                replacement = forms[0]
            editor.setText(f"{editor.text()[:match.start()]}{replacement}{editor.text()[match.end():]}")
            editor.setCursorPosition(match.start() + len(replacement))
            return True
    return False


def attach_formula_completer(editor: QLineEdit) -> None:
    """Show Excel-style function suggestions only while a formula is being entered."""
    model = QStringListModel(FORMULA_FUNCTIONS, editor)
    completer = QCompleter(model, editor)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setCompletionRole(Qt.ItemDataRole.DisplayRole)
    editor.setCompleter(completer)

    hint = QLabel(editor)
    hint.setStyleSheet("color: #505a66; font-size: 11px; padding: 2px 5px;")
    hint.hide()

    def suggest(text: str) -> None:
        if not text.startswith("="):
            completer.popup().hide()
            hint.hide()
            return
        token = text[1:].rsplit("(", 1)[-1].rsplit(",", 1)[-1].strip()
        if token and not token.replace("_", "").isalpha():
            completer.popup().hide()
            hint.hide()
            return
        completer.setCompletionPrefix(token)
        completer.complete()
        matching = next((name for name in FORMULA_FUNCTIONS if name.startswith(token.upper())), "")
        if matching and matching in FORMULA_HINTS:
            hint.setText(FORMULA_HINTS[matching])
            hint.adjustSize()
            hint.move(0, editor.height())
            hint.show()
        else:
            hint.hide()

    def insert_function(name: str) -> None:
        text = editor.text()
        token_start = max(text.rfind("("), text.rfind(","), 0) + 1
        prefix = text[:token_start]
        editor.setText(f"{prefix}{name}(")
        editor.setCursorPosition(len(editor.text()))
        hint.hide()

    editor.textEdited.connect(suggest)
    completer.activated[str].connect(insert_function)
    editor.returnPressed.connect(lambda: editor.setText(complete_formula_parentheses(editor.text())))


class FormulaItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        attach_formula_completer(editor)
        self.parent().installEventFilter(editor)
        return editor

    def setEditorData(self, editor, index) -> None:
        grid = self.parent()
        item = grid.item(index.row(), index.column())
        editor.setText(grid.value_for_item(item))

    def paint(self, painter, option, index) -> None:
        image_columns = {ENTRY_HEADERS.index("Ảnh sản phẩm"), ENTRY_HEADERS.index("Mã QR")}
        if index.column() in image_columns:
            png = index.data(Qt.ItemDataRole.UserRole if index.column() == ENTRY_HEADERS.index("Ảnh sản phẩm")
                             else Qt.ItemDataRole.UserRole + 21)
            if png:
                image = QPixmap()
                image.loadFromData(png, "PNG")
                painter.save()
                painter.fillRect(option.rect, option.palette.base())
                target = image.scaled(max(1, option.rect.width() - 6), max(1, option.rect.height() - 6), Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                x = option.rect.x() + (option.rect.width() - target.width()) // 2
                y = option.rect.y() + (option.rect.height() - target.height()) // 2
                painter.drawPixmap(x, y, target)
                painter.restore()
                return
        self.initStyleOption(option, index)
        text = option.text
        option.text = ""
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget)
        painter.save()
        color_group = QPalette.ColorGroup.Active
        color_role = QPalette.ColorRole.HighlightedText if option.state & QStyle.StateFlag.State_Selected else QPalette.ColorRole.Text
        painter.setPen(option.palette.color(color_group, color_role))
        text_rect = option.rect.adjusted(6, 3, -6, -3)
        if index.column() == ENTRY_HEADERS.index("Mã QR") and text:
            # Lightweight visual cue; print-resolution QR data is created only on demand.
            size = min(28, max(14, option.rect.height() - 10))
            left = option.rect.left() + 6
            top = option.rect.center().y() - size // 2
            painter.fillRect(left, top, size, size, QColor("white"))
            painter.setPen(QPen(QColor("#17212b"), 1))
            painter.drawRect(left, top, size - 1, size - 1)
            module = max(1, size // 9)
            for x, y in ((0, 0), (6, 0), (0, 6)):
                painter.fillRect(left + x * module, top + y * module, 3 * module, 3 * module, QColor("#17212b"))
                painter.fillRect(left + (x + 1) * module, top + (y + 1) * module, module, module, QColor("white"))
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            for bit in range(20):
                x, y = 3 + bit % 6, 3 + bit // 6
                if x < 9 and y < 9 and digest[bit] & 1:
                    painter.fillRect(left + x * module, top + y * module, module, module, QColor("#17212b"))
            text_rect.adjust(size + 8, 0, 0, 0)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere,
            text,
        )
        painter.restore()

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignCenter
        if index.data(Qt.ItemDataRole.UserRole + 22):
            option.features |= QStyleOptionViewItem.ViewItemFeature.WrapText
        else:
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.WrapText
        if index.data(Qt.ItemDataRole.UserRole + 20):
            painter.save()
            painter.setPen(QPen(QColor("#4f4f4f"), 1))
            painter.drawRect(option.rect.adjusted(0, 0, -1, -1))
            painter.restore()


class SpreadsheetHeader(QHeaderView):
    """Two-tier worksheet header with one grouped X/Y/Z dimension label."""

    DIMENSION_COLUMNS = (9, 10, 11)
    filterRequested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setMinimumHeight(48)
        font = self.font()
        font.setBold(True)
        self.setFont(font)

    def filter_icon_rect(self, column: int) -> QRect:
        """Return the exact clickable area occupied by the filter glyph."""
        return QRect(
            self.sectionViewportPosition(column) + self.sectionSize(column) - 16,
            self.height() // 2,
            14,
            self.height() // 2,
        )

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        visual_columns = [self.visualIndex(column) for column in self.DIMENSION_COLUMNS]
        if sorted(visual_columns) != list(range(min(visual_columns), max(visual_columns) + 1)):
            return
        positions = [self.sectionViewportPosition(column) for column in self.DIMENSION_COLUMNS]
        widths = [self.sectionSize(column) for column in self.DIMENSION_COLUMNS]
        left, right = min(positions), max(position + width for position, width in zip(positions, widths))
        height = self.height() // 2
        painter = QPainter(self.viewport())
        painter.fillRect(left, 0, right - left, height, self.palette().button())
        painter.setPen(self.palette().mid().color())
        painter.drawRect(left, 0, right - left - 1, height - 1)
        painter.setPen(self.palette().buttonText().color())
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(left, 0, right - left, height, Qt.AlignmentFlag.AlignCenter, "Kích Thước")
        for visual in range(self.count()):
            column = self.logicalIndex(visual)
            painter.drawText(self.filter_icon_rect(column), Qt.AlignmentFlag.AlignCenter, "▼")
        painter.end()

    def mouseReleaseEvent(self, event) -> None:
        column = self.logicalIndexAt(event.position().toPoint())
        if column >= 0 and self.filter_icon_rect(column).contains(event.position().toPoint()):
            self.filterRequested.emit(column)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SpreadsheetFilterDialog(QDialog):
    def __init__(self, column_name: str, values: list[str], selected: set[str] | None, parent=None) -> None:
        super().__init__(parent)
        self._cleared = False
        self.sort_order: Qt.SortOrder | None = None
        self.setWindowTitle(f"Lọc: {column_name}")
        self.setMinimumWidth(280)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm kiếm")
        self.select_all = QCheckBox("(Chọn tất cả)")
        self.values = QListWidget()
        for value in values:
            item = QListWidgetItem(value or "(Trống)")
            item.setData(Qt.ItemDataRole.UserRole, value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if selected is None or value in selected else Qt.CheckState.Unchecked)
            self.values.addItem(item)
        self.select_all.setChecked(all(self.values.item(index).checkState() == Qt.CheckState.Checked
                                        for index in range(self.values.count())))
        self.sort_ascending = QPushButton("A↓  Sắp xếp từ A đến Z")
        self.sort_descending = QPushButton("Z↓  Sắp xếp từ Z đến A")
        clear = QPushButton("Xóa bộ lọc")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout = QVBoxLayout(self)
        layout.addWidget(self.sort_ascending)
        layout.addWidget(self.sort_descending)
        layout.addWidget(clear)
        layout.addWidget(self.search)
        layout.addWidget(self.select_all)
        layout.addWidget(self.values)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self._search)
        self.select_all.toggled.connect(self._toggle_all)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        clear.clicked.connect(self._clear)
        self.sort_ascending.clicked.connect(lambda: self._sort(Qt.SortOrder.AscendingOrder))
        self.sort_descending.clicked.connect(lambda: self._sort(Qt.SortOrder.DescendingOrder))

    def _search(self, text: str) -> None:
        for index in range(self.values.count()):
            item = self.values.item(index)
            item.setHidden(text.casefold() not in item.text().casefold())

    def _toggle_all(self, checked: bool) -> None:
        for index in range(self.values.count()):
            item = self.values.item(index)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _clear(self) -> None:
        self._cleared = True
        self.accept()

    def _sort(self, order: Qt.SortOrder) -> None:
        self.sort_order = order
        self.accept()

    def selected_values(self) -> set[str]:
        return {self.values.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.values.count())
                if self.values.item(index).checkState() == Qt.CheckState.Checked}


class SpreadsheetFindDialog(QDialog):
    def __init__(self, grid: "SpreadsheetEntryGrid", replace: bool = False) -> None:
        super().__init__(grid)
        self.grid = grid
        self.setWindowTitle("Tìm và thay thế" if replace else "Tìm")
        self.find_text = QLineEdit()
        self.find_text.setPlaceholderText("Nội dung cần tìm")
        self.replace_text = QLineEdit()
        self.replace_text.setPlaceholderText("Nội dung thay thế")
        self.match_case = QCheckBox("Phân biệt hoa/thường")
        find_next = QPushButton("Tìm tiếp")
        replace_one = QPushButton("Thay thế")
        replace_all = QPushButton("Thay tất cả")
        close = QPushButton("Đóng")
        layout = QFormLayout(self)
        layout.addRow("Tìm:", self.find_text)
        if replace:
            layout.addRow("Thay bằng:", self.replace_text)
        layout.addRow("", self.match_case)
        buttons = QHBoxLayout()
        buttons.addWidget(find_next)
        if replace:
            buttons.addWidget(replace_one)
            buttons.addWidget(replace_all)
        buttons.addWidget(close)
        layout.addRow(buttons)
        find_next.clicked.connect(self._find_next)
        replace_one.clicked.connect(self._replace_one)
        replace_all.clicked.connect(self._replace_all)
        close.clicked.connect(self.reject)
        self.find_text.returnPressed.connect(self._find_next)

    def _find_next(self) -> None:
        self.grid.find_next(self.find_text.text(), self.match_case.isChecked())

    def _replace_one(self) -> None:
        if self.grid.replace_current(self.find_text.text(), self.replace_text.text(), self.match_case.isChecked()):
            self._find_next()

    def _replace_all(self) -> None:
        self.grid.replace_all(self.find_text.text(), self.replace_text.text(), self.match_case.isChecked())


class SpreadsheetSizeDialog(QDialog):
    """Default worksheet geometry expressed as character counts per column."""

    settingsApplied = Signal(dict)

    def __init__(self, defaults: dict[str, object], factory_defaults: dict[str, object], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt kích thước ô")
        self.setMinimumWidth(420)
        self._factory_defaults = factory_defaults
        self.column_characters: dict[str, QSpinBox] = {}
        self.row_height = QSpinBox()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Độ rộng mặc định từng cột (số ký tự):"))
        fields = QWidget()
        field_layout = QFormLayout(fields)
        for header in ENTRY_HEADERS:
            control = QSpinBox()
            control.setRange(3, 60)
            control.setValue(defaults["column_chars"].get(header, 12))
            self.column_characters[header] = control
            field_layout.addRow(header, control)
        self.row_height.setRange(22, 200)
        self.row_height.setValue(defaults["row_height"])
        field_layout.addRow("Chiều cao dòng (px)", self.row_height)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(fields)
        layout.addWidget(scroll, 1)
        layout.addWidget(QLabel("Chỉ đặt kích thước mặc định. Bạn vẫn có thể kéo biên cột và hàng trực tiếp."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        restore_defaults = buttons.addButton("Mặc định", QDialogButtonBox.ButtonRole.ResetRole)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        restore_defaults.clicked.connect(self._restore_defaults)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply(self) -> None:
        self.settingsApplied.emit(self.values())

    def _restore_defaults(self) -> None:
        for header, control in self.column_characters.items():
            control.setValue(self._factory_defaults["column_chars"][header])
        self.row_height.setValue(self._factory_defaults["row_height"])

    def values(self) -> dict[str, object]:
        return {
            "column_chars": {header: control.value() for header, control in self.column_characters.items()},
            "row_height": self.row_height.value(),
        }


class SpreadsheetCellFormatDialog(QDialog):
    """Compact format dialog for the worksheet's supported per-cell styles."""

    DISPLAY_FORMATS = ("General", "0", "0.00", "#,##0", "#,##0.00", "dd/MM/yyyy", "dd-MM-yyyy")

    def __init__(self, item: QTableWidgetItem | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Định dạng ô")
        self.display_format = QComboBox()
        self.display_format.addItems(self.DISPLAY_FORMATS)
        self.bold = QCheckBox("In đậm")
        self.italic = QCheckBox("In nghiêng")
        self.underline = QCheckBox("Gạch chân")
        self.border = QCheckBox("Kẻ viền")
        if item is not None:
            self.display_format.setCurrentText(item.data(SpreadsheetEntryGrid.DISPLAY_FORMAT_ROLE) or "General")
            self.bold.setChecked(item.font().bold())
            self.italic.setChecked(item.font().italic())
            self.underline.setChecked(item.font().underline())
            self.border.setChecked(bool(item.data(Qt.ItemDataRole.UserRole + 20)))
        layout = QFormLayout(self)
        layout.addRow("Hiển thị:", self.display_format)
        layout.addRow("", self.bold)
        layout.addRow("", self.italic)
        layout.addRow("", self.underline)
        layout.addRow("", self.border)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict[str, object]:
        return {
            "display_format": self.display_format.currentText(),
            "bold": self.bold.isChecked(),
            "italic": self.italic.isChecked(),
            "underline": self.underline.isChecked(),
            "border": self.border.isChecked(),
        }


class ProductImageViewer(QDialog):
    def __init__(self, png: bytes, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ảnh sản phẩm")
        self.setMinimumSize(480, 360)
        image = QPixmap()
        image.loadFromData(png, "PNG")
        self.scene = QGraphicsScene(self)
        self.image = QGraphicsPixmapItem(image)
        self.scene.addItem(self.image)
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.wheelEvent = self._zoom_image
        QTimer.singleShot(0, self.reset_zoom)
        reset = QPushButton("Khôi phục kích thước")
        reset.clicked.connect(self.reset_zoom)
        close = QPushButton("Đóng")
        close.clicked.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(self.view, 1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(reset)
        actions.addWidget(close)
        actions.addStretch(1)
        layout.addLayout(actions)

    def _zoom_image(self, event) -> None:
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.view.scale(factor, factor)

    def reset_zoom(self) -> None:
        self.view.resetTransform()
        image_size = self.image.boundingRect().size()
        viewport = self.view.viewport().size()
        if image_size.isEmpty() or viewport.isEmpty():
            return
        # Never enlarge a small Excel image: upscaling only makes its original
        # pixels look soft. Large source images still scale down to fit.
        scale = min(1.0, viewport.width() / image_size.width(), viewport.height() / image_size.height())
        if scale < 1.0:
            self.view.scale(scale, scale)
        self.view.centerOn(self.image)


class SpreadsheetEntryGrid(QTableWidget):
    """Editable grid with Excel-compatible tab-separated copy and paste."""

    RAW_FORMULA_ROLE = Qt.ItemDataRole.UserRole + 1
    LITERAL_FORMULA_ROLE = Qt.ItemDataRole.UserRole + 2
    RAW_VALUE_ROLE = Qt.ItemDataRole.UserRole + 3
    DISPLAY_FORMAT_ROLE = Qt.ItemDataRole.UserRole + 4
    historyRestored = Signal()
    zoomRequested = Signal(int)
    columnCharacterWidthChanged = Signal(int, int)
    formulaReferenceSelected = Signal(int, int, int, int)
    formatRequested = Signal(str)
    autoSumRequested = Signal()
    cellFormatRequested = Signal()
    _A1_REFERENCE = re.compile(r"(?<![A-Z0-9_])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Z0-9_])", re.IGNORECASE)

    @staticmethod
    def _style_item(item: QTableWidgetItem, column: int) -> None:
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole + 22, True)
        if (ENTRY_HEADERS[column] in {"Mã QR", "Mã sản phẩm"}
                and item.flags() & Qt.ItemFlag.ItemIsEditable):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def set_column_character_limits(self, limits: dict[str, int]) -> None:
        self._column_character_limits = limits
        for column in range(self.columnCount()):
            self.fit_column_to_contents(column)

    def fit_all_columns_to_contents(self) -> None:
        for column in range(self.columnCount()):
            self.fit_column_to_contents(column)

    def fit_column_to_contents(self, column: int) -> None:
        """Apply the configured fixed width; long values wrap inside the cell."""
        if column >= len(ENTRY_HEADERS):
            return
        header = ENTRY_HEADERS[column]
        width = QFontMetrics(self.font()).horizontalAdvance("0" * self._column_character_limits.get(header, 12)) + 24
        self._auto_resizing_column = column
        try:
            self.setColumnWidth(column, max(40, width))
        finally:
            self._auto_resizing_column = None

    def _mark_column_resized(self, column: int, _old_width: int, _new_width: int) -> None:
        if self._applying_zoom or self._auto_resizing_column == column or column >= len(ENTRY_HEADERS):
            return
        character_width = max(1, QFontMetrics(self.font()).horizontalAdvance("0"))
        characters = max(1, round((_new_width - 24) / character_width))
        self._column_character_limits[ENTRY_HEADERS[column]] = characters
        self.columnCharacterWidthChanged.emit(column, characters)
        QToolTip.showText(QCursor.pos(), f"{characters} ký tự  •  {_new_width} px", self.horizontalHeader())
        self.fit_all_row_heights()

    def fit_all_row_heights(self) -> None:
        for row in range(self.rowCount()):
            self.fit_row_height(row)

    def fit_row_height(self, row: int) -> None:
        """Expand a row to show every wrapped cell, including unbroken text."""
        metrics = QFontMetrics(self.font())
        height = self._minimum_row_height
        wrap_flags = Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere
        for column in range(self.columnCount()):
            item = self.item(row, column)
            if not item or not item.text():
                continue
            available_width = max(1, self.columnWidth(column) - 12)
            text_height = metrics.boundingRect(QRect(0, 0, available_width, 10000), wrap_flags, item.text()).height() + 10
            height = max(height, text_height)
        image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
        qr_column = ENTRY_HEADERS.index("Mã QR")
        if any(self.item(row, column) and self.item(row, column).data(Qt.ItemDataRole.UserRole if column == image_column else Qt.ItemDataRole.UserRole + 21)
               for column in (image_column, qr_column)):
            height = max(height, 62)
        self.setRowHeight(row, height)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rendering_formulas = False
        self._showing_formulas = False
        self._updating_generated_codes = False
        self._restoring_history = False
        self._history_transaction = None
        self._undo_stack = []
        self._redo_stack = []
        self._last_snapshot = self._snapshot()
        self._column_character_limits = {header: 12 for header in ENTRY_HEADERS}
        self._preview_product_codes: dict[int, str] = {}
        self.delivery_date_provider = lambda: date.today()
        self._minimum_row_height = 24
        self._auto_resizing_column: int | None = None
        self._applying_zoom = False
        self._fill_drag_origin: tuple[int, int, int, int] | None = None
        self._fill_drag_target: tuple[int, int] | None = None
        self._fill_drag_copy_only = False
        self._formula_reference_drag_origin: tuple[int, int] | None = None
        self._keyboard_selection_anchor: tuple[int, int] | None = None
        self._extending_keyboard_selection = False
        self.formula_reference_mode = False
        self._find_cursor = -1
        self._find_needle = ""
        self._find_match_case = False
        self.today_provider = date.today
        self.current_time_provider = lambda: datetime.now().strftime("%H:%M")
        self.itemChanged.connect(self._on_item_changed)
        self.itemChanged.connect(self._update_generated_codes)
        self.itemChanged.connect(self._record_item_change)
        self.currentCellChanged.connect(self._reset_keyboard_selection_anchor)
        self.horizontalHeader().sectionResized.connect(self._mark_column_resized)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        source = self._fill_drag_origin or self._selection_bounds()
        if source is None:
            return
        top, left, bottom, right = source
        bottom_right = self.visualItemRect(self.item(bottom, right)) if self.item(bottom, right) else self._cell_rect(bottom, right)
        if not bottom_right.isValid():
            return
        painter = QPainter(self.viewport())
        painter.fillRect(QRect(bottom_right.right() - 4, bottom_right.bottom() - 4, 6, 6), QColor("#217346"))
        if self._fill_drag_target:
            target_row, target_column = self._fill_drag_target
            target = self._cell_rect(target_row, target_column)
            source_rect = self._range_rect(top, left, bottom, right)
            if source_rect.isValid() and target.isValid():
                painter.setPen(QPen(QColor("#217346"), 1, Qt.PenStyle.DashLine))
                painter.drawRect(source_rect.united(target).adjusted(0, 0, -1, -1))
        painter.end()

    def _cell_rect(self, row: int, column: int) -> QRect:
        return QRect(self.columnViewportPosition(column), self.rowViewportPosition(row),
                     self.columnWidth(column), self.rowHeight(row))

    def _range_rect(self, top: int, left: int, bottom: int, right: int) -> QRect:
        return self._cell_rect(top, left).united(self._cell_rect(bottom, right))

    def _selection_bounds(self) -> tuple[int, int, int, int] | None:
        selected = self.selectedIndexes()
        if not selected:
            return None
        return (min(index.row() for index in selected), min(index.column() for index in selected),
                max(index.row() for index in selected), max(index.column() for index in selected))

    def mouseDoubleClickEvent(self, event) -> None:
        """Open image/QR actions without letting Qt create a cell text editor."""
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and ENTRY_HEADERS[index.column()] in {"Ảnh sản phẩm", "Mã QR"}:
            item = self.item(index.row(), index.column())
            if item is not None:
                self.setCurrentItem(item)
                self.itemDoubleClicked.emit(item)
                event.accept()
                return
        bounds = self._selection_bounds()
        if bounds and index.isValid():
            top, left, bottom, right = bounds
            handle = self._cell_rect(bottom, right).adjusted(-2, -2, 2, 2)
            handle.setLeft(handle.right() - 9)
            handle.setTop(handle.bottom() - 9)
            if handle.contains(event.position().toPoint()):
                self.autofill_formula_down(bounds)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        editor = self.findChild(QLineEdit)
        index = self.indexAt(event.position().toPoint())
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and index.isValid() and ((editor and editor.text().startswith("=")) or self.formula_reference_mode)):
            self._formula_reference_drag_origin = (index.row(), index.column())
            event.accept()
            return
        bounds = self._selection_bounds()
        if event.button() == Qt.MouseButton.LeftButton and bounds:
            top, left, bottom, right = bounds
            handle = self._cell_rect(bottom, right).adjusted(-2, -2, 2, 2)
            handle.setLeft(handle.right() - 9)
            handle.setTop(handle.bottom() - 9)
            if handle.contains(event.position().toPoint()):
                self._fill_drag_origin = bounds
                self._fill_drag_target = (bottom, right)
                self._fill_drag_copy_only = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                self.viewport().update()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._formula_reference_drag_origin:
            event.accept()
            return
        if self._fill_drag_origin:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self._fill_drag_target = (index.row(), index.column())
                self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._formula_reference_drag_origin and event.button() == Qt.MouseButton.LeftButton:
            start_row, start_column = self._formula_reference_drag_origin
            self._formula_reference_drag_origin = None
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                end_row, end_column = index.row(), index.column()
                self.setRangeSelected(QTableWidgetSelectionRange(
                    min(start_row, end_row), min(start_column, end_column),
                    max(start_row, end_row), max(start_column, end_column),
                ), True)
                self._append_in_cell_formula_reference(start_row, start_column, end_row, end_column)
                self.formulaReferenceSelected.emit(start_row, start_column, end_row, end_column)
            event.accept()
            return
        if self._fill_drag_origin and event.button() == Qt.MouseButton.LeftButton:
            source, target = self._fill_drag_origin, self._fill_drag_target
            self._fill_drag_origin = None
            self._fill_drag_target = None
            copy_only = self._fill_drag_copy_only
            self._fill_drag_copy_only = False
            if target:
                self.fill_formula_range(source, target, copy_only=copy_only)
            self.viewport().update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _append_in_cell_formula_reference(self, start_row: int, start_column: int, end_row: int, end_column: int) -> None:
        editor = self.findChild(QLineEdit)
        if editor is None or not editor.text().startswith("="):
            return
        start = f"{self._column_name(min(start_column, end_column))}{min(start_row, end_row) + 1}"
        end = f"{self._column_name(max(start_column, end_column))}{max(start_row, end_row) + 1}"
        reference = start if start == end else f"{start}:{end}"
        editor.setText(f"{editor.text()}{reference}")
        editor.setCursorPosition(len(editor.text()))
        editor.setFocus()

    @staticmethod
    def _column_name(column: int) -> str:
        name = ""
        while True:
            column, remainder = divmod(column, 26)
            name = chr(ord("A") + remainder) + name
            if column == 0:
                return name
            column -= 1

    def _translated_formula(self, formula: str, row_delta: int, column_delta: int) -> str:
        def replace(match):
            column_lock, column_name, row_lock, row_number = match.groups()
            column = 0
            for char in column_name.upper():
                column = column * 26 + ord(char) - ord("A") + 1
            column -= 1
            row = int(row_number) - 1
            if not column_lock:
                column += column_delta
            if not row_lock:
                row += row_delta
            if column < 0 or row < 0:
                return "#REF!"
            return f"{column_lock}{self._column_name(column)}{row_lock}{row + 1}"
        return self._A1_REFERENCE.sub(replace, formula)

    @staticmethod
    def _numeric_series_value(values: list[str], position: int) -> str | None:
        """Extend a multi-cell numeric sequence, preserving its inferred step."""
        if len(values) < 2:
            return None
        try:
            numbers = [Decimal(value.replace(",", "")) for value in values]
        except (InvalidOperation, AttributeError):
            return None
        step = (numbers[-1] - numbers[0]) / (len(numbers) - 1)
        result = numbers[0] + step * position
        rendered = format(result, "f")
        return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered

    @staticmethod
    def _date_series_value(values: list[str], position: int) -> str | None:
        """Extend ISO or Vietnamese calendar dates by their source-day interval."""
        if not values:
            return None
        parsed: list[date] = []
        display_format = "%Y-%m-%d"
        try:
            for value in values:
                if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
                    display_format = "%d/%m/%Y"
                    parsed.append(date.fromisoformat(f"{value[6:]}-{value[3:5]}-{value[:2]}"))
                else:
                    parsed.append(date.fromisoformat(value))
        except ValueError:
            return None
        step = 1 if len(parsed) == 1 else (parsed[-1] - parsed[0]).days // (len(parsed) - 1)
        return (parsed[0] + timedelta(days=step * position)).strftime(display_format)

    @staticmethod
    def _text_number_series_value(values: list[str], position: int) -> str | None:
        """Extend labels ending in numbers, retaining their shared prefix and zero padding."""
        if len(values) < 2:
            return None
        matches = [re.fullmatch(r"(.*?)(\d+)", value) for value in values]
        if not all(matches):
            return None
        prefixes = {match.group(1) for match in matches if match}
        if len(prefixes) != 1:
            return None
        numbers = [Decimal(match.group(2)) for match in matches if match]
        step = (numbers[-1] - numbers[0]) / (len(numbers) - 1)
        number = numbers[0] + step * position
        if number != number.to_integral_value():
            return None
        width = max(len(match.group(2)) for match in matches if match)
        return f"{next(iter(prefixes))}{int(number):0{width}d}"

    @staticmethod
    def _calendar_label_series_value(values: list[str], position: int) -> str | None:
        """Extend weekday and month labels through their natural repeating order."""
        calendars = (
            ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
            ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
            ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"),
            ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"),
            ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
            tuple(f"Tháng {month}" for month in range(1, 13)),
        )
        for calendar in calendars:
            try:
                indices = [calendar.index(value) for value in values]
            except ValueError:
                continue
            step = 1 if len(indices) == 1 else (indices[-1] - indices[0]) % len(calendar) // (len(indices) - 1)
            return calendar[(indices[0] + step * position) % len(calendar)]
        return None

    def _series_value(self, values: list[str], position: int) -> str | None:
        return (self._numeric_series_value(values, position)
                or self._date_series_value(values, position)
                or self._text_number_series_value(values, position)
                or self._calendar_label_series_value(values, position))

    def fill_formula_range(self, source: tuple[int, int, int, int], target: tuple[int, int], *, copy_only: bool = False) -> None:
        """Fill a range; Ctrl-drag copies values while the default extends sequences."""
        top, left, bottom, right = source
        target_row, target_column = target
        if top <= target_row <= bottom and left <= target_column <= right:
            return
        row_distance = min(abs(target_row - top), abs(target_row - bottom))
        column_distance = min(abs(target_column - left), abs(target_column - right))
        fill_vertically = (target_row < top or target_row > bottom) and (
            not (target_column < left or target_column > right) or row_distance >= column_distance
        )
        if fill_vertically:
            fill_top, fill_bottom = (target_row, top - 1) if target_row < top else (bottom + 1, target_row)
            fill_left, fill_right = left, right
        else:
            fill_top, fill_bottom = top, bottom
            fill_left, fill_right = (target_column, left - 1) if target_column < left else (right + 1, target_column)
        self._begin_history_transaction()
        self._updating_generated_codes = True
        try:
            for row in range(fill_top, fill_bottom + 1):
                for column in range(fill_left, fill_right + 1):
                    source_row = top + (row - top) % (bottom - top + 1)
                    source_column = left + (column - left) % (right - left + 1)
                    source_item = self.item(source_row, source_column)
                    if source_item is None:
                        continue
                    item = source_item.clone()
                    formula = self.formula_for_item(source_item)
                    if formula.startswith("="):
                        item.setText(self._translated_formula(formula, row - source_row, column - source_column))
                        item.setData(self.RAW_FORMULA_ROLE, item.text())
                    elif fill_vertically and not copy_only:
                        series = [self.item(source_row_, column).text().strip() if self.item(source_row_, column) else ""
                                  for source_row_ in range(top, bottom + 1)]
                        value = self._series_value(series, row - top)
                        if value is not None:
                            item.setText(value)
                    elif not copy_only:
                        series = [self.item(row, source_column_).text().strip() if self.item(row, source_column_) else ""
                                  for source_column_ in range(left, right + 1)]
                        value = self._series_value(series, column - left)
                        if value is not None:
                            item.setText(value)
                    self.setItem(row, column, item)
                self.fit_row_height(row)
        finally:
            self._updating_generated_codes = False
        self.recalculate_formulas()
        self.setRangeSelected(QTableWidgetSelectionRange(min(top, fill_top), min(left, fill_left), max(bottom, fill_bottom), max(right, fill_right)), True)
        self._commit_history_transaction()

    def autofill_formula_down(self, source: tuple[int, int, int, int]) -> None:
        """Match Excel's handle double-click by filling beside contiguous row data."""
        top, left, bottom, right = source
        if not any(self.formula_for_item(self.item(row, column)).startswith("=")
                   for row in range(top, bottom + 1) for column in range(left, right + 1)):
            return
        adjacent_columns = [column for column in (left - 1, right + 1) if 0 <= column < self.columnCount()]
        last_row = bottom
        for row in range(bottom + 1, self.rowCount()):
            if not adjacent_columns or not any(self.item(row, column) and self.item(row, column).text().strip()
                                           for column in adjacent_columns):
                break
            last_row = row
        if last_row > bottom:
            self.fill_formula_range(source, (last_row, right))

    def _snapshot(self):
        return {
            "rows": self.rowCount(),
            "heights": [self.rowHeight(row) for row in range(self.rowCount())],
            "hidden_rows": [self.isRowHidden(row) for row in range(self.rowCount())],
            "hidden_columns": [self.isColumnHidden(column) for column in range(self.columnCount())],
            "items": [[self.item(row, column).clone() if self.item(row, column) else None
                       for column in range(self.columnCount())]
                      for row in range(self.rowCount())],
        }

    def _restore_snapshot(self, snapshot) -> None:
        self._restoring_history = True
        self.blockSignals(True)
        try:
            self.setRowCount(snapshot["rows"])
            for row, items in enumerate(snapshot["items"]):
                for column, item in enumerate(items):
                    self.setItem(row, column, item.clone() if item else None)
                self.setRowHeight(row, snapshot["heights"][row])
                self.setRowHidden(row, snapshot["hidden_rows"][row])
            status_column = ENTRY_HEADERS.index("Trạng thái S/P")
            for column, hidden in enumerate(snapshot["hidden_columns"]):
                self.setColumnHidden(column, hidden or column == status_column)
            self._number_rows()
        finally:
            self.blockSignals(False)
            self._restoring_history = False
        self.recalculate_formulas()
        self._last_snapshot = self._snapshot()
        self.viewport().update()
        self.historyRestored.emit()

    def _record_item_change(self, _item: QTableWidgetItem) -> None:
        if self._restoring_history or self._updating_generated_codes or self._history_transaction is not None:
            return
        self._undo_stack.append(self._last_snapshot)
        self._undo_stack = self._undo_stack[-100:]
        self._redo_stack.clear()
        self._last_snapshot = self._snapshot()

    def _begin_history_transaction(self) -> None:
        if self._history_transaction is None and not self._restoring_history:
            self._history_transaction = self._snapshot()

    def _commit_history_transaction(self) -> None:
        if self._history_transaction is None:
            return
        before = self._history_transaction
        self._history_transaction = None
        current = self._snapshot()
        if current != before:
            self._undo_stack.append(before)
            self._undo_stack = self._undo_stack[-100:]
            self._redo_stack.clear()
        self._last_snapshot = current

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot())
        self._restore_snapshot(self._undo_stack.pop())

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot())
        self._restore_snapshot(self._redo_stack.pop())

    def reset_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._history_transaction = None
        self._last_snapshot = self._snapshot()

    def _update_generated_codes(self, item: QTableWidgetItem) -> None:
        self._style_item(item, item.column())
        self.fit_row_height(item.row())
        if ENTRY_HEADERS[item.column()] == "Trạng thái S/P":
            item.setBackground(QColor(STATUS_COLORS.get(item.text().strip(), "transparent")))
            return
        self._update_row_validation(item.row())
        generated_from = {
            "Khách hàng", "Tên sản phẩm", "Số lượng", "Kích thước X", "Kích thước Y", "Kích thước Z",
        }
        if self._updating_generated_codes:
            return
        if ENTRY_HEADERS[item.column()] not in generated_from:
            return
        row = item.row()
        company = self.item(item.row(), ENTRY_HEADERS.index("Khách hàng"))
        part_name = self.item(row, ENTRY_HEADERS.index("Tên sản phẩm"))
        dimensions = tuple((self.item(row, ENTRY_HEADERS.index(header)).text()
                            if self.item(row, ENTRY_HEADERS.index(header)) else "")
                           for header in ("Kích thước X", "Kích thước Y", "Kích thước Z"))
        quantity = self.item(row, ENTRY_HEADERS.index("Số lượng"))
        if not company or not company.text().strip() or not quantity or not quantity.text().strip():
            self._updating_generated_codes = True
            try:
                for header in ("Mã sản phẩm", "Mã QR", "Trạng thái S/P"):
                    generated = self.item(row, ENTRY_HEADERS.index(header))
                    if generated:
                        generated.setText("")
                        generated.setData(Qt.ItemDataRole.UserRole + 21, None)
                        generated.setBackground(QColor("transparent"))
            finally:
                self._updating_generated_codes = False
            return
        code_value = self._preview_product_codes.get(row)
        delivery = self.delivery_date_provider().isoformat()
        code_value = product_code_value(company.text(), part_name.text() if part_name else "", dimensions, delivery, row)
        self._preview_product_codes[row] = code_value
        self._updating_generated_codes = True
        try:
            code_column = ENTRY_HEADERS.index("Mã sản phẩm")
            qr_column = ENTRY_HEADERS.index("Mã QR")
            code_item = self.item(row, code_column)
            if code_item is None:
                code_item = QTableWidgetItem()
                self.setItem(row, code_column, code_item)
            code_item.setText(code_value)
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            qr_item = self.item(row, qr_column)
            if qr_item is None:
                qr_item = QTableWidgetItem()
                self.setItem(row, qr_column, qr_item)
            qr_item.setText(product_qr_value(code_value, company.text() if company else ""))
            qr_item.setData(
                Qt.ItemDataRole.UserRole + 21,
                product_qr_label_png(
                    qr_item.text(), code_value, part_name.text() if part_name else "",
                    format_dimensions(list(dimensions)), self.delivery_date_provider(),
                ),
            )
            qr_item.setFlags(qr_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status_column = ENTRY_HEADERS.index("Trạng thái S/P")
            status_item = self.item(row, status_column)
            if status_item is None:
                status_item = QTableWidgetItem("Mới")
                self.setItem(row, status_column, status_item)
            if not status_item.text().strip():
                status_item.setText("Mới")
            status_item.setBackground(QColor(STATUS_COLORS.get(status_item.text().strip(), "transparent")))
        finally:
            self._updating_generated_codes = False

    def _update_row_validation(self, row: int) -> None:
        """Flag only quantities the API cannot store; partial rows are allowed."""
        company_column = ENTRY_HEADERS.index("Khách hàng")
        quantity_column = ENTRY_HEADERS.index("Số lượng")
        company = self.item(row, company_column)
        quantity = self.item(row, quantity_column)
        for item, message in (
            (company, ""),
            (quantity, "Số lượng phải là số không âm." if quantity and quantity.text().strip() and not self._is_nonnegative_quantity(quantity.text()) else ""),
        ):
            if item is None:
                continue
            if message:
                item.setBackground(QColor(VALIDATION_WARNING_COLOR))
                item.setToolTip(message)
            elif (ENTRY_HEADERS[item.column()] in {"Khách hàng", "Số lượng"}
                  and not self.formula_for_item(item).startswith("=")):
                item.setBackground(QColor("transparent"))
                item.setToolTip("")

    @staticmethod
    def _is_nonnegative_quantity(value: str) -> bool:
        try:
            quantity = Decimal(value.replace(",", ""))
            return quantity.is_finite() and quantity >= 0
        except InvalidOperation:
            return False

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo()
            return
        if event.matches(QKeySequence.StandardKey.SelectAll):
            self.select_used_range()
            return
        directions = {
            Qt.Key.Key_Left: (0, -1), Qt.Key.Key_Right: (0, 1),
            Qt.Key.Key_Up: (-1, 0), Qt.Key.Key_Down: (1, 0),
        }
        extending_selection = (
            event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
            and event.key() in (*directions, Qt.Key.Key_Home, Qt.Key.Key_End)
        ) or (
            event.modifiers() == Qt.KeyboardModifier.ShiftModifier
            and event.key() in (*directions, Qt.Key.Key_Home, Qt.Key.Key_End)
        )
        if not extending_selection:
            self._keyboard_selection_anchor = None
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() in directions):
            self.navigate_to_data_edge(*directions[event.key()])
            return
        if (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                and event.key() in directions):
            self.extend_selection_to_data_edge(*directions[event.key()])
            return
        if (event.modifiers() == Qt.KeyboardModifier.ShiftModifier
                and event.key() in directions):
            self.extend_selection_by(*directions[event.key()])
            return
        if (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                and event.key() == Qt.Key.Key_Home):
            self.extend_selection_to(0, 0, preserve_anchor=True)
            return
        if (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                and event.key() == Qt.Key.Key_End):
            self.extend_selection_to(*self._used_range_end(), preserve_anchor=True)
            return
        if (event.modifiers() == Qt.KeyboardModifier.ShiftModifier
                and event.key() == Qt.Key.Key_Space):
            self.select_current_row()
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_Space):
            self.select_current_column()
            return
        if (event.modifiers() == Qt.KeyboardModifier.ShiftModifier
                and event.key() == Qt.Key.Key_Home):
            self.extend_selection_to(max(self.currentRow(), 0), 0, preserve_anchor=True)
            return
        if (event.modifiers() == Qt.KeyboardModifier.ShiftModifier
                and event.key() == Qt.Key.Key_End):
            self.extend_selection_to(max(self.currentRow(), 0), self.columnCount() - 1, preserve_anchor=True)
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_D):
            self.fill_selection_down()
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_R):
            self.fill_selection_right()
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_Semicolon):
            self.fill_selected_cells(self.today_provider().isoformat())
            return
        if (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                and event.key() in (Qt.Key.Key_Semicolon, Qt.Key.Key_Colon)):
            self.fill_selected_cells(self.current_time_provider())
            return
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() in {
            Qt.Key.Key_B, Qt.Key.Key_I, Qt.Key.Key_U, Qt.Key.Key_5,
        }:
            self.formatRequested.emit({
                Qt.Key.Key_B: "bold", Qt.Key.Key_I: "italic", Qt.Key.Key_U: "underline", Qt.Key.Key_5: "strikethrough",
            }[event.key()])
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_1):
            self.cellFormatRequested.emit()
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() in (Qt.Key.Key_QuoteLeft, Qt.Key.Key_AsciiTilde)):
            self.toggle_formula_view()
            return
        if (event.modifiers() == Qt.KeyboardModifier.AltModifier
                and event.key() in (Qt.Key.Key_Equal, Qt.Key.Key_Plus)):
            self.autoSumRequested.emit()
            return
        if ((event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Plus)
                or (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                    and event.key() == Qt.Key.Key_Equal)):
            self.insert_entry_row()
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_Minus):
            self.delete_selected_rows()
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_0):
            self.set_selected_columns_hidden(True, {index.column() for index in self.selectedIndexes()})
            return
        if (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                and event.key() == Qt.Key.Key_0):
            self.set_selected_columns_hidden(False)
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_9):
            self.set_selected_rows_hidden(True, {index.row() for index in self.selectedIndexes()})
            return
        if (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                and event.key() == Qt.Key.Key_9):
            self.set_selected_rows_hidden(False)
            return
        if event.key() == Qt.Key.Key_Home:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.setCurrentCell(0, 0)
            else:
                self.setCurrentCell(max(self.currentRow(), 0), 0)
            return
        if (event.key() == Qt.Key.Key_End
                and event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            self.navigate_to_used_range_end()
            return
        if ((event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_G)
                or (event.modifiers() == Qt.KeyboardModifier.NoModifier and event.key() == Qt.Key.Key_F5)):
            self.show_go_to_dialog()
            return
        if event.matches(QKeySequence.StandardKey.Find):
            self.show_find_dialog()
            return
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_H:
            self.show_find_dialog(replace=True)
            return
        if event.key() == Qt.Key.Key_F3 and event.modifiers() in {
            Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier,
        }:
            self.find_next(self._find_needle, self._find_match_case,
                           backwards=event.modifiers() == Qt.KeyboardModifier.ShiftModifier)
            return
        if event.key() == Qt.Key.Key_F2:
            item = self.currentItem()
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsEditable:
                self.editItem(item)
                editor = self.findChild(QLineEdit)
                if editor is not None:
                    editor.setCursorPosition(len(editor.text()))
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.clear_selected_cells()
            return
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return)):
            item = self.currentItem()
            if item is not None:
                self.fill_selected_cells(self.formula_for_item(item))
            return
        if (event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                and event.key() == Qt.Key.Key_V):
            self.paste_values_from_clipboard()
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste_from_clipboard()
            return
        if event.matches(QKeySequence.StandardKey.Cut):
            self.cut_to_clipboard()
            return
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_to_clipboard()
            return
        super().keyPressEvent(event)

    def select_current_row(self) -> None:
        """Select the full active worksheet row for Shift+Space."""
        row = self.currentRow()
        if row < 0 or not self.columnCount():
            return
        self.clearSelection()
        self.setCurrentCell(row, 0)
        self.setRangeSelected(QTableWidgetSelectionRange(row, 0, row, self.columnCount() - 1), True)

    def select_current_column(self) -> None:
        """Select the full active worksheet column for Ctrl+Space."""
        column = self.currentColumn()
        if column < 0 or not self.rowCount():
            return
        self.clearSelection()
        self.setCurrentCell(0, column)
        self.setRangeSelected(QTableWidgetSelectionRange(0, column, self.rowCount() - 1, column), True)

    def set_selected_columns_hidden(self, hidden: bool, selected_columns: set[int] | None = None) -> None:
        """Hide selected schema columns, keeping the frozen status column system-owned."""
        selected_columns = selected_columns if selected_columns is not None else {index.column() for index in self.selectedIndexes()}
        status_column = ENTRY_HEADERS.index("Trạng thái S/P")
        if hidden:
            columns = selected_columns or ({self.currentColumn()} if self.currentColumn() >= 0 else set())
            columns -= {status_column}
        else:
            columns = set(range(self.columnCount())) - {status_column}
        if not columns:
            return
        self._begin_history_transaction()
        for column in columns:
            self.setColumnHidden(column, hidden)
        self._commit_history_transaction()

    def set_selected_rows_hidden(self, hidden: bool, selected_rows: set[int] | None = None) -> None:
        """Hide selected rows or reveal all rows without changing worksheet data."""
        selected_rows = selected_rows if selected_rows is not None else {index.row() for index in self.selectedIndexes()}
        if hidden:
            rows = selected_rows or ({self.currentRow()} if self.currentRow() >= 0 else set())
        else:
            rows = set(range(self.rowCount()))
        if not rows:
            return
        self._begin_history_transaction()
        for row in rows:
            self.setRowHidden(row, hidden)
        self._commit_history_transaction()

    def _reset_keyboard_selection_anchor(self, *_args) -> None:
        """Discard a shortcut anchor when navigation comes from another action."""
        if not self._extending_keyboard_selection:
            self._keyboard_selection_anchor = None

    def navigate_to_data_edge(self, row_step: int, column_step: int) -> None:
        """Move Ctrl+Arrow to the next edge of contiguous worksheet data."""
        row, column = self.currentRow(), self.currentColumn()
        if row < 0 or column < 0:
            return
        self.setCurrentCell(*self._data_edge(row, column, row_step, column_step))

    def _data_edge(self, row: int, column: int, row_step: int, column_step: int) -> tuple[int, int]:
        """Return the Ctrl+Arrow destination without changing the current selection."""
        populated = bool(self.formula_for_item(self.item(row, column)).strip())
        while True:
            next_row, next_column = row + row_step, column + column_step
            if not (0 <= next_row < self.rowCount() and 0 <= next_column < self.columnCount()):
                break
            next_populated = bool(self.formula_for_item(self.item(next_row, next_column)).strip())
            if populated and not next_populated and (row, column) != (self.currentRow(), self.currentColumn()):
                break
            row, column = next_row, next_column
            if populated and not next_populated:
                populated = False
            elif not populated and next_populated:
                break
        return row, column

    def extend_selection_to_data_edge(self, row_step: int, column_step: int) -> None:
        """Extend Ctrl+Shift+Arrow selection from its active cell to the data edge."""
        anchor = (self.currentRow(), self.currentColumn())
        if min(anchor) < 0:
            return
        target = self._data_edge(*anchor, row_step, column_step)
        self.extend_selection_to(*target, preserve_anchor=True)

    def extend_selection_by(self, row_step: int, column_step: int) -> None:
        """Extend Shift+Arrow selection by one cell without leaving the grid."""
        row, column = self.currentRow(), self.currentColumn()
        if row < 0 or column < 0:
            return
        target_row = min(max(0, row + row_step), self.rowCount() - 1)
        target_column = min(max(0, column + column_step), self.columnCount() - 1)
        self.extend_selection_to(target_row, target_column, preserve_anchor=True)

    def extend_selection_to(self, row: int, column: int, *, preserve_anchor: bool = False) -> None:
        """Select the rectangle from the current cell to a keyboard shortcut target."""
        anchor = self._keyboard_selection_anchor if preserve_anchor else None
        anchor = anchor or (self.currentRow(), self.currentColumn())
        if min(anchor) < 0:
            return
        if preserve_anchor:
            self._keyboard_selection_anchor = anchor
        self.clearSelection()
        self._extending_keyboard_selection = True
        try:
            self.setCurrentCell(row, column)
        finally:
            self._extending_keyboard_selection = False
        self.setRangeSelected(QTableWidgetSelectionRange(
            min(anchor[0], row), min(anchor[1], column),
            max(anchor[0], row), max(anchor[1], column),
        ), True)

    def navigate_to_used_range_end(self) -> None:
        """Move Ctrl+End to the lower-right populated worksheet cell."""
        self.setCurrentCell(*self._used_range_end())

    def _used_range_end(self) -> tuple[int, int]:
        """Return the lower-right populated worksheet cell."""
        populated = [
            (row, column) for row in range(self.rowCount()) for column in range(self.columnCount())
            if self.formula_for_item(self.item(row, column)).strip()
        ]
        return max(populated, default=(0, 0))

    def show_go_to_dialog(self) -> None:
        """Prompt for an A1 address without changing selection on cancellation."""
        address, accepted = QInputDialog.getText(self, "Đi tới", "Địa chỉ ô (ví dụ: B12):")
        if accepted:
            self.go_to_address(address)

    def go_to_address(self, address: str) -> bool:
        """Move to a valid in-grid A1 address and report whether it was accepted."""
        match = re.fullmatch(r"\s*\$?([A-Z]{1,3})\$?(\d+)\s*", address, re.IGNORECASE)
        if not match:
            return False
        letters, row_text = match.groups()
        column = 0
        for letter in letters.upper():
            column = column * 26 + ord(letter) - ord("A") + 1
        row = int(row_text) - 1
        column -= 1
        if not (0 <= row < self.rowCount() and 0 <= column < self.columnCount()):
            return False
        self.setCurrentCell(row, column)
        self.scrollToItem(self.item(row, column))
        return True

    def fill_selection_down(self) -> None:
        """Copy the selected range's top row downward, translating formulas by row."""
        bounds = self._selection_bounds()
        if bounds is None:
            return
        top, left, bottom, right = bounds
        if top == bottom:
            return
        self._begin_history_transaction()
        self._updating_generated_codes = True
        try:
            for row in range(top + 1, bottom + 1):
                for column in range(left, right + 1):
                    target = self.item(row, column)
                    if target is not None and not (target.flags() & Qt.ItemFlag.ItemIsEditable):
                        continue
                    source = self.item(top, column)
                    if source is None:
                        continue
                    item = source.clone()
                    formula = self.formula_for_item(source)
                    if formula.startswith("="):
                        item.setText(self._translated_formula(formula, row - top, 0))
                        item.setData(self.RAW_FORMULA_ROLE, item.text())
                    self.setItem(row, column, item)
                self.fit_row_height(row)
        finally:
            self._updating_generated_codes = False
        self.recalculate_formulas()
        self._commit_history_transaction()

    def fill_selection_right(self) -> None:
        """Copy the selected range's left column rightward, translating formulas by column."""
        bounds = self._selection_bounds()
        if bounds is None:
            return
        top, left, bottom, right = bounds
        if left == right:
            return
        self._begin_history_transaction()
        self._updating_generated_codes = True
        try:
            for row in range(top, bottom + 1):
                source = self.item(row, left)
                if source is None:
                    continue
                formula = self.formula_for_item(source)
                for column in range(left + 1, right + 1):
                    target = self.item(row, column)
                    if target is not None and not (target.flags() & Qt.ItemFlag.ItemIsEditable):
                        continue
                    item = source.clone()
                    if formula.startswith("="):
                        item.setText(self._translated_formula(formula, 0, column - left))
                        item.setData(self.RAW_FORMULA_ROLE, item.text())
                    self.setItem(row, column, item)
            for row in range(top, bottom + 1):
                self.fit_row_height(row)
        finally:
            self._updating_generated_codes = False
        self.recalculate_formulas()
        self._commit_history_transaction()

    def select_used_range(self) -> None:
        """Select populated cells first, then the full worksheet on a second Ctrl+A."""
        populated = [
            (row, column) for row in range(self.rowCount()) for column in range(self.columnCount())
            if self.formula_for_item(self.item(row, column)).strip()
        ]
        if not populated:
            self.selectAll()
            return
        top = min(row for row, _column in populated)
        left = min(column for _row, column in populated)
        bottom = max(row for row, _column in populated)
        right = max(column for _row, column in populated)
        if self._selection_bounds() == (top, left, bottom, right):
            self.selectAll()
            return
        self.clearSelection()
        self.setCurrentCell(top, left)
        self.setRangeSelected(QTableWidgetSelectionRange(top, left, bottom, right), True)

    def eventFilter(self, watched, event) -> bool:
        if (isinstance(watched, QLineEdit) and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_F4 and cycle_formula_reference_lock(watched)):
            return True
        if (isinstance(watched, QLineEdit) and event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.fill_selected_cells(complete_formula_parentheses(watched.text()))
            self.closeEditor(watched, QAbstractItemDelegate.EndEditHint.NoHint)
            return True
        return super().eventFilter(watched, event)

    def fill_selected_cells(self, value: str) -> int:
        """Apply one entered value to every editable cell in the current selection."""
        selected = self.selectedIndexes()
        if not selected and self.currentIndex().isValid():
            selected = [self.currentIndex()]
        self._begin_history_transaction()
        changed = 0
        for index in selected:
            item = self.item(index.row(), index.column())
            if item is not None and not (item.flags() & Qt.ItemFlag.ItemIsEditable):
                continue
            if item is None:
                item = QTableWidgetItem()
                self._style_item(item, index.column())
                self.setItem(index.row(), index.column(), item)
            item.setText(value)
            changed += 1
        self._commit_history_transaction()
        return changed

    def show_find_dialog(self, replace: bool = False) -> None:
        dialog = SpreadsheetFindDialog(self, replace)
        dialog.show()
        dialog.find_text.setFocus()

    def find_next(self, needle: str, match_case: bool = False, *, backwards: bool = False) -> bool:
        if not needle:
            return False
        self._find_needle = needle
        self._find_match_case = match_case
        indexes = [(row, column) for row in range(self.rowCount()) for column in range(self.columnCount())]
        if not indexes:
            return False
        current = (self.currentRow(), self.currentColumn())
        try:
            start = indexes.index(current) - 1 if backwards else indexes.index(current) + 1
        except ValueError:
            start = -1 if backwards else 0
        target = needle if match_case else needle.casefold()
        for offset in range(len(indexes)):
            row, column = indexes[(start - offset if backwards else start + offset) % len(indexes)]
            item = self.item(row, column)
            value = self.value_for_item(item)
            candidate = value if match_case else value.casefold()
            if target in candidate:
                self.setCurrentCell(row, column)
                self.setRangeSelected(QTableWidgetSelectionRange(row, column, row, column), True)
                self.scrollToItem(item)
                return True
        return False

    def replace_current(self, needle: str, replacement: str, match_case: bool = False) -> bool:
        item = self.currentItem()
        if not needle or item is None or not (item.flags() & Qt.ItemFlag.ItemIsEditable):
            return False
        value = self.value_for_item(item)
        flags = 0 if match_case else re.IGNORECASE
        updated, count = re.subn(re.escape(needle), replacement, value, count=1, flags=flags)
        if not count:
            return False
        self._begin_history_transaction()
        item.setText(updated)
        self._commit_history_transaction()
        return True

    def replace_all(self, needle: str, replacement: str, match_case: bool = False) -> int:
        if not needle:
            return 0
        flags = 0 if match_case else re.IGNORECASE
        replaced = 0
        self._begin_history_transaction()
        for row in range(self.rowCount()):
            for column in range(self.columnCount()):
                item = self.item(row, column)
                if item is None or not (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    continue
                updated, count = re.subn(re.escape(needle), replacement, self.value_for_item(item), flags=flags)
                if count:
                    item.setText(updated)
                    replaced += count
        self._commit_history_transaction()
        return replaced

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = 10 if event.angleDelta().y() > 0 else -10
            if event.angleDelta().y():
                self.zoomRequested.emit(delta)
            event.accept()
            return
        super().wheelEvent(event)

    def clear_selected_cells(self) -> None:
        """Clear selected editable cells, including the PNG backing an image thumbnail."""
        self._begin_history_transaction()
        selected = self.selectedIndexes()
        if not selected and self.currentIndex().isValid():
            selected = [self.currentIndex()]
        for index in selected:
            item = self.item(index.row(), index.column())
            if item is None or not (item.flags() & Qt.ItemFlag.ItemIsEditable):
                continue
            item.setText("")
            item.setData(self.RAW_VALUE_ROLE, None)
            item.setData(Qt.ItemDataRole.UserRole, None)
            item.setData(Qt.ItemDataRole.UserRole + 21, None)
        self.viewport().update()
        self._commit_history_transaction()

    def paste_from_clipboard(self) -> None:
        self._begin_history_transaction()
        clipboard = QApplication.clipboard()
        target_row = self.currentRow()
        target_column = self.currentColumn()
        text = clipboard.text()
        # Excel places a preview image beside TSV cell data on the Clipboard.
        # Prefer the cell data so copying a range does not turn into image paste.
        if text:
            self._paste_tabular_text(text)
            self._commit_history_transaction()
            return
        image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
        images = self._clipboard_images(clipboard.mimeData())
        if images and len(images) <= 1:
            excel_images = self._excel_selected_images()
            if excel_images:
                images = excel_images
        if images:
            self.paste_images(images, max(target_row, 0), image_column)
            self._commit_history_transaction()
            return

        self._commit_history_transaction()

    def paste_values_from_clipboard(self) -> None:
        """Paste clipboard text literally so formulas remain displayed values."""
        text = QApplication.clipboard().text()
        if not text:
            return
        self._begin_history_transaction()
        self._paste_tabular_text(text, values_only=True)
        self._commit_history_transaction()

    def _paste_tabular_text(self, text: str, *, values_only: bool = False) -> None:
        selected = self.selectedIndexes()
        start_row = min((index.row() for index in selected), default=self.currentRow())
        start_column = min((index.column() for index in selected), default=self.currentColumn())
        if start_row < 0 or start_column < 0:
            start_row = start_column = 0
        source_rows = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if source_rows and source_rows[-1] == "":
            source_rows.pop()
        required_rows = start_row + len(source_rows)
        if required_rows > self.rowCount():
            self.setRowCount(required_rows)
            self._number_rows()
            for row in range(start_row, required_rows):
                self.setRowHeight(row, 62)
        self._rendering_formulas = values_only
        try:
            for row_offset, source_row in enumerate(source_rows):
                target_row = start_row + row_offset
                for column_offset, value in enumerate(source_row.split("\t")):
                    target_column = start_column + column_offset
                    if target_column >= self.columnCount():
                        break
                    if ENTRY_HEADERS[target_column] in {"Mã QR", "Mã sản phẩm"}:
                        continue
                    item = QTableWidgetItem(value)
                    self._style_item(item, target_column)
                    if values_only:
                        item.setData(self.LITERAL_FORMULA_ROLE, True)
                    self.setItem(target_row, target_column, item)
                self.fit_row_height(target_row)
        finally:
            self._rendering_formulas = False
        self.recalculate_formulas()

    def _clipboard_images(self, mime) -> list[QImage]:
        images = []
        for url in mime.urls():
            path = url.toLocalFile()
            image = QImage(path) if path else QImage()
            if not image.isNull():
                images.append(image)
        if images:
            return images
        for encoded in re.findall(r"data:image/[^;]+;base64,([^\"'\s>]+)", mime.html(), re.IGNORECASE):
            image = QImage()
            image.loadFromData(base64.b64decode(encoded), "PNG")
            if not image.isNull():
                images.append(image)
        if images:
            return images
        if mime.hasImage():
            image = QApplication.clipboard().image()
            if not image.isNull():
                images.append(image)
        return images

    @staticmethod
    def _excel_selected_images() -> list[QImage]:
        """Extract Excel pictures at print quality rather than screen-preview quality."""
        try:
            import win32com.client
            from PIL import ImageGrab
            excel = win32com.client.GetActiveObject("Excel.Application")
            selected = excel.Selection.ShapeRange
            shapes = [selected.Item(index) for index in range(1, selected.Count + 1)]
        except Exception:
            return []
        images = []
        for shape in shapes:
            try:
                # xlPrinter (2) retains substantially more detail than xlScreen (1).
                # Some Excel shapes cannot render for a printer, so retain a safe fallback.
                try:
                    shape.CopyPicture(Appearance=2, Format=2)
                except Exception:
                    shape.CopyPicture(Appearance=1, Format=2)
                time.sleep(0.08)
                captured = ImageGrab.grabclipboard()
                if captured is None:
                    continue
                output = BytesIO()
                captured.save(output, format="PNG")
                image = QImage()
                image.loadFromData(output.getvalue(), "PNG")
                if not image.isNull():
                    images.append(image)
            except Exception:
                continue
        return images

    def paste_images(self, images: list[QImage], start_row: int, image_column: int | None = None) -> None:
        self._begin_history_transaction()
        image_column = ENTRY_HEADERS.index("Ảnh sản phẩm") if image_column is None else image_column
        required_rows = start_row + len(images)
        if required_rows > self.rowCount():
            self.setRowCount(required_rows)
            self._number_rows()
        for offset, image in enumerate(images):
            item = QTableWidgetItem()
            self._style_item(item, image_column)
            item.setData(Qt.ItemDataRole.UserRole, self._image_as_png(image))
            row = start_row + offset
            self.setItem(row, image_column, item)
            self.fit_row_height(row)
        self.setCurrentCell(start_row, image_column)
        self._commit_history_transaction()

    def copy_to_clipboard(self) -> None:
        image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
        if self.currentColumn() == image_column:
            item = self.item(self.currentRow(), image_column)
            if item:
                png = item.data(Qt.ItemDataRole.UserRole)
                if png:
                    image = QImage()
                    image.loadFromData(png, "PNG")
                    if not image.isNull():
                        QApplication.clipboard().setImage(image)
                        return
                path = Path(item.text())
                if path.is_file():
                    image = QImage(str(path))
                    if not image.isNull():
                        QApplication.clipboard().setImage(image)
                        return
        selected = self.selectedIndexes()
        if not selected:
            return
        rows = sorted({index.row() for index in selected})
        columns = sorted({index.column() for index in selected})
        lines = []
        for row in rows:
            values = []
            for column in columns:
                item = self.item(row, column)
                values.append(self.value_for_item(item))
            lines.append("\t".join(values))
        QApplication.clipboard().setText("\r\n".join(lines))

    def cut_to_clipboard(self) -> None:
        """Copy the active selection, then clear only editable worksheet cells."""
        self.copy_to_clipboard()
        self.clear_selected_cells()

    @staticmethod
    def _image_as_png(image: QImage) -> bytes:
        output = QByteArray()
        buffer = QBuffer(output)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(output)

    def insert_entry_row(self) -> None:
        self._begin_history_transaction()
        row = self.currentRow() if self.currentRow() >= 0 else self.rowCount()
        self.insertRow(row)
        self._number_rows()
        self._commit_history_transaction()

    def delete_selected_rows(self) -> None:
        self._begin_history_transaction()
        for row in sorted({index.row() for index in self.selectedIndexes()}, reverse=True):
            self.removeRow(row)
        if self.rowCount() == 0:
            self.setRowCount(1)
        self._number_rows()
        self._commit_history_transaction()

    def move_selected_row(self, offset: int) -> None:
        row = self.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.rowCount():
            return
        self._begin_history_transaction()
        values = [self.takeItem(row, column) for column in range(self.columnCount())]
        self.insertRow(target)
        for column, item in enumerate(values):
            self.setItem(target, column, item or QTableWidgetItem())
        self.removeRow(row + 1 if target < row else row)
        self._number_rows()
        self.setCurrentCell(target, 0)
        self._commit_history_transaction()

    def _number_rows(self) -> None:
        for row in range(self.rowCount()):
            self.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))

    def formula_for_item(self, item: QTableWidgetItem | None) -> str:
        if not item:
            return ""
        return item.data(self.RAW_FORMULA_ROLE) or item.text()

    def value_for_item(self, item: QTableWidgetItem | None) -> str:
        """Return the unformatted worksheet value used by data operations."""
        if not item:
            return ""
        raw_value = item.data(self.RAW_VALUE_ROLE)
        return raw_value if raw_value is not None else self.formula_for_item(item)

    @staticmethod
    def _format_value(value: str, display_format: str | None) -> str:
        if not display_format or display_format == "General" or value.startswith("="):
            return value
        if display_format in {"dd/MM/yyyy", "dd-MM-yyyy"}:
            try:
                parsed_date = date.fromisoformat(value)
            except ValueError:
                return value
            return parsed_date.strftime("%d/%m/%Y" if display_format == "dd/MM/yyyy" else "%d-%m-%Y")
        try:
            number = Decimal(value.replace(",", ""))
        except InvalidOperation:
            return value
        if display_format == "0":
            return f"{number:.0f}"
        if display_format == "0.00":
            return f"{number:.2f}"
        if display_format == "#,##0":
            return f"{number:,.0f}"
        if display_format == "#,##0.00":
            return f"{number:,.2f}"
        return value

    def apply_display_format(self, item: QTableWidgetItem, display_format: str) -> None:
        """Store a numeric display format while retaining the original cell value."""
        raw_value = self.value_for_item(item)
        was_rendering = self._rendering_formulas
        self._rendering_formulas = True
        try:
            item.setData(self.RAW_VALUE_ROLE, raw_value)
            item.setData(self.DISPLAY_FORMAT_ROLE, None if display_format == "General" else display_format)
            item.setText(self._format_value(raw_value, display_format))
        finally:
            self._rendering_formulas = was_rendering

    @staticmethod
    def _formula_input_value(value: str) -> object:
        """Let FormulaEngine receive numeric cells as numbers while UI keeps text."""
        try:
            return Decimal(value.replace(",", "")) if value.strip() else value
        except InvalidOperation:
            return value

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._rendering_formulas:
            return
        self._rendering_formulas = True
        try:
            item.setData(self.LITERAL_FORMULA_ROLE, None)
            raw_value = item.text()
            display_format = item.data(self.DISPLAY_FORMAT_ROLE)
            item.setData(self.RAW_VALUE_ROLE, raw_value if display_format and not raw_value.startswith("=") else None)
            if item.text().startswith("="):
                item.setData(self.RAW_FORMULA_ROLE, item.text())
            elif item.data(self.RAW_FORMULA_ROLE):
                item.setData(self.RAW_FORMULA_ROLE, None)
            if display_format and not raw_value.startswith("="):
                item.setText(self._format_value(raw_value, display_format))
        finally:
            self._rendering_formulas = False
        self.recalculate_formulas()

    def recalculate_formulas(self) -> None:
        cache: dict[tuple[int, int], object] = {}
        calculating: set[tuple[int, int]] = set()

        def value_at(row: int, column: int) -> object:
            key = (row, column)
            if key in cache:
                return cache[key]
            if key in calculating:
                raise FormulaError("Tham chiếu vòng", "#REF!")
            item = self.item(row, column)
            raw = self.formula_for_item(item)
            if item and item.data(self.LITERAL_FORMULA_ROLE) or not raw.startswith("="):
                cache[key] = self._formula_input_value(self.value_for_item(item))
                return cache[key]
            calculating.add(key)
            try:
                cache[key] = FormulaEngine(value_at, self.rowCount(), self.columnCount()).evaluate(raw)
            finally:
                calculating.remove(key)
            return cache[key]

        self._rendering_formulas = True
        try:
            for row in range(self.rowCount()):
                for column in range(self.columnCount()):
                    item = self.item(row, column)
                    if (item and not item.data(self.LITERAL_FORMULA_ROLE)
                            and self.formula_for_item(item).startswith("=")):
                        try:
                            if self._showing_formulas:
                                item.setText(self.formula_for_item(item))
                            else:
                                result = value_at(row, column)
                                item.setText(self._display_formula_result(result))
                            item.setToolTip(self.formula_for_item(item))
                        except FormulaError as exc:
                            item.setText(exc.code)
                            item.setToolTip(f"{self.formula_for_item(item)}\n{exc}")
        finally:
            self._rendering_formulas = False

    def toggle_formula_view(self) -> None:
        """Toggle formula text without changing formula values or worksheet history."""
        self._showing_formulas = not self._showing_formulas
        self.recalculate_formulas()
        self.fit_all_row_heights()
        self.viewport().update()

    @staticmethod
    def _display_formula_result(result: object) -> str:
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)


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
        values = [product.product_code, product.company, product.part_name, format_quantity(product.quantity), product.unit,
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
    def __init__(self, on_submit, *, editable: bool = True) -> None:
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
        self.submit_button = QPushButton("Lưu sản phẩm")
        self.submit_button.clicked.connect(self.submit)
        form = QFormLayout(self)
        for label, widget in (("Mã sản phẩm", self.code), ("Công ty", self.company), ("Tên chi tiết", self.part_name),
                              ("Số lượng", self.quantity), ("Đơn vị", self.unit), ("Vật liệu", self.material),
                              ("Trạng thái", self.status)):
            form.addRow(label, widget)
        form.addRow(self.submit_button)
        self.set_editable(editable)

    def set_editable(self, editable: bool) -> None:
        for widget in (self.code, self.company, self.part_name, self.quantity, self.unit, self.material, self.status, self.submit_button):
            widget.setEnabled(editable)

    def submit(self) -> None:
        try:
            self.on_submit({"product_code": self.code.text() or None, "company": self.company.text(),
                            "part_name": self.part_name.text(), "quantity": Decimal(self.quantity.text()),
                            "unit": self.unit.text(), "material": self.material.text() or None,
                            "status": self.status.currentData()})
        except (ProductValidationError, ValueError) as exc:
            QMessageBox.warning(self, "Dữ liệu chưa hợp lệ", str(exc))


class ProductMasterWindow(QMainWindow):
    def __init__(
        self,
        service: ProductService,
        actor: str = "desktop-user",
        managed_file_service=None,
        transfer_service=None,
        server_url: str = "",
        account_role: str = "",
    ) -> None:
        super().__init__()
        self.service = service
        self.actor = actor
        self.server_url = server_url.rstrip("/")
        self.account_role = account_role
        self.is_viewer = account_role.upper() == "VIEWER"
        self.is_admin = account_role.upper() == "ADMIN"
        self.setWindowTitle("HMS QR — Quản lý sản phẩm")
        self.resize(1100, 620)
        self.setStyleSheet(PY_SIDE_THEME)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm mã, công ty, tên chi tiết, vật liệu...")
        self.filter_status = QComboBox()
        self.filter_status.addItem("Tất cả trạng thái", None)
        for item in ProductStatus:
            self.filter_status.addItem(STATUS_LABELS[item], item)
        refresh = QPushButton("Làm mới")
        refresh.clicked.connect(self.refresh)
        copy_products = QPushButton("COPY DANH SÁCH ĐANG LỌC")
        copy_products.clicked.connect(self.copy_to_excel)
        self.open_stage2_button = QPushButton("KHÁCH HÀNG / PO")
        self.open_stage2_button.clicked.connect(self.open_stage2)
        self.open_stage2_button.setEnabled(bool(self.server_url and getattr(service, "access_token", "")))
        self.product_result_count = QLabel()
        self.table = QTableView()
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.model = ProductTableModel()
        self.table.setModel(self.model)
        self.table.selectionModel().selectionChanged.connect(self._select_product_files)
        self.files_panel = ProductFilesPanel(managed_file_service, transfer_service, actor, editable=not self.is_viewer)
        self.admin_storage_panel = AdminStoragePanel(transfer_service)
        self.entry_grid = SpreadsheetEntryGrid(12, len(ENTRY_HEADERS))
        self.entry_grid.delivery_date_provider = lambda: self.selected_delivery_date
        self.entry_grid.setHorizontalHeaderLabels([
            f"\n{ENTRY_HEADER_LABELS[header]}" if header.startswith("Kích thước ") else f"{self._excel_column_name(column)}\n{ENTRY_HEADER_LABELS[header]}"
            for column, header in enumerate(ENTRY_HEADERS)
        ])
        self.entry_grid.setVerticalHeaderLabels([str(row + 1) for row in range(self.entry_grid.rowCount())])
        self.entry_grid.setHorizontalHeader(SpreadsheetHeader(self.entry_grid))
        self.entry_grid.horizontalHeader().sectionResized.connect(self.entry_grid._mark_column_resized)
        self.entry_grid.setAlternatingRowColors(True)
        self.entry_grid.setWordWrap(True)
        self.entry_grid.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.entry_grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.entry_grid.setMinimumHeight(260)
        self.entry_grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.entry_grid.horizontalHeader().setSectionsMovable(True)
        self.entry_grid.horizontalHeader().setHighlightSections(True)
        self.entry_grid.horizontalHeader().sectionResized.connect(lambda *_args: self.entry_grid.horizontalHeader().viewport().update())
        self.entry_grid.horizontalHeader().filterRequested.connect(self.open_column_filter)
        self._column_filters: dict[int, set[str]] = {}
        self.selected_delivery_date = date.today()
        self._entry_products_by_date: dict[date, list] = {}
        self._entry_products_month: tuple[int, int] | None = None
        self._latest_product_version: tuple[str, datetime] | None = None
        self._lan_change_notice_visible = False
        self._product_change_timer = QTimer(self)
        self._product_change_timer.setInterval(30_000)
        self._product_change_timer.timeout.connect(self.check_for_product_changes)
        self._trim_blank_rows_timer = QTimer(self)
        self._trim_blank_rows_timer.setSingleShot(True)
        self._trim_blank_rows_timer.timeout.connect(self.trim_entry_blank_rows)
        self.entry_grid.setItemDelegate(FormulaItemDelegate(self.entry_grid))
        self._cell_size_settings = QSettings("HMS QR", "Quan Ly QR")
        self._draft_save_timer = QTimer(self)
        self._draft_save_timer.setSingleShot(True)
        self._draft_save_timer.timeout.connect(self.save_entry_draft)
        self._entry_auto_save_timer = QTimer(self)
        self._entry_auto_save_timer.setSingleShot(True)
        self._entry_auto_save_timer.timeout.connect(self.save_completed_entry_rows)
        self._pending_entry_rows: set[int] = set()
        self._saving_entry_rows = False
        self._qr_copy_scale = int(self._cell_size_settings.value("worksheet/qr_copy_scale", 100))
        self._cell_size_defaults = self.load_cell_size_settings()
        self.entry_grid.set_column_character_limits(self._cell_size_defaults["column_chars"])
        for row in range(self.entry_grid.rowCount()):
            self.entry_grid.setRowHeight(row, self._cell_size_defaults["row_height"])
            for column in range(self.entry_grid.columnCount()):
                item = QTableWidgetItem()
                self.entry_grid._style_item(item, column)
                self.entry_grid.setItem(row, column, item)
        self.entry_grid.reset_history()
        self.status_grid = QTableWidget(self.entry_grid.rowCount(), 1)
        self.status_grid.setHorizontalHeaderLabels(["O\nTrạng thái S/P"])
        self.status_grid.setVerticalHeaderLabels(["" for _ in range(self.entry_grid.rowCount())])
        self.status_grid.setFixedWidth(145)
        self.status_grid.setColumnWidth(0, 125)
        self.status_grid.verticalHeader().setVisible(False)
        self.status_grid.horizontalHeader().setMinimumHeight(48)
        self.status_grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.status_grid.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.status_grid.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.status_grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.status_grid.setItemDelegate(FormulaItemDelegate(self.status_grid))
        self.entry_grid.setColumnHidden(ENTRY_HEADERS.index("Trạng thái S/P"), True)
        self.entry_grid.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.worksheet_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self.worksheet_scrollbar.setRange(
            self.entry_grid.verticalScrollBar().minimum(), self.entry_grid.verticalScrollBar().maximum(),
        )
        self.worksheet_scrollbar.setPageStep(self.entry_grid.verticalScrollBar().pageStep())
        self._syncing_worksheet_scroll = False
        self._entry_zoom_percent = 100
        self._entry_zoom_base_font = self.entry_grid.font()
        self._entry_zoom_base_widths = [self.entry_grid.columnWidth(column) for column in range(self.entry_grid.columnCount())]
        self._entry_zoom_base_heights = [self.entry_grid.rowHeight(row) for row in range(self.entry_grid.rowCount())]
        self.entry_grid._minimum_row_height = self._cell_size_defaults["row_height"]
        self.entry_grid.fit_all_row_heights()
        self.sync_frozen_status_column()

        add_entry_rows = QPushButton("Thêm 10 dòng")
        add_entry_rows.clicked.connect(self.add_entry_rows)
        save_entry_rows = QPushButton("Lưu các dòng nhập")
        save_entry_rows.clicked.connect(self.save_entry_rows)
        self.save_entry_action = QAction("Lưu các dòng nhập", self)
        self.save_entry_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_entry_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.save_entry_action.triggered.connect(self.save_entry_rows)
        self.addAction(self.save_entry_action)
        clear_entry_rows = QPushButton("Xóa vùng nhập")
        clear_entry_rows.clicked.connect(self.clear_entry_rows)
        copy_entry_rows = QPushButton("COPY VÙNG CHỌN")
        copy_entry_rows.clicked.connect(self.copy_selected_entry_rows)
        select_image = QPushButton("Chọn ảnh cho dòng")
        select_image.clicked.connect(self.select_entry_image)
        insert_row = QPushButton("+ Chèn dòng")
        insert_row.clicked.connect(self.entry_grid.insert_entry_row)
        delete_row = QPushButton("Xóa dòng")
        delete_row.clicked.connect(self.entry_grid.delete_selected_rows)
        move_row_up = QPushButton("↑ Dòng")
        move_row_up.clicked.connect(lambda: self.entry_grid.move_selected_row(-1))
        move_row_down = QPushButton("↓ Dòng")
        move_row_down.clicked.connect(lambda: self.entry_grid.move_selected_row(1))
        self.cell_address = QLabel("A1")
        self.cell_address.setMinimumWidth(58)
        self.cell_address.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formula_bar = QLineEdit()
        self.formula_bar.setPlaceholderText("Nhập giá trị cho ô đang chọn")
        attach_formula_completer(self.formula_bar)
        self.formula_bar.installEventFilter(self)
        self.formula_bar.returnPressed.connect(self.apply_formula_bar)
        self.formula_bar.textEdited.connect(self.begin_formula_edit)
        self._formula_edit_target: tuple[int, int] | None = None
        formula_layout = QHBoxLayout()
        formula_layout.addWidget(self.cell_address)
        formula_layout.addWidget(QLabel("fx"))
        formula_layout.addWidget(self.formula_bar, 1)
        bold = QPushButton("B")
        bold.setToolTip("In đậm ô đang chọn")
        bold.clicked.connect(lambda: self.format_selected_cells("bold"))
        italic = QPushButton("I")
        italic.setToolTip("In nghiêng ô đang chọn")
        italic.clicked.connect(lambda: self.format_selected_cells("italic"))
        underline = QPushButton("U⌄")
        underline.setToolTip("Gạch chân ô đang chọn")
        underline.clicked.connect(lambda: self.format_selected_cells("underline"))
        borders = QPushButton("▦⌄")
        borders.setToolTip("Kẻ đường viền cho các ô đang chọn")
        borders.clicked.connect(lambda: self.format_selected_cells("border"))
        highlight = QPushButton("🖍⌄")
        highlight.setToolTip("Chọn màu nền")
        highlight.clicked.connect(lambda: self.choose_cell_color("background"))
        font_color = QPushButton("A̲⌄")
        font_color.setToolTip("Chọn màu chữ")
        font_color.clicked.connect(lambda: self.choose_cell_color("foreground"))
        number_format = QComboBox()
        number_format.addItems(["General", "0", "0.00", "#,##0", "#,##0.00", "dd/MM/yyyy", "dd-MM-yyyy"])
        number_format.setToolTip("Định dạng số hoặc ngày cho ô đang chọn")
        number_format.activated.connect(self.format_selected_numbers)
        clear_format = QPushButton("⌫")
        clear_format.setToolTip("Xóa định dạng")
        clear_format.clicked.connect(lambda: self.format_selected_cells("clear"))
        auto_sum = QPushButton("Σ AutoSum")
        auto_sum.setToolTip("Chọn một vùng số trong cùng cột để chèn =SUM(...) bên dưới")
        auto_sum.clicked.connect(self.insert_auto_sum)
        cell_size = QPushButton("Kích thước ô")
        cell_size.setToolTip("Đặt độ rộng cột và chiều cao dòng mặc định")
        cell_size.clicked.connect(self.configure_cell_sizes)
        worksheet_toolbar = QHBoxLayout()
        for button in (bold, italic, underline, borders, highlight, font_color, number_format, clear_format, auto_sum, cell_size, insert_row, delete_row, move_row_up, move_row_down):
            button.setMinimumWidth(30)
            worksheet_toolbar.addWidget(button)
        worksheet_toolbar.addStretch(1)
        worksheet_toolbar.addWidget(QLabel("Căn giữa, tự ngắt dòng • Kích thước tự nới cột • Ctrl+C / Ctrl+V dữ liệu hoặc ảnh"))
        entry_actions = QHBoxLayout()
        entry_actions.addWidget(QLabel("NHẬP LIỆU KIỂU EXCEL: điền trực tiếp theo từng cột. Dòng có dữ liệu được tự lưu; Khách hàng và Số lượng có thể để trống."))
        entry_actions.addStretch(1)
        delivery_navigator = QVBoxLayout()
        delivery_navigator.setContentsMargins(0, 0, 0, 0)
        delivery_navigator.setSpacing(2)
        self.delivery_date_labels = {}
        self.delivery_date_editors = {}
        for unit, title in (("year", "NĂM"), ("month", "THÁNG"), ("day", "NGÀY")):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)
            title_label = QLabel(title)
            title_label.setFixedWidth(52)
            row.addWidget(title_label)
            previous = QPushButton("◀")
            previous.setToolTip(f"Lùi {title.lower()}")
            previous.setFixedSize(30, 26)
            previous.clicked.connect(lambda _checked=False, value=unit: self.change_entry_delivery_date(value, -1))
            row.addWidget(previous)
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(100)
            label.setToolTip(f"Double-click để nhập {title.lower()}")
            label.setProperty("delivery_date_unit", unit)
            label.installEventFilter(self)
            self.delivery_date_labels[unit] = label
            row.addWidget(label)
            following = QPushButton("▶")
            following.setToolTip(f"Tới {title.lower()}")
            following.setFixedSize(30, 26)
            following.clicked.connect(lambda _checked=False, value=unit: self.change_entry_delivery_date(value, 1))
            row.addWidget(following)
            row.addStretch(1)
            delivery_navigator.addLayout(row)
        self._update_entry_delivery_date_labels()
        body = QVBoxLayout()
        body.addLayout(entry_actions)
        body.addLayout(delivery_navigator)
        body.addLayout(worksheet_toolbar)
        body.addLayout(formula_layout)
        worksheet_area = QHBoxLayout()
        worksheet_area.setContentsMargins(0, 0, 0, 0)
        worksheet_area.setSpacing(0)
        worksheet_area.addWidget(self.entry_grid, 1)
        worksheet_area.addWidget(self.status_grid)
        worksheet_area.addWidget(self.worksheet_scrollbar)
        body.addLayout(worksheet_area, 1)
        zoom_out = QPushButton("−")
        zoom_out.setToolTip("Thu nhỏ worksheet")
        zoom_in = QPushButton("+")
        zoom_in.setToolTip("Phóng to worksheet")
        self.entry_zoom_label = QLabel("100%")
        self.entry_zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.entry_zoom_slider.setRange(60, 160)
        self.entry_zoom_slider.setValue(100)
        self.entry_zoom_slider.setFixedWidth(140)
        zoom_bar = QHBoxLayout()
        zoom_bar.addStretch(1)
        zoom_bar.addWidget(QLabel("Zoom"))
        zoom_bar.addWidget(zoom_out)
        zoom_bar.addWidget(self.entry_zoom_slider)
        zoom_bar.addWidget(zoom_in)
        zoom_bar.addWidget(self.entry_zoom_label)
        body.addLayout(zoom_bar)
        product_tab = QWidget()
        product_tab.setLayout(body)
        tabs = QTabWidget()
        tabs.addTab(product_tab, "SẢN PHẨM")
        tracking_tab = QWidget()
        tracking_layout = QVBoxLayout(tracking_tab)
        tracking_layout.addWidget(QLabel("Theo dõi tiến trình, QR, QC, đóng gói và giao hàng của sản phẩm."))
        tracking_layout.addWidget(self.product_result_count)
        tracking_layout.addWidget(self.table, 1)
        open_tracking = QPushButton("MỞ THEO DÕI TIẾN TRÌNH CHI TIẾT")
        open_tracking.clicked.connect(self.open_selected_product_tracking)
        open_tracking.setEnabled(bool(self.server_url and getattr(service, "access_token", "")))
        tracking_layout.addWidget(open_tracking)
        tabs.addTab(tracking_tab, "THEO DÕI TIẾN TRÌNH CHI TIẾT")
        if self.is_admin:
            tabs.addTab(self.admin_storage_panel, "CẤU HÌNH LƯU TRỮ")
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(tabs)
        self.setCentralWidget(container)
        self.connection_status = QLabel()
        self.connection_status.setObjectName("connectionStatus")
        self.desktop_version = QLabel(APP_VERSION)
        self.desktop_version.setObjectName("desktopVersion")
        self.check_connection_button = QPushButton("KIỂM TRA KẾT NỐI")
        self.check_connection_button.setObjectName("connectionCheckButton")
        self.check_connection_button.clicked.connect(self.check_server_connection)
        self.statusBar().addPermanentWidget(self.desktop_version)
        self.statusBar().addPermanentWidget(self.connection_status, 1)
        self.statusBar().addPermanentWidget(self.check_connection_button)
        self._set_connection_status("ĐÃ KẾT NỐI" if self.server_url else "CHẾ ĐỘ CỤC BỘ")
        if self.is_viewer:
            self._set_viewer_mode(
                add_entry_rows, save_entry_rows, clear_entry_rows, select_image, insert_row, delete_row, move_row_up, move_row_down,
            )
        self.entry_grid.currentCellChanged.connect(self.update_formula_bar)
        self.search.returnPressed.connect(self.refresh)
        self.filter_status.currentIndexChanged.connect(self.refresh)
        self.entry_grid.itemChanged.connect(self.update_formula_bar_from_item)
        self.entry_grid.itemChanged.connect(self.schedule_entry_save)
        self.entry_grid.itemClicked.connect(self.insert_formula_reference)
        self.entry_grid.formulaReferenceSelected.connect(self.insert_formula_reference_range)
        self.entry_grid.itemDoubleClicked.connect(self.handle_entry_grid_double_click)
        self.entry_grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.entry_grid.customContextMenuRequested.connect(self.show_qr_context_menu)
        self.entry_grid.itemChanged.connect(lambda _item: self.sync_frozen_status_column())
        self.entry_grid.historyRestored.connect(self.sync_frozen_status_column)
        self.entry_grid.formatRequested.connect(self.format_selected_cells)
        self.entry_grid.autoSumRequested.connect(self.insert_auto_sum)
        self.entry_grid.cellFormatRequested.connect(self.show_cell_format_dialog)
        self.entry_grid.columnCharacterWidthChanged.connect(self.update_configured_column_width)
        self.entry_grid.verticalScrollBar().valueChanged.connect(self.sync_worksheet_scrollbar)
        self.entry_grid.verticalScrollBar().valueChanged.connect(self.extend_entry_rows_at_scroll_end)
        self.worksheet_scrollbar.valueChanged.connect(self.scroll_worksheet)
        self.entry_grid.verticalHeader().sectionResized.connect(self.sync_frozen_status_row_height)
        self.status_grid.itemClicked.connect(self.select_status_from_frozen_column)
        self.entry_zoom_slider.valueChanged.connect(self.set_entry_zoom)
        self.entry_grid.zoomRequested.connect(self.adjust_entry_zoom)
        zoom_out.clicked.connect(lambda: self.entry_zoom_slider.setValue(max(60, self.entry_zoom_slider.value() - 10)))
        zoom_in.clicked.connect(lambda: self.entry_zoom_slider.setValue(min(160, self.entry_zoom_slider.value() + 10)))
        self.refresh()
        self._capture_latest_product_version()
        self._product_change_timer.start()
        self.load_entry_rows_for_selected_date()
        QTimer.singleShot(250, self.preload_adjacent_entry_dates)

    def _set_viewer_mode(self, *editing_controls: QWidget) -> None:
        for control in editing_controls:
            control.setEnabled(False)
        self.entry_grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.formula_bar.setReadOnly(True)
        self.save_entry_action.setEnabled(False)
        self.statusBar().showMessage("Chế độ chỉ xem: tài khoản VIEWER không thể thay đổi dữ liệu.", 10_000)

    def _set_connection_status(self, state: str) -> None:
        if self.server_url:
            account = f" · {self.actor} ({self.account_role})" if self.account_role else f" · {self.actor}"
            self.connection_status.setText(f"SERVER: {state} · {self.server_url}{account}")
        else:
            self.connection_status.setText(f"SERVER: {state}")

    def check_server_connection(self) -> None:
        if not self.server_url or not hasattr(self.service, "verify_server_readiness"):
            self._set_connection_status("CHẾ ĐỘ CỤC BỘ")
            self.statusBar().showMessage("Ứng dụng đang dùng dữ liệu cục bộ.", 5_000)
            return
        try:
            self.service.verify_server_readiness()
        except Exception:
            self._set_connection_status("KHÔNG KẾT NỐI")
            self.statusBar().showMessage("Không thể kết nối HMS QR Server. Kiểm tra mạng LAN và Máy 1.", 8_000)
            return
        self._set_connection_status("ĐÃ KẾT NỐI")
        self.statusBar().showMessage("HMS QR Server sẵn sàng.", 5_000)

    def copy_to_excel(self) -> None:
        rows = self.model.page.items
        if not rows:
            QMessageBox.information(self, "Thông báo", "Không có sản phẩm nào để copy.")
            return
        headers = ["Mã sản phẩm", "Công ty", "Tên chi tiết", "Số lượng", "Đơn vị", "Vật liệu", "Trạng thái"]
        tsv_lines = ["\t".join(headers)]
        for p in rows:
            tsv_lines.append("\t".join([
                p.product_code, p.company, p.part_name, format_quantity(p.quantity), p.unit, p.material or "", STATUS_LABELS.get(p.status, str(p.status))
            ]))
        QApplication.clipboard().setText("\r\n".join(tsv_lines))
        QMessageBox.information(self, "Đã sao chép", f"Đã copy {len(rows)} sản phẩm vào Clipboard!\nBạn có thể mở Excel và bấm Ctrl+V.")

    def open_selected_product_tracking(self) -> None:
        row = self.table.currentIndex().row()
        if row < 0 or row >= len(self.model.page.items):
            QMessageBox.information(self, "Theo dõi sản phẩm", "Chọn một sản phẩm trước khi mở Tracking.")
            return
        product = self.model.page.items[row]
        try:
            client = TrackingApiClient(self.server_url, access_token=self.service.access_token)
            summaries = client.list_tracking(search=product.product_code)
        except Exception as exc:
            QMessageBox.warning(self, "Không thể mở Tracking", str(exc))
            return
        self.tracking_window = TrackingWindow(summary_rows=summaries)
        self.tracking_window.setWindowTitle(f"HMS QR — Tracking: {product.product_code}")
        self.tracking_window.show()

    def open_stage2(self) -> None:
        self.stage2_window = Stage2Window(
            Stage2ApiClient(self.server_url, access_token=self.service.access_token),
            role=self.account_role,
        )
        self.stage2_window.show()

    def configure_cell_sizes(self) -> None:
        dialog = SpreadsheetSizeDialog(self._cell_size_defaults, DEFAULT_CELL_SIZE_SETTINGS, self)
        dialog.settingsApplied.connect(self.apply_cell_size_settings)
        dialog.exec()

    def load_cell_size_settings(self) -> dict[str, object]:
        saved = self._cell_size_settings.value("worksheet/cell_sizes")
        if saved:
            try:
                loaded = json.loads(saved)
                if set(loaded.get("column_chars", {})) == set(ENTRY_HEADERS):
                    return loaded
            except (TypeError, ValueError):
                pass
        return {
            "column_chars": dict(DEFAULT_CELL_SIZE_SETTINGS["column_chars"]),
            "row_height": DEFAULT_CELL_SIZE_SETTINGS["row_height"],
        }

    def apply_cell_size_settings(self, settings: dict[str, object]) -> None:
        self._cell_size_defaults = {
            "column_chars": dict(settings["column_chars"]),
            "row_height": settings["row_height"],
        }
        self.save_cell_size_settings()
        self.apply_default_cell_sizes()

    def update_configured_column_width(self, column: int, characters: int) -> None:
        if 0 <= column < len(ENTRY_HEADERS):
            self._cell_size_defaults["column_chars"][ENTRY_HEADERS[column]] = characters
            self.save_cell_size_settings()

    def save_cell_size_settings(self) -> None:
        self._cell_size_settings.setValue("worksheet/cell_sizes", json.dumps(self._cell_size_defaults, ensure_ascii=True))
        self._cell_size_settings.sync()

    def apply_default_cell_sizes(self) -> None:
        self.entry_grid.set_column_character_limits(self._cell_size_defaults["column_chars"])
        self.entry_grid._minimum_row_height = self._cell_size_defaults["row_height"]
        for row in range(self.entry_grid.rowCount()):
            self.entry_grid.setRowHeight(row, self._cell_size_defaults["row_height"])
        self.sync_frozen_status_column()

    def open_column_filter(self, column: int) -> None:
        values = sorted({(self.entry_grid.item(row, column).text() if self.entry_grid.item(row, column) else "")
                         for row in range(self.entry_grid.rowCount())})
        dialog = SpreadsheetFilterDialog(ENTRY_HEADERS[column], values, self._column_filters.get(column), self)
        if not dialog.exec():
            return
        if dialog._cleared:
            self._column_filters.pop(column, None)
        elif dialog.sort_order is not None:
            self.sort_entry_grid(column, dialog.sort_order)
        else:
            self._column_filters[column] = dialog.selected_values()
        self.apply_column_filters()

    def sort_entry_grid(self, column: int, order: Qt.SortOrder) -> None:
        rows = [[self.entry_grid.takeItem(row, current_column)
                 for current_column in range(self.entry_grid.columnCount())]
                for row in range(self.entry_grid.rowCount())]
        populated = [items for items in rows if any(item and item.text().strip() for item in items)]
        empty = [items for items in rows if not any(item and item.text().strip() for item in items)]

        def sort_key(items: list[QTableWidgetItem | None]) -> tuple[int, object]:
            item = items[column]
            value = self.entry_grid.value_for_item(item) if item else ""
            # Formula cells sort by their calculated result, not the formula source.
            if item and self.entry_grid.formula_for_item(item).startswith("="):
                value = item.text()
            try:
                return 0, Decimal(value.replace(",", ""))
            except InvalidOperation:
                pass
            try:
                return 1, date.fromisoformat(value)
            except ValueError:
                return 2, value.casefold()

        populated.sort(
            key=sort_key,
            reverse=order == Qt.SortOrder.DescendingOrder,
        )
        for row, items in enumerate(populated + empty):
            for current_column, item in enumerate(items):
                self.entry_grid.setItem(row, current_column, item)
        self.apply_column_filters()
        self.sync_frozen_status_column()

    def apply_column_filters(self) -> None:
        for row in range(self.entry_grid.rowCount()):
            visible = True
            for column, allowed in self._column_filters.items():
                item = self.entry_grid.item(row, column)
                value = item.text() if item else ""
                if value not in allowed:
                    visible = False
                    break
            self.entry_grid.setRowHidden(row, not visible)
        self.sync_frozen_status_column()

    def _update_entry_delivery_date_labels(self) -> None:
        selected = self.selected_delivery_date
        for editor in self.delivery_date_editors.values():
            editor.hide()
        self.delivery_date_labels["year"].setText(str(selected.year))
        self.delivery_date_labels["month"].setText(f"THÁNG {selected.month}")
        self.delivery_date_labels["day"].setText(str(selected.day))

    def change_entry_delivery_date(self, unit: str, step: int) -> None:
        self.save_entry_draft()
        selected = self.selected_delivery_date
        if unit == "year":
            year = selected.year + step
            self.selected_delivery_date = selected.replace(year=year, day=min(selected.day, monthrange(year, selected.month)[1]))
        elif unit == "month":
            month_index = selected.year * 12 + selected.month - 1 + step
            year, month = divmod(month_index, 12)
            self.selected_delivery_date = selected.replace(year=year, month=month + 1, day=min(selected.day, monthrange(year, month + 1)[1]))
        else:
            self.selected_delivery_date = date.fromordinal(selected.toordinal() + step)
        self._update_entry_delivery_date_labels()
        self.load_entry_rows_for_selected_date()

    def eventFilter(self, watched, event) -> bool:
        if (watched is self.formula_bar and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape and self.cancel_formula_bar_edit()):
            return True
        if (watched is self.formula_bar and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_F4 and cycle_formula_reference_lock(self.formula_bar)):
            return True
        unit = watched.property("delivery_date_unit") if isinstance(watched, QLabel) else None
        if unit and event.type() == QEvent.Type.MouseButtonDblClick:
            self._edit_entry_delivery_date(unit)
            return True
        return super().eventFilter(watched, event)

    def _edit_entry_delivery_date(self, unit: str) -> None:
        """Replace a date label with a focused numeric editor at the same position."""
        selected = self.selected_delivery_date
        label = self.delivery_date_labels[unit]
        editor = self.delivery_date_editors.get(unit)
        if editor is None:
            editor = QSpinBox(label.parentWidget())
            editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            editor.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            editor.editingFinished.connect(lambda value=unit: self._commit_entry_delivery_date(value))
            self.delivery_date_editors[unit] = editor
        editor.setRange(2000 if unit == "year" else 1, 9999 if unit == "year" else (12 if unit == "month" else monthrange(selected.year, selected.month)[1]))
        editor.setValue(getattr(selected, unit))
        editor.setGeometry(label.geometry())
        editor.show()
        editor.raise_()
        editor.setFocus()
        editor.selectAll()

    def _commit_entry_delivery_date(self, unit: str) -> None:
        editor = self.delivery_date_editors[unit]
        selected = self.selected_delivery_date
        value = editor.value()
        if unit == "year":
            self.selected_delivery_date = selected.replace(year=value, day=min(selected.day, monthrange(value, selected.month)[1]))
        elif unit == "month":
            self.selected_delivery_date = selected.replace(month=value, day=min(selected.day, monthrange(selected.year, value)[1]))
        else:
            self.selected_delivery_date = selected.replace(day=value)
        self._update_entry_delivery_date_labels()
        self.load_entry_rows_for_selected_date()
        QTimer.singleShot(0, self.preload_adjacent_entry_dates)

    def _entry_draft_key(self) -> str:
        return f"worksheet/drafts/{self.selected_delivery_date.isoformat()}"

    def schedule_entry_draft_save(self) -> None:
        # Keep incomplete spreadsheet rows when users navigate away without saving.
        self._draft_save_timer.start(500)

    def schedule_entry_save(self, item: QTableWidgetItem) -> None:
        self.schedule_entry_draft_save()
        if self._saving_entry_rows:
            return
        self._pending_entry_rows.add(item.row())
        self._entry_auto_save_timer.start(600)

    def save_completed_entry_rows(self) -> None:
        rows = sorted(self._pending_entry_rows)
        self._pending_entry_rows.clear()
        self.save_entry_rows(rows=rows, interactive=False)

    def save_entry_draft(self) -> None:
        rows = []
        generated_headers = {"Mã QR", "Mã sản phẩm"}
        for row in range(self.entry_grid.rowCount()):
            cells = {}
            for column, header in enumerate(ENTRY_HEADERS):
                if header in generated_headers:
                    continue
                item = self.entry_grid.item(row, column)
                if item is None:
                    continue
                image = item.data(Qt.ItemDataRole.UserRole) if header == "Ảnh sản phẩm" else None
                internal_id = item.data(Qt.ItemDataRole.UserRole + 30) if column == 0 else None
                raw_value = self.entry_grid.value_for_item(item)
                display_format = item.data(self.entry_grid.DISPLAY_FORMAT_ROLE)
                if raw_value or image or internal_id:
                    cells[header] = {
                        "text": raw_value,
                        "display_format": display_format,
                        "image": base64.b64encode(bytes(image)).decode("ascii") if image else None,
                        "internal_id": str(internal_id) if internal_id else None,
                    }
            if cells:
                rows.append({"row": row, "cells": cells})
        if rows:
            self._cell_size_settings.setValue(self._entry_draft_key(), json.dumps(rows, ensure_ascii=True))
        else:
            self._cell_size_settings.remove(self._entry_draft_key())
        self._cell_size_settings.sync()

    def _load_entry_draft(self) -> list[dict[str, object]]:
        saved = self._cell_size_settings.value(self._entry_draft_key())
        if not saved:
            return []
        try:
            draft = json.loads(saved)
            return draft if isinstance(draft, list) else []
        except (TypeError, ValueError):
            return []

    @staticmethod
    def _normalize_draft_quantity(value: object) -> str:
        """Migrate old worksheet drafts that saved Decimal values as 1.0000."""
        text = str(value or "").strip()
        if not text or text.startswith("="):
            return text
        try:
            return format_quantity(Decimal(text))
        except Exception:
            return text

    def _products_for_entry_date(self, delivery_date: date):
        month = (delivery_date.year, delivery_date.month)
        if self._entry_products_month == month:
            return self._entry_products_by_date.get(delivery_date, [])
        products_by_date: dict[date, list] = {}
        month_end = date(delivery_date.year + (delivery_date.month == 12), delivery_date.month % 12 + 1, 1)
        page = 1
        while True:
            result = self.service.list_products(
                page=page,
                page_size=200,
                sort_by="product_code",
                descending=False,
                delivery_start=date(delivery_date.year, delivery_date.month, 1),
                delivery_end=month_end,
            )
            for product in result.items:
                if product.delivery_schedule:
                    products_by_date.setdefault(product.delivery_schedule, []).append(product)
            if page * result.page_size >= result.total:
                self._entry_products_by_date = products_by_date
                self._entry_products_month = month
                return products_by_date.get(delivery_date, [])
            page += 1

    def preload_adjacent_entry_dates(self) -> None:
        """Load and index the entire visible month before date navigation."""
        self._products_for_entry_date(self.selected_delivery_date)

    def load_entry_rows_for_selected_date(self) -> None:
        """Replace the worksheet with the selected date's saved products and draft cells."""
        draft = self._load_entry_draft()
        products = self._products_for_entry_date(self.selected_delivery_date)
        self.entry_grid._preview_product_codes.clear()
        row_count = max(12, (max((int(row["row"]) for row in draft), default=-1) + 10) if draft else len(products) + 10)
        self.entry_grid.setUpdatesEnabled(False)
        self.status_grid.setUpdatesEnabled(False)
        product_rows: dict[object, int] = {}
        self.entry_grid.setRowCount(row_count)
        self.entry_grid.setVerticalHeaderLabels([str(row + 1) for row in range(row_count)])
        self.entry_grid.blockSignals(True)
        try:
            for row in range(row_count):
                for column in range(self.entry_grid.columnCount()):
                    item = QTableWidgetItem()
                    self.entry_grid._style_item(item, column)
                    self.entry_grid.setItem(row, column, item)
            if draft:
                products_by_id = {str(product.internal_id): product for product in products}
                for draft_row in draft:
                    row = int(draft_row["row"])
                    for header, saved_cell in draft_row["cells"].items():
                        item = self.entry_grid.item(row, ENTRY_HEADERS.index(header))
                        text = saved_cell.get("text", "")
                        item.setText(self._normalize_draft_quantity(text) if header == "Số lượng" else text)
                        if saved_cell.get("display_format"):
                            self.entry_grid.apply_display_format(item, saved_cell["display_format"])
                        if saved_cell.get("image"):
                            item.setData(Qt.ItemDataRole.UserRole, base64.b64decode(saved_cell["image"]))
                        if saved_cell.get("internal_id"):
                            item.setData(Qt.ItemDataRole.UserRole + 30, saved_cell["internal_id"])
                    saved_id = self.entry_grid.item(row, 0).data(Qt.ItemDataRole.UserRole + 30)
                    product = products_by_id.get(str(saved_id)) if saved_id else None
                    if product:
                        product_rows[product.internal_id] = row
                        dimensions = (product.size or "").split(" x ", 2)
                        dimensions.extend([""] * (3 - len(dimensions)))
                        for header, dimension in zip(
                            ("Kích thước X", "Kích thước Y", "Kích thước Z"), dimensions
                        ):
                            self.entry_grid.item(row, ENTRY_HEADERS.index(header)).setText(dimension)
                        qr_item = self.entry_grid.item(row, ENTRY_HEADERS.index("Mã QR"))
                        code_item = self.entry_grid.item(row, ENTRY_HEADERS.index("Mã sản phẩm"))
                        code_item.setText(product.product_code)
                        qr_item.setText(product_qr_value(product.product_code, product.company))
                        qr_item.setData(Qt.ItemDataRole.UserRole + 21, None)
            else:
                for row, product in enumerate(products):
                    product_rows[product.internal_id] = row
                    dimensions = (product.size or "").split(" x ", 2)
                    dimensions.extend([""] * (3 - len(dimensions)))
                    values = {
                        "Khách hàng": product.company,
                        "Tên sản phẩm": product.part_name,
                        "Số lượng": "" if product.quantity == 0 else format_quantity(product.quantity),
                        "Đơn vị": product.unit,
                        "Vật liệu": product.material or "",
                        "Người đặt": product.requester or "",
                        "Xử lý bề mặt": product.surface_treatment or "",
                        "Đặt ngoài": product.outsourced_company or ("Có" if product.outsourced else ""),
                        "Kích thước X": dimensions[0],
                        "Kích thước Y": dimensions[1],
                        "Kích thước Z": dimensions[2],
                        "Ghi chú": product.notes or "",
                        "Mã QR": product_qr_value(product.product_code, product.company),
                        "Mã sản phẩm": product.product_code,
                        "Trạng thái S/P": STATUS_LABELS[product.status],
                    }
                    for header, value in values.items():
                        item = self.entry_grid.item(row, ENTRY_HEADERS.index(header))
                        item.setText(value)
                    self.entry_grid.item(row, 0).setData(Qt.ItemDataRole.UserRole + 30, str(product.internal_id))
        finally:
            self.entry_grid.blockSignals(False)
        try:
            self.load_entry_image_thumbnails(product_rows)
        finally:
            self.entry_grid.setUpdatesEnabled(True)
            self.status_grid.setUpdatesEnabled(True)
        for row in range(row_count):
            self.entry_grid.setRowHeight(row, self.entry_grid._minimum_row_height)
        self.entry_grid.reset_history()
        self.apply_column_filters()
        self.sync_frozen_status_column()
        if draft:
            # Persist the migrated display values so future opens remain clean.
            self.save_entry_draft()

    def load_entry_image_thumbnails(self, product_rows: dict[object, int]) -> None:
        """Load only the visible date's primary images as small worksheet thumbnails."""
        files = self.files_panel.managed_service
        if files is None:
            return
        image_column = ENTRY_HEADERS.index("Ảnh sản phẩm")
        for product_id, row in product_rows.items():
            try:
                if hasattr(files, "list_images"):
                    images = files.list_images(product_id)
                    primary = next((image for image in images if image["is_primary"]), images[0] if images else None)
                    content = files.download(UUID(primary["file_id"])) if primary else None
                    filename = primary["original_filename"] if primary else ""
                    file_id = primary["file_id"] if primary else ""
                else:
                    images = files.repository.list_images(product_id)
                    primary = next((image for image in images if image.relation.is_primary), images[0] if images else None)
                    content = files.read(primary.managed_file.file_id) if primary else None
                    filename = primary.managed_file.original_filename if primary else ""
                    file_id = str(primary.managed_file.file_id) if primary else ""
                if primary is None:
                    continue
                image = QImage()
                if not image.loadFromData(content):
                    continue
                thumbnail = image.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                encoded = QByteArray()
                buffer = QBuffer(encoded)
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                thumbnail.save(buffer, "PNG", 85)
                item = self.entry_grid.item(row, image_column)
                item.setText(filename)
                item.setData(Qt.ItemDataRole.UserRole, bytes(encoded))
                item.setData(Qt.ItemDataRole.UserRole + 31, file_id)
            except Exception:
                # A missing archived file must not block the rest of the worksheet.
                continue

    def closeEvent(self, event) -> None:
        self.save_entry_draft()
        for timer in (
            self._product_change_timer,
            self._trim_blank_rows_timer,
            self._draft_save_timer,
            self._entry_auto_save_timer,
        ):
            timer.stop()
        super().closeEvent(event)

    def sync_frozen_status_column(self) -> None:
        """Mirror the status column in a fixed right-hand table."""
        status_column = ENTRY_HEADERS.index("Trạng thái S/P")
        self.status_grid.setRowCount(self.entry_grid.rowCount())
        for row in range(self.entry_grid.rowCount()):
            source = self.entry_grid.item(row, status_column)
            text = source.text() if source else ""
            item = self.status_grid.item(row, 0)
            is_new = item is None
            if item is None:
                item = QTableWidgetItem()
            item.setText(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setBackground(QColor(STATUS_COLORS.get(text.strip(), "transparent")))
            if is_new:
                self.status_grid.setItem(row, 0, item)
            self.status_grid.setRowHeight(row, self.entry_grid.rowHeight(row))
            self.status_grid.setRowHidden(row, self.entry_grid.isRowHidden(row))
        bar = self.entry_grid.verticalScrollBar()
        self.worksheet_scrollbar.setRange(bar.minimum(), bar.maximum())
        self.worksheet_scrollbar.setPageStep(bar.pageStep())
        self.worksheet_scrollbar.setValue(bar.value())

    def sync_frozen_status_row_height(self, row: int, _old_height: int, new_height: int) -> None:
        if row < self.status_grid.rowCount():
            self.status_grid.setRowHeight(row, new_height)

    def sync_worksheet_scrollbar(self, value: int) -> None:
        if self._syncing_worksheet_scroll:
            return
        self._syncing_worksheet_scroll = True
        try:
            self.status_grid.verticalScrollBar().setValue(value)
            self.worksheet_scrollbar.setValue(value)
        finally:
            self._syncing_worksheet_scroll = False

    def extend_entry_rows_at_scroll_end(self, value: int) -> None:
        """Append blank worksheet rows only after the user reaches the current bottom."""
        bar = self.entry_grid.verticalScrollBar()
        if bar.maximum() > bar.minimum() and value >= bar.maximum():
            self.add_entry_rows(count=20, record_history=False)
        elif value <= bar.minimum():
            # Delay the trim until the drag settles so scrolling remains smooth.
            self._trim_blank_rows_timer.start(120)

    def trim_entry_blank_rows(self) -> None:
        """Discard unused rows below the final entered row after returning to the top."""
        bar = self.entry_grid.verticalScrollBar()
        if bar.value() > bar.minimum():
            return
        last_used = -1
        generated_headers = {"Mã QR", "Mã sản phẩm", "Trạng thái S/P"}
        for row in range(self.entry_grid.rowCount()):
            if any(
                self.entry_grid.item(row, column)
                and self.entry_grid.item(row, column).text().strip()
                for column, header in enumerate(ENTRY_HEADERS)
                if header not in generated_headers
            ):
                last_used = row
        target_rows = max(12, last_used + 11)
        if target_rows >= self.entry_grid.rowCount():
            return
        self.entry_grid.setUpdatesEnabled(False)
        try:
            self.entry_grid.setRowCount(target_rows)
            self.status_grid.setRowCount(target_rows)
        finally:
            self.entry_grid.setUpdatesEnabled(True)
        self.sync_frozen_status_column()

    def scroll_worksheet(self, value: int) -> None:
        if self._syncing_worksheet_scroll:
            return
        self._syncing_worksheet_scroll = True
        try:
            self.entry_grid.verticalScrollBar().setValue(value)
            self.status_grid.verticalScrollBar().setValue(value)
        finally:
            self._syncing_worksheet_scroll = False

    def set_entry_zoom(self, percent: int) -> None:
        """Scale worksheet display while preserving the underlying cell-size settings."""
        self._entry_zoom_percent = percent
        factor = percent / 100
        font = QFont(self._entry_zoom_base_font)
        font.setPointSizeF(max(6, self._entry_zoom_base_font.pointSizeF() * factor))
        self.entry_grid._applying_zoom = True
        try:
            for grid in (self.entry_grid, self.status_grid):
                grid.setFont(font)
                grid.horizontalHeader().setFont(font)
            metrics = QFontMetrics(self._entry_zoom_base_font)
            for column, header in enumerate(ENTRY_HEADERS):
                base_width = metrics.horizontalAdvance("0" * self._cell_size_defaults["column_chars"][header]) + 24
                self.entry_grid.setColumnWidth(column, max(40, round(base_width * factor)))
            self.status_grid.setFixedWidth(max(100, round(145 * factor)))
            self.status_grid.setColumnWidth(0, max(80, round(125 * factor)))
            base_height = self._cell_size_defaults["row_height"]
            self.entry_grid._minimum_row_height = max(22, round(base_height * factor))
            for row in range(self.entry_grid.rowCount()):
                self.entry_grid.setRowHeight(row, self.entry_grid._minimum_row_height)
        finally:
            self.entry_grid._applying_zoom = False
        self.entry_zoom_label.setText(f"{percent}%")
        self.sync_frozen_status_column()

    def adjust_entry_zoom(self, delta: int) -> None:
        self.entry_zoom_slider.setValue(
            max(self.entry_zoom_slider.minimum(), min(self.entry_zoom_slider.maximum(), self.entry_zoom_slider.value() + delta))
        )

    def select_status_from_frozen_column(self, item: QTableWidgetItem) -> None:
        self.entry_grid.setCurrentCell(item.row(), ENTRY_HEADERS.index("Trạng thái S/P"))

    def open_product_image(self, item: QTableWidgetItem) -> None:
        if item.column() != ENTRY_HEADERS.index("Ảnh sản phẩm"):
            return
        png = item.data(Qt.ItemDataRole.UserRole)
        if not png:
            return
        source_file_id = item.data(Qt.ItemDataRole.UserRole + 31)
        if source_file_id and self.files_panel.managed_service is not None:
            try:
                png = self.files_panel.managed_service.read(UUID(str(source_file_id)))
            except (FileNotFoundError, ValueError):
                # Unsaved pasted images and unavailable archived files still open
                # from their worksheet thumbnail.
                pass
        viewer = ProductImageViewer(bytes(png), self)
        viewer.exec()

    def handle_entry_grid_double_click(self, item: QTableWidgetItem) -> None:
        if item.column() == ENTRY_HEADERS.index("Mã QR"):
            self.copy_qr_label(item)
            return
        self.open_product_image(item)

    def ensure_qr_label(self, item: QTableWidgetItem) -> bytes | None:
        """Create the costly print-quality QR label only when the user requests it."""
        png = item.data(Qt.ItemDataRole.UserRole + 21)
        if png:
            return bytes(png)
        row = item.row()
        code_item = self.entry_grid.item(row, ENTRY_HEADERS.index("Mã sản phẩm"))
        part_item = self.entry_grid.item(row, ENTRY_HEADERS.index("Tên sản phẩm"))
        code = code_item.text().strip() if code_item else ""
        if not item.text().strip() or not code:
            return None
        dimensions = format_dimensions([
            self.entry_grid.item(row, ENTRY_HEADERS.index(header)).text().strip()
            for header in ("Kích thước X", "Kích thước Y", "Kích thước Z")
            if self.entry_grid.item(row, ENTRY_HEADERS.index(header))
            and self.entry_grid.item(row, ENTRY_HEADERS.index(header)).text().strip()
        ])
        png = product_qr_label_png(
            item.text(), code, part_item.text().strip() if part_item else "", dimensions,
            self.selected_delivery_date,
        )
        item.setData(Qt.ItemDataRole.UserRole + 21, png)
        return png

    def copy_qr_label(self, item: QTableWidgetItem) -> None:
        png = self.ensure_qr_label(item)
        if not png:
            return
        label = QImage()
        if not label.loadFromData(bytes(png), "PNG"):
            return
        # Excel pastes clipboard bitmaps by pixel count. A dedicated 300-DPI copy is
        # sharp at 50 x 30 mm but avoids the slow, oversized 1500-DPI bitmap path.
        copy_width = max(1, round(591 * self._qr_copy_scale / 100))
        copy_height = max(1, round(354 * self._qr_copy_scale / 100))
        label = label.scaled(copy_width, copy_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        copy_dots_per_meter = round(300 / 0.0254)
        label.setDotsPerMeterX(copy_dots_per_meter)
        label.setDotsPerMeterY(copy_dots_per_meter)
        encoded = QByteArray()
        buffer = QBuffer(encoded)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        label.save(buffer, "PNG", 100)
        width_points = 50 * self._qr_copy_scale / 100 / 25.4 * 72
        height_points = 30 * self._qr_copy_scale / 100 / 25.4 * 72
        mime = QMimeData()
        mime.setImageData(label)
        # Excel honors the physical CSS dimensions from HTML, unlike raw bitmap pixels on its clipboard.
        mime.setHtml(
            f'<img src="data:image/png;base64,{base64.b64encode(bytes(encoded)).decode("ascii")}" '
            f'style="width:{width_points:.2f}pt;height:{height_points:.2f}pt" '
            f'width="{round(width_points / 72 * 96)}" height="{round(height_points / 72 * 96)}">'
        )
        QApplication.clipboard().setMimeData(mime)
        # The QR payload and lightweight preview remain visible; discard the large
        # print label so copied rows do not accumulate 1500-DPI images in memory.
        item.setData(Qt.ItemDataRole.UserRole + 21, None)
        self.show_qr_copy_confirmation()

    def show_qr_copy_confirmation(self) -> None:
        message = QLabel(f"Đã copy tem QR ({self._qr_copy_scale}%)", self.entry_grid.viewport())
        message.setStyleSheet(
            "QLabel { background: #147a69; color: white; border: 1px solid #0f5b4e; "
            "border-radius: 5px; font-weight: bold; padding: 8px 12px; }"
        )
        message.adjustSize()
        viewport = self.entry_grid.viewport()
        message.move(max(8, viewport.width() - message.width() - 14), max(8, viewport.height() - message.height() - 14))
        message.show()
        QTimer.singleShot(1000, message.deleteLater)

    def show_qr_context_menu(self, point: QPoint) -> None:
        item = self.entry_grid.itemAt(point)
        if not item or item.column() != ENTRY_HEADERS.index("Mã QR") or not item.text().strip():
            return
        menu = QMenu(self.entry_grid)
        copy = menu.addAction("Copy QR")
        view = menu.addAction("Xem")
        scale = menu.addAction("Cài đặt tỉ lệ copy")
        chosen = menu.exec(self.entry_grid.viewport().mapToGlobal(point))
        if chosen == copy:
            self.copy_qr_label(item)
        elif chosen == view:
            png = self.ensure_qr_label(item)
            if png:
                ProductImageViewer(png, self).exec()
        elif chosen == scale:
            self.set_qr_copy_scale()

    def set_qr_copy_scale(self) -> None:
        scale, accepted = QInputDialog.getInt(
            self,
            "Cài đặt tỉ lệ copy QR",
            "Tỉ lệ ảnh dán vào Excel (%):",
            self._qr_copy_scale,
            25,
            300,
            5,
        )
        if accepted:
            self._qr_copy_scale = scale
            self._cell_size_settings.setValue("worksheet/qr_copy_scale", scale)

    def paste_from_excel(self) -> None:
        text = QApplication.clipboard().text()
        if not text.strip():
            QMessageBox.warning(self, "Clipboard rỗng", "Vui lòng copy các dòng trong Excel (Ctrl+C) trước khi dán.")
            return
        from packages.excel.factory_adapter import parse_factory_tsv
        items = parse_factory_tsv(text)
        if not items:
            QMessageBox.warning(self, "Không đọc được", "Không nhận diện được dòng chi tiết hợp lệ trong nội dung dán.")
            return
        reply = QMessageBox.question(
            self, "Xác nhận nhập",
            f"Tìm thấy {len(items)} chi tiết từ Excel.\nBạn có muốn nạp các chi tiết này vào danh mục sản phẩm không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            imported = 0
            for it in items:
                try:
                    self.service.create_product(
                        actor=self.actor,
                        company=it["company"],
                        part_name=it["part_name"],
                        quantity=Decimal(str(it["quantity"])),
                        unit=it["unit"],
                        material=it.get("material") or None,
                        surface_treatment=it.get("surface_treatment") or None,
                        size=it.get("size") or None,
                        notes=it.get("notes") or None,
                    )
                    imported += 1
                except Exception:
                    pass
            self.refresh()
            QMessageBox.information(self, "Hoàn tất", f"Đã nhập thành công {imported}/{len(items)} sản phẩm từ Excel!")

    def _select_product_files(self, *_args) -> None:
        row = self.table.currentIndex().row()
        product_id = self.model.page.items[row].internal_id if row >= 0 else None
        self.files_panel.set_product(product_id)

    def add_entry_rows(self, count: int = 10, record_history: bool = True) -> None:
        if record_history:
            self.entry_grid._begin_history_transaction()
        start = self.entry_grid.rowCount()
        self.entry_grid.setRowCount(start + count)
        self.entry_grid.blockSignals(True)
        try:
            for row in range(start, start + count):
                self.entry_grid.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
                self.entry_grid.setRowHeight(row, self.entry_grid._minimum_row_height)
                for column in range(self.entry_grid.columnCount()):
                    item = QTableWidgetItem()
                    self.entry_grid._style_item(item, column)
                    self.entry_grid.setItem(row, column, item)
        finally:
            self.entry_grid.blockSignals(False)
        self.sync_frozen_status_column()
        if record_history:
            self.entry_grid._commit_history_transaction()

    def clear_entry_rows(self) -> None:
        self.entry_grid._begin_history_transaction()
        self.entry_grid.clearContents()
        for row in range(self.entry_grid.rowCount()):
            for column in range(self.entry_grid.columnCount()):
                item = QTableWidgetItem()
                self.entry_grid._style_item(item, column)
                self.entry_grid.setItem(row, column, item)
        self.sync_frozen_status_column()
        self.entry_grid._commit_history_transaction()

    @staticmethod
    def _excel_column_name(column: int) -> str:
        name = ""
        while True:
            name = chr(ord("A") + column % 26) + name
            column = column // 26 - 1
            if column < 0:
                return name

    def update_formula_bar(self, row: int, column: int, *_args) -> None:
        if row < 0 or column < 0:
            return
        self.cell_address.setText(f"{self._excel_column_name(column)}{row + 1}")
        if self._formula_edit_target is not None:
            return
        item = self.entry_grid.item(row, column)
        self.formula_bar.setText(self.entry_grid.value_for_item(item))

    def update_formula_bar_from_item(self, item: QTableWidgetItem) -> None:
        if item.row() == self.entry_grid.currentRow() and item.column() == self.entry_grid.currentColumn():
            self.formula_bar.setText(self.entry_grid.value_for_item(item))

    def begin_formula_edit(self, text: str) -> None:
        if text.startswith("="):
            row, column = self.entry_grid.currentRow(), self.entry_grid.currentColumn()
            self._formula_edit_target = (max(row, 0), max(column, 0))
        else:
            self._formula_edit_target = None
        self.entry_grid.formula_reference_mode = self._formula_edit_target is not None

    def cancel_formula_bar_edit(self) -> bool:
        """Discard a pending formula-bar edit and leave the worksheet unchanged."""
        if self._formula_edit_target is None:
            return False
        row, column = self._formula_edit_target
        self._formula_edit_target = None
        self.entry_grid.formula_reference_mode = False
        self.entry_grid._formula_reference_drag_origin = None
        self.entry_grid.setCurrentCell(row, column)
        self.update_formula_bar(row, column)
        return True

    def insert_formula_reference(self, _item: QTableWidgetItem) -> None:
        if self._formula_edit_target is None or not self.formula_bar.text().startswith("="):
            return
        selected = self.entry_grid.selectedIndexes()
        rows = [index.row() for index in selected]
        columns = [index.column() for index in selected]
        if not rows or not columns:
            return
        start = f"{self._excel_column_name(min(columns))}{min(rows) + 1}"
        end = f"{self._excel_column_name(max(columns))}{max(rows) + 1}"
        reference = start if start == end else f"{start}:{end}"
        self.formula_bar.setText(f"{self.formula_bar.text()}{reference}")
        self.formula_bar.setCursorPosition(len(self.formula_bar.text()))

    def insert_formula_reference_range(self, start_row: int, start_column: int, end_row: int, end_column: int) -> None:
        if self._formula_edit_target is None or not self.formula_bar.text().startswith("="):
            return
        start = f"{self._excel_column_name(min(start_column, end_column))}{min(start_row, end_row) + 1}"
        end = f"{self._excel_column_name(max(start_column, end_column))}{max(end_row, start_row) + 1}"
        reference = start if start == end else f"{start}:{end}"
        self.formula_bar.setText(f"{self.formula_bar.text()}{reference}")
        self.formula_bar.setCursorPosition(len(self.formula_bar.text()))

    def apply_formula_bar(self) -> None:
        row, column = self._formula_edit_target or (self.entry_grid.currentRow(), self.entry_grid.currentColumn())
        if row < 0 or column < 0:
            row = column = 0
        if ENTRY_HEADERS[column] in {"Mã QR", "Mã sản phẩm"}:
            self._formula_edit_target = None
            self.entry_grid.formula_reference_mode = False
            self.update_formula_bar(row, column)
            return
        self.entry_grid._begin_history_transaction()
        item = self.entry_grid.item(row, column) or QTableWidgetItem()
        item.setText(complete_formula_parentheses(self.formula_bar.text()))
        self.entry_grid.setItem(row, column, item)
        self.entry_grid.setCurrentCell(row, column)
        self._formula_edit_target = None
        self.entry_grid.formula_reference_mode = False
        self.update_formula_bar(row, column)
        self.entry_grid._commit_history_transaction()

    def format_selected_cells(self, action: str) -> None:
        selected = self.entry_grid.selectedItems()
        if not selected and self.entry_grid.currentItem():
            selected = [self.entry_grid.currentItem()]
        self.entry_grid._begin_history_transaction()
        was_rendering = self.entry_grid._rendering_formulas
        self.entry_grid._rendering_formulas = True
        try:
            for item in selected:
                font = item.font()
                if action == "bold":
                    font.setBold(not font.bold())
                elif action == "italic":
                    font.setItalic(not font.italic())
                elif action == "underline":
                    font.setUnderline(not font.underline())
                elif action == "strikethrough":
                    font.setStrikeOut(not font.strikeOut())
                elif action == "border":
                    item.setData(Qt.ItemDataRole.UserRole + 20, True)
                elif action == "clear":
                    font = QFont()
                    item.setBackground(QColor("transparent"))
                    item.setForeground(QColor(Qt.GlobalColor.black))
                    item.setData(Qt.ItemDataRole.UserRole + 20, None)
                item.setFont(font)
        finally:
            self.entry_grid._rendering_formulas = was_rendering
        self.entry_grid.viewport().update()
        self.entry_grid._commit_history_transaction()

    def format_selected_numbers(self, index: int) -> None:
        """Apply a numeric display format without changing raw worksheet values."""
        source = self.sender()
        display_format = source.itemText(index) if isinstance(source, QComboBox) else str(index)
        selected = self.entry_grid.selectedItems()
        if not selected and self.entry_grid.currentItem():
            selected = [self.entry_grid.currentItem()]
        self.entry_grid._begin_history_transaction()
        for item in selected:
            self.entry_grid.apply_display_format(item, display_format)
        self.entry_grid.fit_all_row_heights()
        self.entry_grid._commit_history_transaction()

    def show_cell_format_dialog(self) -> None:
        dialog = SpreadsheetCellFormatDialog(self.entry_grid.currentItem(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_cell_format(dialog.values())

    def apply_cell_format(self, values: dict[str, object]) -> None:
        """Apply supported display and font options to the current worksheet range."""
        selected = self.entry_grid.selectedItems()
        if not selected and self.entry_grid.currentItem():
            selected = [self.entry_grid.currentItem()]
        self.entry_grid._begin_history_transaction()
        self.entry_grid._rendering_formulas = True
        try:
            for item in selected:
                self.entry_grid.apply_display_format(item, str(values["display_format"]))
                font = item.font()
                font.setBold(bool(values["bold"]))
                font.setItalic(bool(values["italic"]))
                font.setUnderline(bool(values["underline"]))
                item.setFont(font)
                item.setData(Qt.ItemDataRole.UserRole + 20, bool(values["border"]) or None)
        finally:
            self.entry_grid._rendering_formulas = False
        self.entry_grid.fit_all_row_heights()
        self.entry_grid.viewport().update()
        self.entry_grid._commit_history_transaction()

    def choose_cell_color(self, target: str) -> None:
        color = QColorDialog.getColor(parent=self, title="Chọn màu ô")
        if not color.isValid():
            return
        selected = self.entry_grid.selectedItems()
        if not selected and self.entry_grid.currentItem():
            selected = [self.entry_grid.currentItem()]
        self.entry_grid._begin_history_transaction()
        for item in selected:
            if target == "background":
                item.setBackground(color)
            else:
                item.setForeground(color)
        self.entry_grid._commit_history_transaction()

    def insert_auto_sum(self) -> None:
        selected = self.entry_grid.selectedIndexes()
        if not selected:
            QMessageBox.information(self, "AutoSum", "Chọn các ô số trong một cột trước.")
            return
        columns = {index.column() for index in selected}
        if len(columns) != 1:
            QMessageBox.warning(self, "AutoSum", "AutoSum hiện áp dụng cho một cột tại một thời điểm.")
            return
        column = columns.pop()
        rows = sorted({index.row() for index in selected})
        start, end = rows[0], rows[-1]
        target = end + 1
        if target >= self.entry_grid.rowCount():
            self.entry_grid._begin_history_transaction()
            self.entry_grid.setRowCount(target + 1)
            self.entry_grid._number_rows()
        else:
            self.entry_grid._begin_history_transaction()
        formula = f"=SUM({self._excel_column_name(column)}{start + 1}:{self._excel_column_name(column)}{end + 1})"
        self.entry_grid.setItem(target, column, QTableWidgetItem(formula))
        self.entry_grid.setCurrentCell(target, column)
        self.entry_grid._commit_history_transaction()

    def select_entry_image(self) -> None:
        row = self.entry_grid.currentRow()
        if row < 0:
            QMessageBox.information(self, "Chọn dòng", "Hãy chọn dòng cần gắn ảnh trước.")
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh sản phẩm",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp)",
        )
        if filename:
            self.entry_grid._begin_history_transaction()
            image = QImage(filename)
            item = QTableWidgetItem(filename)
            if not image.isNull():
                item.setData(Qt.ItemDataRole.UserRole, self.entry_grid._image_as_png(image))
            self.entry_grid.setItem(row, ENTRY_HEADERS.index("Ảnh sản phẩm"), item)
            self.entry_grid._commit_history_transaction()

    def copy_selected_entry_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self.entry_grid.selectedIndexes()})
        if not selected_rows:
            QMessageBox.information(self, "Copy worksheet", "Chọn ít nhất một ô hoặc dòng để copy.")
            return
        lines = ["\t".join(ENTRY_HEADER_LABELS[header] for header in ENTRY_HEADERS)]
        for row in selected_rows:
            lines.append("\t".join(
                (self.entry_grid.item(row, column).text() if self.entry_grid.item(row, column) else "")
                for column in range(self.entry_grid.columnCount())
            ))
        QApplication.clipboard().setText("\r\n".join(lines))
        self.statusBar().showMessage(f"Đã copy {len(selected_rows)} dòng worksheet. Dán vào Excel bằng Ctrl+V.", 5_000)

    def entry_validation_errors(self, rows: list[int] | None = None) -> list[str]:
        return []

    def entry_row_has_user_data(self, values: list[str]) -> bool:
        generated_headers = {"Mã QR", "Mã sản phẩm", "Trạng thái S/P"}
        return any(value for header, value in zip(ENTRY_HEADERS, values) if header not in generated_headers)

    def save_entry_rows(self, *, rows: list[int] | None = None, interactive: bool = True) -> None:
        validation_errors = self.entry_validation_errors(rows)
        if validation_errors:
            if interactive:
                QMessageBox.warning(
                    self,
                    "Chưa thể lưu worksheet",
                    "Sửa các dòng sau trước khi lưu:\n" + "\n".join(validation_errors),
                )
            return
        imported = 0
        skipped: list[str] = []
        for row in rows if rows is not None else range(self.entry_grid.rowCount()):
            values = [self.entry_grid.item(row, column).text().strip() if self.entry_grid.item(row, column) else ""
                      for column in range(self.entry_grid.columnCount())]
            if not self.entry_row_has_user_data(values):
                continue
            row_data = dict(zip(ENTRY_HEADERS, values))
            company = row_data["Khách hàng"]
            part_name = row_data["Tên sản phẩm"]
            quantity = row_data["Số lượng"] or "0"
            try:
                # The selected navigator date owns this worksheet list. Users do
                # not need to repeat the same date in every row.
                delivery_schedule = self.selected_delivery_date
                dimensions = format_dimensions([
                    row_data["Kích thước X"], row_data["Kích thước Y"], row_data["Kích thước Z"],
                ])
                status = next((value for value, label in STATUS_LABELS.items()
                               if label.casefold() == row_data["Trạng thái S/P"].casefold()), ProductStatus.NEW)
                product_data = dict(
                    company=company, part_name=part_name, quantity=max(Decimal("0"), Decimal(quantity.replace(",", ""))),
                    unit=row_data["Đơn vị"] or "pcs", material=row_data["Vật liệu"] or None,
                    requester=row_data["Người đặt"] or None, surface_treatment=row_data["Xử lý bề mặt"] or None,
                    outsourced=bool(row_data["Đặt ngoài"]), outsourced_company=row_data["Đặt ngoài"] or None,
                    size=dimensions or None, notes=row_data["Ghi chú"] or None,
                    delivery_schedule=delivery_schedule, status=status,
                )
                saved_id = self.entry_grid.item(row, 0).data(Qt.ItemDataRole.UserRole + 30)
                preview_code = row_data["Mã sản phẩm"] or None
                self._saving_entry_rows = True
                self.entry_grid.blockSignals(True)
                try:
                    product = (self.service.update_product(
                        saved_id, actor=self.actor, product_code=preview_code, **product_data,
                    )
                               if saved_id else self.service.create_product(
                                    actor=self.actor, product_code=preview_code, **product_data,
                                ))
                finally:
                    self.entry_grid.blockSignals(False)
                    self._saving_entry_rows = False
                self.entry_grid.item(row, 0).setData(Qt.ItemDataRole.UserRole + 30, str(product.internal_id))
                code_column = ENTRY_HEADERS.index("Mã sản phẩm")
                qr_column = ENTRY_HEADERS.index("Mã QR")
                code_item = self.entry_grid.item(row, code_column) or QTableWidgetItem()
                code_item.setText(product.product_code)
                code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if self.entry_grid.item(row, code_column) is None:
                    self.entry_grid.setItem(row, code_column, code_item)
                qr_item = self.entry_grid.item(row, qr_column) or QTableWidgetItem()
                qr_item.setText(product_qr_value(product.product_code, company))
                qr_item.setData(
                    Qt.ItemDataRole.UserRole + 21,
                    product_qr_label_png(
                        qr_item.text(), product.product_code, part_name, dimensions, delivery_schedule,
                    ),
                )
                qr_item.setFlags(qr_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if self.entry_grid.item(row, qr_column) is None:
                    self.entry_grid.setItem(row, qr_column, qr_item)
                image_path = row_data["Ảnh sản phẩm"]
                image_item = self.entry_grid.item(row, ENTRY_HEADERS.index("Ảnh sản phẩm"))
                image_bytes = image_item.data(Qt.ItemDataRole.UserRole) if image_item else None
                saved_file_id = image_item.data(Qt.ItemDataRole.UserRole + 31) if image_item else None
                if (image_bytes or image_path) and not saved_file_id:
                    image = Path(image_path)
                    if not image_bytes and not image.is_file():
                        raise ValueError("Không tìm thấy tệp ảnh")
                    if self.files_panel.managed_service is None:
                        raise ValueError("Dịch vụ lưu ảnh chưa sẵn sàng")
                    self.files_panel.managed_service.upload_product_image(
                        product_id=product.internal_id,
                        original_filename="clipboard-image.png" if image_bytes else image.name,
                        declared_mime="image/png" if image_bytes else mimetypes.guess_type(image.name)[0] or "application/octet-stream",
                        content=bytes(image_bytes) if image_bytes else image.read_bytes(),
                        actor=self.actor,
                        make_primary=True,
                    )
                imported += 1
            except Exception as exc:
                skipped.append(f"Dòng {row + 1}: {exc}")
        if imported:
            self.refresh()
        if imported:
            self._entry_products_by_date.clear()
            self._entry_products_month = None
            self.save_entry_draft()
            self.load_entry_rows_for_selected_date()
        if not interactive:
            return
        message = f"Đã lưu {imported} dòng trong list ngày {self.selected_delivery_date.isoformat()}."
        if skipped:
            message += " Không lưu được:\n" + "\n".join(skipped)
        QMessageBox.information(self, "Kết quả nhập liệu", message)

    def refresh(self) -> None:
        self.model.set_page(self.service.list_products(search=self.search.text() or None,
                                                       status=self.filter_status.currentData()))
        self.product_result_count.setText(f"{self.model.page.total} sản phẩm")
        self._capture_latest_product_version()

    def _latest_product_version_from_server(self) -> tuple[str, datetime] | None:
        """Fetch one row only so polling never replaces an in-progress worksheet."""
        page = self.service.list_products(page=1, page_size=1, sort_by="updated_at", descending=True)
        if not page.items:
            return None
        product = page.items[0]
        return str(product.internal_id), product.updated_at

    def _capture_latest_product_version(self) -> None:
        try:
            self._latest_product_version = self._latest_product_version_from_server()
            self._lan_change_notice_visible = False
        except Exception:
            # A transient connection failure must not interrupt local worksheet editing.
            pass

    def check_for_product_changes(self) -> None:
        try:
            latest = self._latest_product_version_from_server()
        except Exception:
            return
        if self._latest_product_version is None:
            self._latest_product_version = latest
            return
        if latest == self._latest_product_version:
            return
        self._latest_product_version = latest
        self.model.set_page(self.service.list_products(search=self.search.text() or None,
                                                       status=self.filter_status.currentData()))
        self.product_result_count.setText(f"{self.model.page.total} sản phẩm")
        if not self._lan_change_notice_visible:
            self.statusBar().showMessage(
                "Dữ liệu sản phẩm đã được cập nhật từ máy khác. Bảng đã làm mới; worksheet đang nhập được giữ nguyên.",
                15_000,
            )
            self._lan_change_notice_visible = True

    def create_product(self, payload: dict[str, object]) -> None:
        self.service.create_product(actor=self.actor, **payload)
        self.refresh()


def run(service: ProductService, *, managed_service=None, transfer_service=None, server_url: str = "", actor: str = "desktop-user", account_role: str = "") -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = ProductMasterWindow(
        service,
        actor=actor,
        managed_file_service=managed_service,
        transfer_service=transfer_service,
        server_url=server_url,
        account_role=account_role,
    )
    window.show()
    return app.exec()


__all__ = ["ProductMasterWindow", "ProductTableModel", "run"]
