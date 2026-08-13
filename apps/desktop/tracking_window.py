from PySide6.QtWidgets import QMainWindow,QWidget,QVBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QMessageBox
class TrackingWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle("HMS QR — Theo dõi đơn hàng và QR");self.resize(1050,650);self.setStyleSheet("QWidget{background:#18212b;color:#eef4fa} QPushButton{background:#177e70;padding:8px}")
        root=QWidget();layout=QVBoxLayout(root);layout.addWidget(QLabel("TRACKING ITEM / QR / BÁO CÁO GIA CÔNG"));table=QTableWidget(0,8);table.setHorizontalHeaderLabels(["Mã theo dõi","QR","Ngày giao","Sản phẩm","Khách hàng","Đơn hàng","Số lượng","Báo cáo"]);layout.addWidget(table)
        for text in ("TẠO QR","XEM QR","IN / XUẤT QR","ĐỔI NGÀY GIAO HÀNG","TẠO ĐƠN MỚI"):
            button=QPushButton(text);layout.addWidget(button)
        self.table=table;self.setCentralWidget(root)
