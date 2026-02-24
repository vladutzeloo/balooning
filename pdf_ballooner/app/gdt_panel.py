"""GD&T symbols dock panel."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QGridLayout, QPushButton,
    QLabel, QVBoxLayout,
)

# (button label, symbol string to place, tooltip)
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
    """Dock panel: clicking a symbol activates GD&T placement mode."""

    symbol_selected = pyqtSignal(str)  # symbol string to place

    def __init__(self, parent=None):
        super().__init__("GD&T Symbols", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )

        w = QWidget()
        vlay = QVBoxLayout(w)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        hint = QLabel("Click a symbol, then\nclick on the PDF to place it.")
        hint.setWordWrap(True)
        vlay.addWidget(hint)

        grid = QGridLayout()
        grid.setSpacing(2)
        btn_font = QFont("Arial", 13)

        for idx, (lbl, sym, tip) in enumerate(GDT_SYMBOLS):
            btn = QPushButton(lbl)
            btn.setFont(btn_font)
            btn.setToolTip(f"{tip}  ({sym})")
            btn.setFixedSize(38, 38)
            btn.clicked.connect(lambda _checked, s=sym: self.symbol_selected.emit(s))
            grid.addWidget(btn, idx // _COLS, idx % _COLS)

        vlay.addLayout(grid)
        vlay.addStretch()
        self.setWidget(w)
