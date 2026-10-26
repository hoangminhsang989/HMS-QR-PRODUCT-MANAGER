"""PySide6 screens for the desktop licence gate.

``QtLicenseUi`` is the adapter ``DesktopLicenseGate`` drives: it owns no policy
and decides nothing. Every user-facing string is Vietnamese; the status codes
come from ``packages.hms_license`` and are translated here.

The SDK is never imported at module level. The gate hands this class a ready
client, so a missing or broken vendored SDK shows up as a message on a screen
instead of an ImportError before a single window exists.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

#: ``LicenseClient.activate`` outcomes, in the customer's words. ``ok`` is
#: absent on purpose: it closes the dialog rather than printing a message.
_ONLINE_OUTCOME_MESSAGES = {
    "invalid_key": "Mã kích hoạt không đúng. Kiểm tra lại ký tự đã nhập.",
    "devices_exceeded": "Mã kích hoạt đã dùng hết số máy cho phép.",
    "key_revoked": "Mã kích hoạt đã bị thu hồi.",
    "product_mismatch": "Ma kich ho?t thu?c ph?n m?m khac, khong dung du?c cho ph?n m?m nay.",
    "key_expired": "Mã kích hoạt đã hết hạn.",
    "network_error": "Không kết nối được Máy chủ bản quyền. Kiểm tra mạng rồi thử lại.",
}

#: ``LicenseClient.import_license_file`` outcomes.
_IMPORT_OUTCOME_MESSAGES = {
    "hwid-mismatch": "File license này thuộc về máy khác.",
    "invalid-file": "File license không đọc được hoặc không đúng.",
}

_UNKNOWN_OUTCOME_MESSAGE = "Không kích hoạt được. Thử lại hoặc liên hệ nhà cung cấp."
_MISSING_CLIENT_MESSAGE = "Hệ thống bản quyền chưa được cài đặt. Liên hệ nhà cung cấp."


class ActivationDialog(QDialog):
    """Collect a key and redeem it, online or from an offline file."""

    def __init__(self, client, parent=None) -> None:
        super().__init__(parent)
        self._client = client
        self.setWindowTitle("Kích hoạt bản quyền HMS QR")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Nhập mã kích hoạt để mở phần mềm HMS QR."))
        self.key_field = QLineEdit()
        self.key_field.setPlaceholderText("Mã kích hoạt")
        layout.addWidget(self.key_field)
        self.online_button = QPushButton("Kích hoạt online")
        self.online_button.clicked.connect(self._activate_online)
        layout.addWidget(self.online_button)
        self.offline_button = QPushButton("Kích hoạt offline")
        self.offline_button.clicked.connect(self._activate_offline)
        layout.addWidget(self.offline_button)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    # -- online -------------------------------------------------------------

    def _activate_online(self) -> None:
        key = self.key_field.text().strip()
        if not key:
            self._report("Nhập mã kích hoạt trước.")
            return
        try:
            outcome = self._client.activate(key)
        except Exception:
            self._report(_UNKNOWN_OUTCOME_MESSAGE)
            return
        if outcome == "ok":
            self.accept()
            return
        self._report(_ONLINE_OUTCOME_MESSAGES.get(outcome, _UNKNOWN_OUTCOME_MESSAGE))

    # -- offline ------------------------------------------------------------

    def _activate_offline(self) -> None:
        request_path = self._ask_request_path()
        if not request_path:
            return
        try:
            self._client.create_request_file(request_path)
        except Exception:
            self._report("Không tạo được file yêu cầu kích hoạt.")
            return
        self._confirm_request_created(request_path)
        license_path = self._ask_license_path()
        if not license_path:
            return
        try:
            outcome = self._client.import_license_file(license_path)
        except Exception:
            self._report(_UNKNOWN_OUTCOME_MESSAGE)
            return
        if outcome == "ok":
            self.accept()
            return
        self._report(_IMPORT_OUTCOME_MESSAGES.get(outcome, _UNKNOWN_OUTCOME_MESSAGE))

    # -- file-picker seams --------------------------------------------------

    def _ask_request_path(self) -> str:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Lưu file yêu cầu kích hoạt",
            "yeu-cau-kich-hoat.req",
            "File yêu cầu (*.req)",
        )
        return path or ""

    def _ask_license_path(self) -> str:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Chọn file license đã nhận",
            "",
            "File license (*.lic)",
        )
        return path or ""

    def _confirm_request_created(self, path: str) -> None:
        QMessageBox.information(
            self,
            "Đã tạo file yêu cầu",
            f"Đã lưu file yêu cầu tại:\n{path}\n\n"
            "Gửi file này cho nhà cung cấp để nhận về file license, "
            "rồi mở lại cửa sổ này và bấm \"Kích hoạt offline\" một lần nữa.",
        )

    def _report(self, message: str) -> None:
        self.status.setText(message)


class LockScreen(QDialog):
    """The app cannot be used until the licence is repaired.

    Escape, the window close button and ``reject()`` are all refused: a lock
    screen that can be dismissed is not a lock. The only ways out are a
    successful reactivation or the explicit quit button, which records the
    choice so the gate can tell "the operator quit" from "the operator gave up".
    """

    def __init__(self, reason: str, ui: "QtLicenseUi", parent=None) -> None:
        super().__init__(parent)
        self._ui = ui
        self.reactivated = False
        self.quit_requested = False
        self.setWindowTitle("HMS QR đã bị khóa")
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        layout = QVBoxLayout(self)
        self.reason_label = QLabel(reason)
        self.reason_label.setWordWrap(True)
        layout.addWidget(self.reason_label)
        self.reactivate_button = QPushButton("Kích hoạt lại")
        self.reactivate_button.clicked.connect(self._reactivate)
        layout.addWidget(self.reactivate_button)
        self.quit_button = QPushButton("Thoát")
        self.quit_button.clicked.connect(self._quit)
        layout.addWidget(self.quit_button)

    def reject(self) -> None:
        """Escape and the window close button must not dismiss a lock screen."""
        return None

    def closeEvent(self, event) -> None:
        event.ignore()

    def _reactivate(self) -> None:
        if self._ui.activation():
            self.reactivated = True
            self.accept()

    def _quit(self) -> None:
        self.quit_requested = True
        self.accept()


class GraceBanner(QLabel):
    """A non-modal reminder that the grace window is running out."""

    def __init__(self, grace_days: int | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("HMS QR")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWordWrap(True)
        self.setMargin(8)
        self.setText(_grace_text(grace_days))
        self.adjustSize()


def _grace_text(grace_days: int | None) -> str:
    """The banner sentence for 0, 1, many, or an unknown number of days."""
    if grace_days is None:
        return "Bản quyền đã hết hạn. Hãy gia hạn để tránh bị khóa."
    if grace_days <= 0:
        return "Bản quyền đã hết hạn. Gia hạn ngay để tránh bị khóa."
    if grace_days == 1:
        return "Bản quyền đã hết hạn, còn 1 ngày."
    return f"Bản quyền đã hết hạn, còn {grace_days} ngày."


class QtLicenseUi:
    """The gate's adapter: show the right screen, report what happened."""

    def __init__(self, client, *, error_view=QMessageBox.critical) -> None:
        self._client = client
        self._error_view = error_view
        self._banner: GraceBanner | None = None

    def activation(self) -> bool:
        """Ask for a key. True only when the client stored a usable licence."""
        if self._client is None:
            self._error_view(None, "Lỗi bản quyền", _MISSING_CLIENT_MESSAGE)
            return False
        dialog = ActivationDialog(self._client)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def lock(self, reason: str) -> bool:
        """Show the lock screen. True only when the customer reactivated."""
        if self._client is None:
            self._error_view(None, "Lỗi bản quyền", _MISSING_CLIENT_MESSAGE)
            return False
        screen = LockScreen(reason, self)
        screen.exec()
        return screen.reactivated

    def banner(self, grace_days: int | None) -> None:
        """A non-modal reminder; it never blocks the app from starting."""
        if self._banner is None:
            self._banner = GraceBanner(grace_days)
        else:
            self._banner.setText(_grace_text(grace_days))
        self._banner.show()
