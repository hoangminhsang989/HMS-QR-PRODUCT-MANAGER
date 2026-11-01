"""HMS QR Stage 5 design tokens for the **desktop** (PySide6) surface.

These are the desktop tokens only. The web surfaces do not read this file:
``web/index.html`` declares its own ``:root`` block, which is the source of
truth for the mobile web and, since the portal was brought onto the same light
direction, for the portal too. The two palettes differ on purpose - see the
"Two surfaces, two token sets" section of DESIGN.md - so an agent editing one
surface must not "fix" it toward the other.

``PY_SIDE_THEME`` renders these names into a Qt stylesheet;
``STATUS_COLORS`` maps workflow states onto them. Every desktop window applies
``PY_SIDE_THEME``; status text is always rendered alongside its colour.
"""

TOKENS = {
    "background": "#f3f1ec",
    "surface": "#ffffff",
    "surface_raised": "#e7e8e8",
    "border": "#b8bdc1",
    "text_primary": "#333333",
    "text_secondary": "#555555",
    "text_disabled": "#777777",
    "accent": "#246b9c",
    "success": "#2f8f63",
    "warning": "#b7791f",
    "danger": "#c44747",
    "info": "#3b72a6",
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
QTableView, QTableWidget {{ background: {TOKENS['surface']}; alternate-background-color: #f0f1f2;
  color: {TOKENS['text_primary']}; gridline-color: {TOKENS['border']}; border: 1px solid {TOKENS['border']};
  selection-background-color: {TOKENS['accent']}; selection-color: #ffffff; }}
QHeaderView::section {{ background: {TOKENS['surface_raised']}; color: {TOKENS['text_secondary']}; padding: 7px; border: 0; }}
QTabBar::tab {{ background: {TOKENS['surface']}; color: {TOKENS['text_secondary']}; padding: 8px 14px; }} QTabBar::tab:selected {{ background: {TOKENS['accent']}; color: #ffffff; }}
"""
