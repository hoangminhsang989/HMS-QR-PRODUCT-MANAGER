"""Canonical HMS QR Stage 5 design tokens shared by desktop and web UI."""

TOKENS = {
    "background": "#111923",
    "surface": "#1b2733",
    "surface_raised": "#243544",
    "border": "#3b5162",
    "text_primary": "#eef4f8",
    "text_secondary": "#a9bbc7",
    "text_disabled": "#6f808c",
    "accent": "#35b7a4",
    "success": "#2fb889",
    "warning": "#d39a3d",
    "danger": "#d56363",
    "info": "#5c9ed6",
}

SPACING = {"2": 2, "4": 4, "6": 6, "8": 8, "12": 12, "16": 16, "24": 24, "32": 32}

STATUS_COLORS = {
    "IN_PROCESS": TOKENS["info"], "WAITING_QC": TOKENS["warning"], "QC_CHECKED": TOKENS["success"],
    "QC_NG": TOKENS["danger"], "REWORK": TOKENS["danger"], "SHORTAGE": TOKENS["warning"],
    "PACKING": TOKENS["info"], "PACKED": TOKENS["success"], "PARTIALLY_DELIVERED": TOKENS["info"],
    "DELIVERED": TOKENS["success"], "HOLD": TOKENS["warning"],
}

PY_SIDE_THEME = f"""
QMainWindow, QWidget {{ background: {TOKENS['background']}; color: {TOKENS['text_primary']};
  font-family: 'Segoe UI'; font-size: 13px; }}
QLineEdit, QComboBox, QDateEdit, QSpinBox {{ background: {TOKENS['surface_raised']};
  color: {TOKENS['text_primary']}; border: 1px solid {TOKENS['border']}; border-radius: 4px; padding: 6px 8px; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{ border: 2px solid {TOKENS['accent']}; padding: 5px 7px; }}
QPushButton {{ background: {TOKENS['surface_raised']}; color: {TOKENS['text_primary']}; border: 1px solid {TOKENS['border']};
  border-radius: 4px; padding: 7px 12px; min-height: 28px; }}
QPushButton:hover {{ border-color: {TOKENS['accent']}; }} QPushButton:pressed {{ background: {TOKENS['accent']}; }}
QTableView, QTableWidget {{ background: {TOKENS['surface']}; alternate-background-color: #202f3c;
  color: {TOKENS['text_primary']}; gridline-color: {TOKENS['border']}; border: 1px solid {TOKENS['border']}; }}
QHeaderView::section {{ background: {TOKENS['surface_raised']}; color: {TOKENS['text_secondary']}; padding: 7px; border: 0; }}
QTabBar::tab {{ background: {TOKENS['surface']}; padding: 8px 14px; }} QTabBar::tab:selected {{ background: {TOKENS['accent']}; }}
"""

WEB_CSS_VARS = ":root{" + ";".join(f"--{k.replace('_','-')}:{v}" for k, v in TOKENS.items()) + "}"

