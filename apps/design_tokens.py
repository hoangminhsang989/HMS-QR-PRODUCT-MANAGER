"""HMS QR Stage 5 design tokens for the **desktop** (PySide6) surface.

These are the desktop tokens only. The web surfaces do not read this file:
``web/index.html`` declares its own ``:root`` block, which is the source of
truth for the mobile web and, since the portal was brought onto the same light
direction, for the portal too.

The two palettes differ, and DESIGN.md records that difference under the
"Known drift - recorded, not yet reconciled" section of DESIGN.md: the desktop
accent is blue where the web is teal, the desktop background is warm where the
web is cool. That drift is **not** a settled decision - DESIGN.md says
reconciling the two palettes into one token set is a product decision that has
not been taken. So an agent editing one surface must not "fix" it toward the
other, but must also not treat the difference as blessed.

``PY_SIDE_THEME`` renders these names into a Qt stylesheet;
``STATUS_COLORS`` maps every :class:`~packages.domain.product.ProductStatus`
member onto them. Every desktop window applies ``PY_SIDE_THEME``; status text is
always rendered alongside its colour, per DESIGN.md's status-mapping rule.

``tests/stage1/test_design_tokens.py`` enforces the two invariants that keep
this file honest: no colour reaches the Qt stylesheet except through ``TOKENS``,
and ``STATUS_COLORS`` names exactly the statuses that exist.
"""

TOKENS = {
    "background": "#f3f1ec",
    "surface": "#ffffff",
    "surface_raised": "#e7e8e8",
    "surface_alt": "#f0f1f2",
    "border": "#b8bdc1",
    "text_primary": "#333333",
    "text_secondary": "#555555",
    "text_disabled": "#777777",
    "accent": "#246b9c",
    "on_accent": "#ffffff",
    "success": "#2f8f63",
    "warning": "#b7791f",
    "danger": "#c44747",
    "info": "#3b72a6",
    "neutral": "#e4e4e4",
}

SPACING = {"2": 2, "4": 4, "6": 6, "8": 8, "12": 12, "16": 16, "24": 24, "32": 32}

# Keyed by ProductStatus member name, so a lookup by ``product.status`` cannot
# silently miss. It used to be keyed by names from an older status model
# (IN_PROCESS, QC_CHECKED, SHORTAGE, PACKING, PARTIALLY_DELIVERED) that
# ``ProductStatus`` no longer has, while five real statuses - NEW, WAITING,
# IN_PROGRESS, QC_PASS and CANCELLED - had no entry at all. The tracking
# window's ``value in STATUS_COLORS`` check therefore left five of the eleven
# statuses with no background colour, against DESIGN.md's rule that status is
# always text plus semantic colour. ``tests/stage1/test_design_tokens.py``
# now fails if the key set and the enum ever disagree again.
STATUS_COLORS = {
    "NEW": TOKENS["info"],
    "WAITING": TOKENS["warning"],
    "IN_PROGRESS": TOKENS["info"],
    "WAITING_QC": TOKENS["warning"],
    "QC_PASS": TOKENS["success"],
    "QC_NG": TOKENS["danger"],
    "REWORK": TOKENS["danger"],
    "PACKED": TOKENS["success"],
    "DELIVERED": TOKENS["success"],
    "HOLD": TOKENS["warning"],
    "CANCELLED": TOKENS["neutral"],
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
QTableView, QTableWidget {{ background: {TOKENS['surface']}; alternate-background-color: {TOKENS['surface_alt']};
  color: {TOKENS['text_primary']}; gridline-color: {TOKENS['border']}; border: 1px solid {TOKENS['border']};
  selection-background-color: {TOKENS['accent']}; selection-color: {TOKENS['on_accent']}; }}
QHeaderView::section {{ background: {TOKENS['surface_raised']}; color: {TOKENS['text_secondary']}; padding: 7px; border: 0; }}
QTabBar::tab {{ background: {TOKENS['surface']}; color: {TOKENS['text_secondary']}; padding: 8px 14px; }} QTabBar::tab:selected {{ background: {TOKENS['accent']}; color: {TOKENS['on_accent']}; }}
"""
