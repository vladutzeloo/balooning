"""GD&T description builder panel.

This panel is used to compose balloon descriptions that contain GD&T symbols,
to be exported in the inspection sheet (CSV).  It is NOT for placing annotations
on the PDF drawing.

Workflow:
  1. Click a balloon in the table or on the canvas to select it.
  2. The panel loads that balloon's current description.
  3. Click GD&T symbol buttons to insert symbols at the cursor position.
  4. Type any additional text (tolerances, datum references, etc.).
  5. Click "Apply" to save the description back to the selected balloon.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QGridLayout, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
)

# (button label, symbol to insert, tooltip)
GDT_SYMBOLS = [
    ("⏤",  "⏤",  "Straightness"),
    ("⏥",  "⏥",  "Flatness"),
    ("○",   "○",   "Circularity"),
    ("⌭",  "⌭",  "Cylindricity"),
    ("⌒",  "⌒",  "Profile of a Line"),
    ("⌓",  "⌓",  "Profile of a Surface"),
    ("⊥",  "⊥",  "Perpendicularity"),
    ("∠",  "∠",  "Angularity"),
    ("∥",  "∥",  "Parallelism"),
    ("⊕",  "⊕",  "True Position"),
    ("◎",  "◎",  "Concentricity"),
    ("⌯",  "⌯",  "Symmetry"),
    ("⌀",  "⌀",  "Diameter"),
    ("Ⓜ",  "Ⓜ",  "Max Material Condition"),
    ("Ⓛ",  "Ⓛ",  "Least Material Condition"),
    ("Ⓢ",  "Ⓢ",  "Regardless of Feature Size"),
    ("±",   "±",   "Bilateral Tolerance"),
    ("▽",  "▽",  "Datum Feature"),
]

_COLS = 3


class GDTPanelWidget(QDockWidget):
    """Description builder: compose GD&T descriptions for balloons."""

    # Emitted when the user clicks Apply; carries the new description text.
    apply_description = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("GD&T Description Builder", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )

        w = QWidget()
        vlay = QVBoxLayout(w)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        # Which balloon is currently loaded
        self._balloon_label = QLabel("No balloon selected")
        self._balloon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._balloon_label.font()
        font.setBold(True)
        self._balloon_label.setFont(font)
        vlay.addWidget(self._balloon_label)

        # Text area for building the description
        self._desc_edit = QPlainTextEdit()
        self._desc_edit.setPlaceholderText("Select a balloon, then type or click symbols…")
        self._desc_edit.setMaximumHeight(70)
        vlay.addWidget(self._desc_edit)

        # Apply / Clear buttons
        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("Apply to balloon")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._desc_edit.clear)
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(self._clear_btn)
        vlay.addLayout(btn_row)

        vlay.addWidget(QLabel("Insert GD&T symbol:"))

        # Symbol grid
        grid = QGridLayout()
        grid.setSpacing(2)
        btn_font = QFont("Arial", 12)
        for idx, (lbl, sym, tip) in enumerate(GDT_SYMBOLS):
            btn = QPushButton(lbl)
            btn.setFont(btn_font)
            btn.setToolTip(f"{tip}  ({sym})")
            btn.setFixedSize(38, 38)
            btn.clicked.connect(lambda _checked, s=sym: self._insert(s))
            grid.addWidget(btn, idx // _COLS, idx % _COLS)

        vlay.addLayout(grid)
        vlay.addStretch()
        self.setWidget(w)

    # ------------------------------------------------------------------
    # Public API (called by MainWindow)
    # ------------------------------------------------------------------

    def set_balloon(self, number: int, description: str):
        """Load a balloon's description into the editor."""
        self._balloon_label.setText(f"Editing: Balloon #{number}")
        self._desc_edit.setPlainText(description)
        self._apply_btn.setEnabled(True)

    def clear_selection(self):
        """Called when no balloon is selected."""
        self._balloon_label.setText("No balloon selected")
        self._apply_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _insert(self, symbol: str):
        """Insert symbol at the current cursor position in the text area."""
        cursor = self._desc_edit.textCursor()
        cursor.insertText(symbol)
        self._desc_edit.setFocus()

    def _on_apply(self):
        self.apply_description.emit(self._desc_edit.toPlainText())
