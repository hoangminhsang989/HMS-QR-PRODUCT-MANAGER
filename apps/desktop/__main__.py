import os

from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from packages.application.product_api_client import ProductApiClient
from packages.application.file_api_client import FileApiClient
from packages.application.server_discovery import discover_server_url, normalize_server_url, resolve_server_url, save_server_url, server_is_ready
from .product_master_window import run
from .credentials import delete_credentials, load_credentials, save_credentials


class DesktopLoginDialog(QDialog):
    """Collect LAN credentials only when the launcher did not provide them."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Đăng nhập HMS QR Desktop")
        form = QFormLayout(self)
        self.username = QLineEdit()
        self.username.setPlaceholderText("Tên đăng nhập")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Mật khẩu")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.remember_credentials = QCheckBox("Ghi nhớ đăng nhập trên máy này")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_complete)
        buttons.rejected.connect(self.reject)
        form.addRow("Tên đăng nhập:", self.username)
        form.addRow("Mật khẩu:", self.password)
        form.addRow(self.remember_credentials)
        form.addRow(buttons)

    def _accept_if_complete(self) -> None:
        if not self.username.text().strip() or not self.password.text():
            QMessageBox.warning(self, "Thiếu thông tin", "Nhập tên đăng nhập và mật khẩu.")
            return
        self.accept()


class ServerSelectionDialog(QDialog):
    """Recover from unavailable automatic LAN discovery without accepting an unready endpoint."""

    def __init__(self, *, discover=discover_server_url, ready=server_is_ready, save=save_server_url) -> None:
        super().__init__()
        self.discover = discover
        self.ready = ready
        self.save = save
        self.setWindowTitle("Kết nối HMS QR Server")
        form = QFormLayout(self)
        self.message = QLabel("Không tự tìm thấy Server. Tìm lại trong mạng LAN hoặc nhập URL Máy 1.")
        self.message.setWordWrap(True)
        self.server_url = QLineEdit()
        self.server_url.setPlaceholderText("Ví dụ: http://192.168.2.15:8010")
        self.discover_button = QPushButton("TÌM SERVER LAN")
        self.discover_button.clicked.connect(self.find_server)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_ready)
        buttons.rejected.connect(self.reject)
        form.addRow(self.message)
        form.addRow("URL Server:", self.server_url)
        form.addRow(self.discover_button)
        form.addRow(buttons)

    def find_server(self) -> None:
        self.message.setText("Đang tìm HMS QR Server trong mạng LAN...")
        QApplication.processEvents()
        found = self.discover()
        if not found:
            self.message.setText("Không tìm thấy Server. Kiểm tra Máy 1, Wi-Fi/LAN và mạng Private.")
            return
        self.server_url.setText(found)
        self.message.setText("Đã tìm thấy Server. Bấm Kết nối để kiểm tra.")

    def _accept_if_ready(self) -> None:
        try:
            server_url = normalize_server_url(self.server_url.text())
        except ValueError:
            QMessageBox.warning(self, "URL không hợp lệ", "Nhập URL dạng http://IP:8010.")
            return
        if not self.ready(server_url):
            self.message.setText("Server chưa sẵn sàng. Kiểm tra Máy 1 hoặc thử tìm lại.")
            return
        self.save(server_url)
        self.server_url.setText(server_url)
        self.accept()


def desktop_server_url(*, configured_url: str = "", resolver=resolve_server_url, dialog_factory=ServerSelectionDialog) -> str:
    try:
        return normalize_server_url(resolver(configured_url=configured_url))
    except RuntimeError:
        if configured_url.strip():
            raise
    dialog = dialog_factory()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        raise RuntimeError("Đã hủy chọn HMS QR Server.")
    return normalize_server_url(dialog.server_url.text())


def desktop_login_details(*, username: str = "", password: str = "", dialog_factory=DesktopLoginDialog,
                          load_credentials=load_credentials, credential_path=None) -> tuple[str, str, bool]:
    if username.strip() and password:
        return username.strip(), password, False
    dialog = dialog_factory()
    saved = load_credentials() if load_credentials is not None else None
    if saved:
        dialog.username.setText(saved[0])
        dialog.password.setText(saved[1])
        dialog.remember_credentials.setChecked(True)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        raise RuntimeError("Đã hủy đăng nhập HMS QR Desktop.")
    return dialog.username.text().strip(), dialog.password.text(), dialog.remember_credentials.isChecked()


def desktop_credentials(**kwargs) -> tuple[str, str]:
    """Compatibility helper returning only the username and password pair."""
    username, password, _remember = desktop_login_details(**kwargs)
    return username, password


if __name__ == "__main__":
    app = QApplication.instance() or QApplication([])
    server_url = desktop_server_url(configured_url=os.environ.get("HMS_QR_SERVER_URL", ""))
    product_service = ProductApiClient(server_url)
    username, password, remember = desktop_login_details(
        username=os.environ.get("HMS_QR_USERNAME", ""),
        password=os.environ.get("HMS_QR_PASSWORD", ""),
    )
    product_service.verify_server_readiness()
    session = product_service.login(username, password)
    if remember:
        save_credentials(username, password)
    else:
        delete_credentials()
    file_service = FileApiClient(server_url, access_token=product_service.access_token or "")
    run(
        product_service,
        managed_service=file_service,
        server_url=server_url,
        actor=session["username"],
        account_role=session["role"],
    )
