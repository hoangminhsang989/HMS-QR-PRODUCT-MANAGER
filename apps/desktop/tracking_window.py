from uuid import uuid4
from datetime import date
from calendar import monthrange
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QMessageBox
from packages.domain.workflow import WorkflowEventType
from packages.domain.product import format_quantity
from apps.design_tokens import PY_SIDE_THEME, STATUS_COLORS

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
    STATUS_COLORS=STATUS_COLORS
    def __init__(self,workflow_actions=None,workflow_context=None,summary_rows=None):
        self._stage5_theme = PY_SIDE_THEME
        super().__init__();self.setWindowTitle("HMS QR — Theo dõi đơn hàng và QR");self.resize(1050,650);self.setStyleSheet("QWidget{background:#18212b;color:#eef4fa} QPushButton{background:#177e70;padding:8px}")
        self.selected_delivery_date=date.today()
        self._summary_rows=[]
        root=QWidget();layout=QVBoxLayout(root);layout.addWidget(QLabel("TRACKING ITEM / QR / GIA CÔNG / QC / ĐÓNG GÓI / GIAO HÀNG"))
        layout.addWidget(self._delivery_date_navigator())
        table=QTableWidget(0,12);table.setHorizontalHeaderLabels(["Mã theo dõi","QR","Ngày giao","Sản phẩm","Khách hàng","Mã sản phẩm","Số lượng","QC / NG","Đã đóng gói","Đã giao","Trạng thái","Lịch sử"]);layout.addWidget(table)
        for text in ("TẠO QR","XEM QR","IN / XUẤT QR","ĐỔI NGÀY GIAO HÀNG","TẠO ĐƠN MỚI"):
            button=QPushButton(text);layout.addWidget(button)
        action_row=QHBoxLayout();self.workflow_buttons={}
        for code,text in (("QC_CHECKED","ĐÃ KIỂM TRA"),("SHORTAGE_REPORTED","THIẾU HÀNG"),("QC_NG_RETURNED_TO_MACHINING","NG"),("PACKED","ĐÃ ĐÓNG GÓI"),("DELIVERED","ĐÃ GIAO HÀNG"),("GENERAL_REPORT","BÁO CÁO")):
            button=QPushButton(text);self.workflow_buttons[code]=button;action_row.addWidget(button)
            if workflow_actions and code in workflow_actions:button.clicked.connect(workflow_actions[code])
        layout.addLayout(action_row)
        bottom_row=QHBoxLayout()
        history_button=QPushButton("MỞ LỊCH SỬ TRACKING ITEM")
        bottom_row.addWidget(history_button)
        if workflow_actions and "HISTORY" in workflow_actions:history_button.clicked.connect(workflow_actions["HISTORY"])
        copy_excel_btn=QPushButton("📋 COPY BẢNG SANG EXCEL")
        copy_excel_btn.clicked.connect(self.copy_table_to_excel)
        bottom_row.addWidget(copy_excel_btn)
        layout.addLayout(bottom_row)
        self.table=table;self.history_button=history_button;self.setCentralWidget(root)
        # Apply the canonical Stage 5 theme after all widgets are constructed.
        # This keeps the existing workflow wiring intact while aligning the
        # desktop shell with apps.design_tokens.PY_SIDE_THEME.
        self.setStyleSheet(self._stage5_theme)
        if workflow_context:self.bind_workflow_context(**workflow_context)
        if summary_rows is not None:self.show_summaries(summary_rows)

    def _delivery_date_navigator(self):
        navigator=QWidget();layout=QVBoxLayout(navigator);layout.setContentsMargins(0,0,0,0);layout.setSpacing(3)
        self.delivery_date_labels={}
        for unit,title in (("year","NĂM"),("month","THÁNG"),("day","NGÀY")):
            row=QHBoxLayout();previous=QPushButton("◀");previous.setObjectName(f"delivery_{unit}_previous");previous.setFixedWidth(42);previous.clicked.connect(lambda _checked=False,u=unit:self.change_delivery_date(u,-1));row.addWidget(previous)
            label=QLabel();label.setObjectName(f"delivery_{unit}_label");label.setAlignment(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.AlignmentFlag.AlignCenter);self.delivery_date_labels[unit]=label;row.addWidget(label,1)
            following=QPushButton("▶");following.setObjectName(f"delivery_{unit}_next");following.setFixedWidth(42);following.clicked.connect(lambda _checked=False,u=unit:self.change_delivery_date(u,1));row.addWidget(following);layout.addLayout(row)
        self._update_delivery_date_labels()
        return navigator

    def _update_delivery_date_labels(self):
        selected=self.selected_delivery_date
        self.delivery_date_labels["year"].setText(str(selected.year))
        self.delivery_date_labels["month"].setText(f"THÁNG {selected.month}")
        self.delivery_date_labels["day"].setText(str(selected.day))

    def change_delivery_date(self,unit,step):
        selected=self.selected_delivery_date
        if unit=="year":
            year=selected.year+step
            self.selected_delivery_date=selected.replace(year=year,day=min(selected.day,monthrange(year,selected.month)[1]))
        elif unit=="month":
            month_index=selected.year*12+selected.month-1+step
            year,month=divmod(month_index,12);month+=1
            self.selected_delivery_date=selected.replace(year=year,month=month,day=min(selected.day,monthrange(year,month)[1]))
        else:
            self.selected_delivery_date=date.fromordinal(selected.toordinal()+step)
        self._update_delivery_date_labels()
        self._render_summaries()

    @staticmethod
    def _delivery_date_matches(value,selected):
        return str(value or "").split("T",1)[0]==selected.isoformat()

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

    def copy_table_to_excel(self):
        from PySide6.QtWidgets import QApplication
        row_count = self.table.rowCount()
        col_count = self.table.columnCount()
        if row_count == 0:
            QMessageBox.information(self, "Thông báo", "Không có dữ liệu trong bảng để copy.")
            return
        headers = [self.table.horizontalHeaderItem(c).text() for c in range(col_count)]
        tsv_lines = ["\t".join(headers)]
        for r in range(row_count):
            row_vals = []
            for c in range(col_count):
                item = self.table.item(r, c)
                row_vals.append(item.text() if item else "")
            tsv_lines.append("\t".join(row_vals))
        QApplication.clipboard().setText("\r\n".join(tsv_lines))
        QMessageBox.information(self, "Đã sao chép", f"Đã copy {row_count} dòng bảng vào Clipboard!\nBạn có thể mở Excel và bấm Ctrl+V.")

    def show_summaries(self,rows):
        self._summary_rows=list(rows)
        self._render_summaries()

    def _render_summaries(self):
        rows=[data for data in self._summary_rows if self._delivery_date_matches(data.get("delivery_date"),self.selected_delivery_date)]
        self.table.setRowCount(len(rows))
        for row,data in enumerate(rows):
            values=(data.get("tracking_code",""),data.get("qr_status",""),data.get("delivery_date",""),data.get("part_name",""),data.get("customer",""),data.get("product_code",""),data.get("target_quantity",""),f"QC {data.get('checked_quantity','0')} / NG {data.get('ng_quantity','0')}",data.get("packed_quantity","0"),data.get("delivered_quantity","0"),data.get("current_status",""),"Mở")
            for column,value in enumerate(values):
                cell=QTableWidgetItem(str(value));self.table.setItem(row,column,cell)
                if column==10 and value in self.STATUS_COLORS:cell.setBackground(__import__('PySide6.QtGui',fromlist=['QColor']).QColor(self.STATUS_COLORS[value]))
