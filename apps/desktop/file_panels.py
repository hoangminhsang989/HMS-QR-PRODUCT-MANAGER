"""Compact Light Industrial product-file and storage administration widgets."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import UUID, uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView,
    QVBoxLayout, QWidget,
)

from packages.domain.store_forward import StorageConfiguration


ARCHIVE_LABELS = {
    "LOCAL_READY": "ĐÃ LƯU TRÊN SERVER",
    "TRANSFER_QUEUED": "CHỜ ĐỒNG BỘ",
    "TRANSFERRING": "ĐANG ĐỒNG BỘ",
    "REMOTE_VERIFYING": "ĐANG XÁC MINH",
    "REMOTE_READY": "ĐÃ LƯU TRỮ",
    "LOCAL_GRACE_RETENTION": "ĐÃ LƯU TRỮ · GIỮ BẢN SERVER",
    "LOCAL_PURGE_PENDING": "ĐÃ LƯU TRỮ · CHỜ DỌN SERVER",
    "ARCHIVED_REMOTE_ONLY": "ĐÃ LƯU TRỮ",
    "TRANSFER_FAILED_RETRYABLE": "LỖI ĐỒNG BỘ · SẼ THỬ LẠI",
    "TRANSFER_FAILED_PERMANENT": "LỖI ĐỒNG BỘ · CẦN XỬ LÝ",
}


class ProductFilesPanel(QWidget):
    def __init__(self, managed_service=None, transfer_service=None, actor: str = "desktop-user") -> None:
        super().__init__()
        self.managed_service = managed_service
        self.transfer_service = transfer_service
        self.actor = actor
        self.product_id: UUID | None = None
        self.images = _file_table(["Tên ảnh", "Chính", "Chú thích", "Lưu trữ"])
        self.attachments = _file_table(["Tên tệp", "Loại", "Dung lượng", "Người tải", "Lưu trữ"])
        self.add_image_button = QPushButton("THÊM ẢNH")
        self.primary_button = QPushButton("ĐẶT ẢNH CHÍNH")
        self.add_attachment_button = QPushButton("THÊM TỆP")
        self.view_button = QPushButton("XEM / TẢI")
        self.archive_button = QPushButton("LƯU TRỮ")
        self.retry_button = QPushButton("ĐỒNG BỘ NGAY")
        self.state_label = QLabel("Chọn một sản phẩm để xem ảnh và tệp đính kèm.")
        self.state_label.setWordWrap(True)
        self.add_image_button.clicked.connect(self.add_image)
        self.primary_button.clicked.connect(self.set_primary)
        self.add_attachment_button.clicked.connect(self.add_attachment)
        self.view_button.clicked.connect(self.download_selected)
        self.archive_button.clicked.connect(self.archive_selected)
        self.retry_button.clicked.connect(self.retry_selected)
        self.images.itemSelectionChanged.connect(
            lambda: self.attachments.clearSelection() if self.images.selectedItems() else None
        )
        self.attachments.itemSelectionChanged.connect(
            lambda: self.images.clearSelection() if self.attachments.selectedItems() else None
        )
        actions = QHBoxLayout()
        for button in (
            self.add_image_button, self.primary_button, self.add_attachment_button,
            self.view_button, self.archive_button, self.retry_button,
        ):
            actions.addWidget(button)
        images_box = QGroupBox("ẢNH SẢN PHẨM")
        images_layout = QVBoxLayout(images_box)
        images_layout.addWidget(self.images)
        attachments_box = QGroupBox("TỆP ĐÍNH KÈM")
        attachments_layout = QVBoxLayout(attachments_box)
        attachments_layout.addWidget(self.attachments)
        tables = QHBoxLayout()
        tables.addWidget(images_box, 1)
        tables.addWidget(attachments_box, 2)
        layout = QVBoxLayout(self)
        layout.addWidget(self.state_label)
        layout.addLayout(actions)
        layout.addLayout(tables)
        self.setEnabled(managed_service is not None)

    def set_product(self, product_id: UUID | None) -> None:
        self.product_id = product_id
        self.refresh()

    def refresh(self) -> None:
        self.images.setRowCount(0)
        self.attachments.setRowCount(0)
        if self.product_id is None or self.managed_service is None:
            self.state_label.setText("Chọn một sản phẩm để xem ảnh và tệp đính kèm.")
            return
        images = self.managed_service.repository.list_images(self.product_id)
        attachments = self.managed_service.repository.list_attachments(self.product_id)
        for item in images:
            state = self._state(item.managed_file.file_id)
            _append_row(self.images, item.managed_file.file_id, (
                item.managed_file.original_filename,
                "●" if item.relation.is_primary else "",
                item.relation.caption or "",
                state,
            ))
        for item in attachments:
            state = self._state(item.managed_file.file_id)
            _append_row(self.attachments, item.managed_file.file_id, (
                item.managed_file.original_filename,
                item.relation.attachment_category or "OTHER",
                _human_bytes(item.managed_file.size_bytes),
                item.managed_file.created_by,
                state,
            ))
        self.state_label.setText(
            f"{len(images)} ảnh · {len(attachments)} tệp · Tệp mới được lưu an toàn trên Server trước."
        )

    def add_image(self) -> None:
        path = self._choose_open("Chọn ảnh sản phẩm", "Images (*.png *.jpg *.jpeg *.gif *.webp)")
        if path and self.product_id:
            self._run(lambda: self.managed_service.upload_product_image(
                product_id=self.product_id, original_filename=path.name,
                declared_mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                content=path.read_bytes(), actor=self.actor,
                make_primary=self.images.rowCount() == 0,
            ))

    def add_attachment(self) -> None:
        path = self._choose_open("Chọn tệp đính kèm", "Managed files (*.*)")
        if path and self.product_id:
            self._run(lambda: self.managed_service.upload_attachment(
                product_id=self.product_id, original_filename=path.name,
                declared_mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                content=path.read_bytes(), actor=self.actor, attachment_category="OTHER",
            ))

    def set_primary(self) -> None:
        file_id = _selected_id(self.images)
        if file_id and self.product_id:
            self._run(lambda: self.managed_service.set_primary_image(
                product_id=self.product_id, file_id=file_id
            ))

    def download_selected(self) -> None:
        file_id = _selected_id(self.images) or _selected_id(self.attachments)
        if not file_id:
            return
        managed = self.managed_service.repository.get(file_id)
        target, _ = QFileDialog.getSaveFileName(self, "Lưu bản tải xuống", managed.original_filename)
        if target:
            self._run(lambda: Path(target).write_bytes(self.managed_service.read(file_id)))

    def archive_selected(self) -> None:
        file_id = _selected_id(self.images) or _selected_id(self.attachments)
        if file_id:
            self._run(lambda: self.managed_service.archive(file_id=file_id, actor=self.actor))

    def retry_selected(self) -> None:
        file_id = _selected_id(self.images) or _selected_id(self.attachments)
        if file_id and self.transfer_service:
            self._run(lambda: self.transfer_service.retry_now(file_id))

    def _state(self, file_id: UUID) -> str:
        if not self.transfer_service:
            return "ĐÃ LƯU TRÊN SERVER"
        try:
            state = self.transfer_service.status(file_id).state.value
            return ARCHIVE_LABELS.get(state, state)
        except LookupError:
            return "ĐÃ LƯU TRÊN SERVER"

    def _choose_open(self, title: str, file_filter: str) -> Path | None:
        selected, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        return Path(selected) if selected else None

    def _run(self, operation) -> None:
        try:
            operation()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Không thể thực hiện", str(exc))


class AdminStoragePanel(QWidget):
    def __init__(self, transfer_service=None) -> None:
        super().__init__()
        self.transfer_service = transfer_service
        self.local_root = QLineEdit()
        self.archive_root = QLineEdit()
        self.grace_hours = QSpinBox()
        self.grace_hours.setRange(0, 168)
        self.grace_hours.setValue(24)
        self.health = QLabel("Chưa tải trạng thái lưu trữ.")
        self.health.setWordWrap(True)
        local_row = _path_row(self.local_root, self, "Chọn vị trí lưu trên Server")
        archive_row = _path_row(self.archive_root, self, "Chọn vị trí lưu trữ dài hạn")
        form = QFormLayout()
        form.addRow("Vị trí lưu trên Server", local_row)
        form.addRow("Vị trí lưu trữ dài hạn", archive_row)
        form.addRow("Giữ bản Server sau đồng bộ (giờ)", self.grace_hours)
        save = QPushButton("KIỂM TRA VÀ LƯU CẤU HÌNH")
        refresh = QPushButton("LÀM MỚI SỨC KHỎE")
        retry = QPushButton("THỬ LẠI LỖI")
        save.clicked.connect(self.save)
        refresh.clicked.connect(self.refresh)
        retry.clicked.connect(self.retry_failed)
        actions = QHBoxLayout()
        actions.addWidget(save)
        actions.addWidget(refresh)
        actions.addWidget(retry)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(self.health)
        layout.addStretch(1)
        self.setEnabled(transfer_service is not None)
        self.load()

    def load(self) -> None:
        if not self.transfer_service:
            return
        try:
            config = self.transfer_service.repository.get_active_configuration()
            self.local_root.setText(config.local_ingest_root)
            self.archive_root.setText(config.archive_target_root)
            self.grace_hours.setValue(config.grace_period_hours)
            self.refresh()
        except LookupError:
            self.health.setText("Chưa có cấu hình lưu trữ đang hoạt động.")

    def save(self) -> None:
        if not self.transfer_service:
            return
        try:
            current = None
            try:
                current = self.transfer_service.repository.get_active_configuration()
            except LookupError:
                pass
            configuration = StorageConfiguration(
                configuration_id=uuid4(),
                local_ingest_root=self.local_root.text(),
                archive_target_root=self.archive_root.text(),
                grace_period_hours=self.grace_hours.value(),
                retry_schedule_seconds=current.retry_schedule_seconds if current else (60, 300, 900, 1800, 3600),
                warning_free_bytes=current.warning_free_bytes if current else 10 * 1024**3,
                critical_free_bytes=current.critical_free_bytes if current else 5 * 1024**3,
                upload_refusal_free_bytes=current.upload_refusal_free_bytes if current else 2 * 1024**3,
            )
            self.transfer_service.configure(configuration, validate_write=True)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Cấu hình lưu trữ không hợp lệ", str(exc))

    def refresh(self) -> None:
        if not self.transfer_service:
            return
        try:
            value = self.transfer_service.health()
            capacity = value["capacity"]
            self.health.setText(
                f"SERVER: {value['local']['state']} · ARCHIVE: {value['archive']['state']} · "
                f"Chờ đồng bộ: {capacity.pending_transfer_count} tệp / {_human_bytes(capacity.pending_transfer_bytes)} · "
                f"Trống: {_human_bytes(capacity.local_free_bytes)} · Mức: {capacity.level}"
            )
        except Exception as exc:
            self.health.setText(f"Không thể đọc trạng thái: {exc}")

    def retry_failed(self) -> None:
        if not self.transfer_service:
            return
        for job in self.transfer_service.repository.list_jobs():
            if job.state.value.startswith("TRANSFER_FAILED"):
                self.transfer_service.retry_now(job.managed_file_id)
        self.refresh()


def _file_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setMaximumHeight(180)
    return table


def _append_row(table: QTableWidget, file_id: UUID, values: tuple[str, ...]) -> None:
    row = table.rowCount()
    table.insertRow(row)
    for column, value in enumerate(values):
        item = QTableWidgetItem(str(value))
        if column == 0:
            item.setData(Qt.ItemDataRole.UserRole, str(file_id))
        table.setItem(row, column, item)


def _selected_id(table: QTableWidget) -> UUID | None:
    row = table.currentRow()
    if row < 0 or table.item(row, 0) is None:
        return None
    value = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
    return UUID(value) if value else None


def _path_row(field: QLineEdit, parent: QWidget, title: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    choose = QPushButton("CHỌN…")
    choose.clicked.connect(lambda: _choose_directory(parent, field, title))
    layout.addWidget(field, 1)
    layout.addWidget(choose)
    return row


def _choose_directory(parent: QWidget, field: QLineEdit, title: str) -> None:
    path = QFileDialog.getExistingDirectory(parent, title, field.text())
    if path:
        field.setText(path)


def _human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


__all__ = ["AdminStoragePanel", "ProductFilesPanel", "ARCHIVE_LABELS"]
