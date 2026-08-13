from uuid import uuid4
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QMessageBox
from packages.domain.workflow import WorkflowEventType

class WorkflowActionDialog(QDialog):
    def __init__(self,title,quantity_required=True,parent=None):
        super().__init__(parent);self.setWindowTitle(title);form=QFormLayout(self);self.quantity=QLineEdit();self.notes=QLineEdit()
        if quantity_required:form.addRow("Số lượng",self.quantity)
        form.addRow("Nội dung / ghi chú",self.notes);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);form.addRow(buttons)

class TrackingHistoryDialog(QDialog):
    def __init__(self,rows,parent=None):
        super().__init__(parent);self.setWindowTitle("Lịch sử Tracking Item");layout=QVBoxLayout(self);table=QTableWidget(len(rows),6);table.setHorizontalHeaderLabels(["Thời gian","Người dùng","Nhóm","Hành động","Số lượng","Nội dung"])
        for row,data in enumerate(rows):
            for column,value in enumerate((data.get("server_timestamp",""),data.get("actor_display_name_snapshot",""),data.get("source",""),data.get("event_type",""),data.get("quantity") or "",data.get("notes") or "")):table.setItem(row,column,QTableWidgetItem(str(value)))
        layout.addWidget(table);self.table=table

class TrackingWindow(QMainWindow):
    STATUS_COLORS={"QC_NG":"#c44536","REWORK":"#c44536","SHORTAGE":"#b7791f","PACKING":"#2878a8","PACKED":"#177e70","PARTIALLY_DELIVERED":"#2878a8","DELIVERED":"#177e70"}
    def __init__(self,workflow_actions=None,workflow_context=None):
        super().__init__();self.setWindowTitle("HMS QR — Theo dõi đơn hàng và QR");self.resize(1050,650);self.setStyleSheet("QWidget{background:#18212b;color:#eef4fa} QPushButton{background:#177e70;padding:8px}")
        root=QWidget();layout=QVBoxLayout(root);layout.addWidget(QLabel("TRACKING ITEM / QR / GIA CÔNG / QC / ĐÓNG GÓI / GIAO HÀNG"));table=QTableWidget(0,12);table.setHorizontalHeaderLabels(["Mã theo dõi","QR","Ngày giao","Sản phẩm","Khách hàng","Đơn hàng","Số lượng","QC / NG","Đã đóng gói","Đã giao","Trạng thái","Lịch sử"]);layout.addWidget(table)
        for text in ("TẠO QR","XEM QR","IN / XUẤT QR","ĐỔI NGÀY GIAO HÀNG","TẠO ĐƠN MỚI"):
            button=QPushButton(text);layout.addWidget(button)
        action_row=QHBoxLayout();self.workflow_buttons={}
        for code,text in (("QC_CHECKED","ĐÃ KIỂM TRA"),("SHORTAGE_REPORTED","THIẾU HÀNG"),("QC_NG_RETURNED_TO_MACHINING","NG"),("PACKED","ĐÃ ĐÓNG GÓI"),("DELIVERED","ĐÃ GIAO HÀNG"),("GENERAL_REPORT","BÁO CÁO")):
            button=QPushButton(text);self.workflow_buttons[code]=button;action_row.addWidget(button)
            if workflow_actions and code in workflow_actions:button.clicked.connect(workflow_actions[code])
        layout.addLayout(action_row);history_button=QPushButton("MỞ LỊCH SỬ TRACKING ITEM");layout.addWidget(history_button)
        if workflow_actions and "HISTORY" in workflow_actions:history_button.clicked.connect(workflow_actions["HISTORY"])
        self.table=table;self.history_button=history_button;self.setCentralWidget(root)
        if workflow_context:self.bind_workflow_context(**workflow_context)

    def bind_workflow_context(self,tracking_item_id,actor_user_id,actor_display_name,qc_service,packing_service,delivery_service,general_service,history_service):
        services={"QC_CHECKED":qc_service,"SHORTAGE_REPORTED":qc_service,"QC_NG_RETURNED_TO_MACHINING":qc_service,"PACKED":packing_service,"DELIVERED":delivery_service,"GENERAL_REPORT":general_service}
        for event_type,service in services.items():
            self.workflow_buttons[event_type].clicked.connect(lambda _checked=False,t=event_type,s=service:self.submit_selected_workflow(t,s,tracking_item_id,actor_user_id,actor_display_name))
        self.history_button.clicked.connect(lambda:self.open_history(history_service,tracking_item_id))

    def open_history(self,history_service,tracking_item_id):
        dialog=TrackingHistoryDialog(history_service.history(tracking_item_id),self);dialog.exec();return dialog

    def submit_selected_workflow(self,event_type,service,tracking_item_id,actor_user_id,actor_display_name):
        dialog=WorkflowActionDialog(self.workflow_buttons[event_type].text(),event_type!="GENERAL_REPORT",self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return None
        try:
            return service.submit(request_id=uuid4(),tracking_item_id=tracking_item_id,event_type=WorkflowEventType(event_type),quantity=dialog.quantity.text() or None,notes=dialog.notes.text() or None,actor_user_id=actor_user_id,actor_display_name=actor_display_name)
        except Exception as exc:
            QMessageBox.warning(self,"Không thể ghi sự kiện",str(exc));return None

    def show_summaries(self,rows):
        self.table.setRowCount(len(rows))
        for row,data in enumerate(rows):
            values=(data.get("tracking_code",""),data.get("qr_status",""),data.get("delivery_date",""),data.get("part_name",""),data.get("customer",""),data.get("order_code",""),data.get("target_quantity",""),f"QC {data.get('checked_quantity','0')} / NG {data.get('ng_quantity','0')}",data.get("packed_quantity","0"),data.get("delivered_quantity","0"),data.get("current_status",""),"Mở")
            for column,value in enumerate(values):
                cell=QTableWidgetItem(str(value));self.table.setItem(row,column,cell)
                if column==10 and value in self.STATUS_COLORS:cell.setBackground(__import__('PySide6.QtGui',fromlist=['QColor']).QColor(self.STATUS_COLORS[value]))
