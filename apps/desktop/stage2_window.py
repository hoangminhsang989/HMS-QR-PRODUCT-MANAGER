from __future__ import annotations
from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QListWidget
from packages.application.stage2_service import Stage2Service

class Stage2Window(QMainWindow):
    def __init__(self, service: Stage2Service):
        super().__init__(); self.service=service; self.setWindowTitle("HMS QR — Khách hàng, Đơn hàng và Lịch sản xuất"); self.resize(1200,720)
        self.setStyleSheet("QMainWindow,QWidget{background:#18212b;color:#e8eef5;} QTabWidget::pane{border:1px solid #405060;}")
        tabs=QTabWidget()
        for title, items in (("KHÁCH HÀNG",["Danh sách khách hàng","Tìm kiếm","Tạo / sửa khách hàng"]),("ĐƠN HÀNG / PO",["Danh sách PO","Chi tiết PO","PO lines"]),("LỊCH SẢN XUẤT",["Production Run","Lịch giao hàng","Theo dõi planned / completed"])):
            page=QWidget(); layout=QVBoxLayout(page); layout.addWidget(QLabel(title)); list_widget=QListWidget(); list_widget.addItems(items); layout.addWidget(list_widget); tabs.addTab(page,title)
        self.setCentralWidget(tabs)
