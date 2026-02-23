"""Dockable side panel showing the balloon table."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)

from app.balloon import BalloonData

_COL_NUM  = 0
_COL_PAGE = 1
_COL_X    = 2
_COL_Y    = 3
_COL_DESC = 4
_HEADERS  = ["#", "Page", "X", "Y", "Description"]


class BalloonTableWidget(QDockWidget):
    balloon_selected = pyqtSignal(str)          # uid
    description_changed = pyqtSignal(str, str)  # uid, new_description

    def __init__(self, parent=None):
        super().__init__("Balloon Table", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._balloons: dict[str, BalloonData] = {}   # uid -> data
        self._uid_for_row: list[str] = []              # row index -> uid

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_DESC, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_NUM, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_PAGE, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_X, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_Y, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked
        )
        self._table.verticalHeader().setVisible(False)
        self._table.cellClicked.connect(self._on_row_clicked)
        self._table.cellChanged.connect(self._on_cell_changed)

        layout.addWidget(self._table)
        self.setWidget(container)
        self.setMinimumWidth(280)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_balloon(self, data: BalloonData):
        self._balloons[data.uid] = data
        self._rebuild()

    def remove_balloon(self, uid: str):
        self._balloons.pop(uid, None)
        self._rebuild()

    def update_balloon(self, data: BalloonData):
        self._balloons[data.uid] = data
        self._rebuild()

    def clear_all(self):
        self._balloons.clear()
        self._rebuild()

    def select_balloon(self, uid: str):
        """Highlight the row corresponding to uid."""
        try:
            row = self._uid_for_row.index(uid)
        except ValueError:
            return
        self._table.selectRow(row)

    def all_balloons(self) -> list[BalloonData]:
        return sorted(self._balloons.values(), key=lambda b: (b.page, b.number))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild(self):
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        self._uid_for_row.clear()

        for data in sorted(self._balloons.values(), key=lambda b: (b.page, b.number)):
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._uid_for_row.append(data.uid)

            num_item = QTableWidgetItem(str(data.number))
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, _COL_NUM, num_item)

            page_item = QTableWidgetItem(str(data.page + 1))
            page_item.setFlags(page_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, _COL_PAGE, page_item)

            x_item = QTableWidgetItem(f"{data.balloon_center.x():.1f}")
            x_item.setFlags(x_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, _COL_X, x_item)

            y_item = QTableWidgetItem(f"{data.balloon_center.y():.1f}")
            y_item.setFlags(y_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, _COL_Y, y_item)

            desc_item = QTableWidgetItem(data.description)
            self._table.setItem(row, _COL_DESC, desc_item)

        self._table.blockSignals(False)

    def _on_row_clicked(self, row: int, col: int):
        if row < len(self._uid_for_row):
            self.balloon_selected.emit(self._uid_for_row[row])

    def _on_cell_changed(self, row: int, col: int):
        if col != _COL_DESC:
            return
        if row >= len(self._uid_for_row):
            return
        uid = self._uid_for_row[row]
        new_desc = self._table.item(row, col).text()
        if uid in self._balloons:
            self._balloons[uid].description = new_desc
            self.description_changed.emit(uid, new_desc)
