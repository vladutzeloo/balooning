"""Main application window: menus, toolbar, undo stack, wiring."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, Qt, QSize
from PyQt6.QtGui import QAction, QKeySequence, QUndoStack, QUndoCommand, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar, QLabel, QFileDialog,
    QMessageBox, QPushButton, QWidget, QSizePolicy, QSpinBox,
    QComboBox, QDoubleSpinBox,
)

from app.balloon import BalloonData
from app.balloon_table import BalloonTableWidget
from app.gdt_panel import GDTPanelWidget
from app.pdf_viewer import PDFViewer, ViewMode
from app.exporter import export_pdf, export_csv, export_excel


# ---------------------------------------------------------------------------
# Undo commands
# ---------------------------------------------------------------------------

class PlaceBalloonCommand(QUndoCommand):
    def __init__(self, window: "MainWindow", data: BalloonData):
        super().__init__(f"Place balloon #{data.number}")
        self._win = window
        self._data = data

    def redo(self):
        self._win._do_add_balloon(self._data)

    def undo(self):
        self._win._do_remove_balloon(self._data.uid)


class DeleteBalloonCommand(QUndoCommand):
    def __init__(self, window: "MainWindow", data: BalloonData):
        super().__init__(f"Delete balloon #{data.number}")
        self._win = window
        self._data = data

    def redo(self):
        self._win._do_remove_balloon(self._data.uid)

    def undo(self):
        self._win._do_add_balloon(self._data)


class MoveBalloonCommand(QUndoCommand):
    def __init__(self, window: "MainWindow", uid: str,
                 old_center: QPointF, new_center: QPointF,
                 old_target: QPointF, new_target: QPointF):
        super().__init__("Move balloon")
        self._win = window
        self._uid = uid
        self._old_center = old_center
        self._new_center = new_center
        self._old_target = old_target
        self._new_target = new_target

    def redo(self):
        self._win._do_move_balloon(self._uid, self._new_center, self._new_target)

    def undo(self):
        self._win._do_move_balloon(self._uid, self._old_center, self._old_target)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Ballooner")
        self.resize(1280, 900)

        self._undo_stack = QUndoStack(self)
        self._pdf_path: str = ""
        self._balloons: dict[str, BalloonData] = {}
        self._move_origin: dict[str, tuple[QPointF, QPointF]] = {}

        # Currently selected balloon (for the GD&T description builder)
        self._selected_balloon_uid: str = ""

        # Balloon style defaults for newly placed balloons
        self._default_style: str = "default"
        self._default_diameter: float = 36.0
        self._default_font_size: float = 0.0  # 0 = auto

        # -- Central viewer --
        self._viewer = PDFViewer(self)
        self.setCentralWidget(self._viewer)

        # -- Right dock: balloon table --
        self._table = BalloonTableWidget(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._table)

        # -- Left dock: GD&T description builder --
        self._gdt_panel = GDTPanelWidget(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._gdt_panel)

        # -- Status bar --
        self._status_page  = QLabel("No file open")
        self._status_zoom  = QLabel("Zoom: 100%")
        self._status_count = QLabel("Balloons: 0")
        sb = QStatusBar()
        sb.addWidget(self._status_page)
        sb.addPermanentWidget(self._status_zoom)
        sb.addPermanentWidget(self._status_count)
        self.setStatusBar(sb)

        self._build_menus()
        self._build_toolbar()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Menu / Toolbar
    # ------------------------------------------------------------------

    def _build_menus(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        self._act_open = QAction("&Open PDF…", self, shortcut="Ctrl+O")
        self._act_open.triggered.connect(self.open_pdf)
        file_menu.addAction(self._act_open)

        self._act_save = QAction("&Export Ballooned PDF…", self, shortcut="Ctrl+S")
        self._act_save.triggered.connect(self.export_pdf)
        file_menu.addAction(self._act_save)

        self._act_csv = QAction("Export Balloon &List (CSV)…", self)
        self._act_csv.triggered.connect(self.export_csv)
        file_menu.addAction(self._act_csv)

        self._act_excel = QAction("Export &Inspection Sheet (Excel)…", self)
        self._act_excel.triggered.connect(self.export_excel_sheet)
        file_menu.addAction(self._act_excel)

        self._act_save_session = QAction("Save &Session…", self, shortcut="Ctrl+Shift+S")
        self._act_save_session.triggered.connect(self.save_session)
        file_menu.addAction(self._act_save_session)

        self._act_load_session = QAction("&Load Session…", self)
        self._act_load_session.triggered.connect(self.load_session)
        file_menu.addAction(self._act_load_session)

        file_menu.addSeparator()
        file_menu.addAction(QAction("&Quit", self, shortcut="Ctrl+Q",
                                    triggered=self.close))

        # Edit
        edit_menu = mb.addMenu("&Edit")
        undo_act = self._undo_stack.createUndoAction(self, "&Undo")
        undo_act.setShortcut("Ctrl+Z")
        redo_act = self._undo_stack.createRedoAction(self, "&Redo")
        redo_act.setShortcut("Ctrl+Shift+Z")
        edit_menu.addAction(undo_act)
        edit_menu.addAction(redo_act)
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("&Renumber All Balloons", self,
                                     triggered=self._renumber_balloons))

        # View
        view_menu = mb.addMenu("&View")
        view_menu.addAction(QAction("Zoom &In", self, shortcut="Ctrl++",
                                     triggered=self._viewer.zoom_in))
        view_menu.addAction(QAction("Zoom &Out", self, shortcut="Ctrl+-",
                                     triggered=self._viewer.zoom_out))
        view_menu.addAction(QAction("&Fit to Page", self, shortcut="Ctrl+0",
                                     triggered=self._viewer.fit_to_page))
        view_menu.addAction(QAction("Fit to &Width", self,
                                     triggered=self._viewer.fit_to_width))
        view_menu.addSeparator()
        view_menu.addAction(QAction("Rotate Page &Clockwise", self, shortcut="Ctrl+]",
                                     triggered=self._viewer.rotate_page_cw))
        view_menu.addAction(QAction("Rotate Page &Counter-Clockwise", self, shortcut="Ctrl+[",
                                     triggered=self._viewer.rotate_page_ccw))

        # Tools
        tools_menu = mb.addMenu("&Tools")
        self._act_nav_mode = QAction("&Navigate Mode", self, checkable=True,
                                      shortcut="Escape")
        self._act_nav_mode.setChecked(True)
        self._act_nav_mode.triggered.connect(lambda: self._set_mode(ViewMode.NAVIGATE))
        tools_menu.addAction(self._act_nav_mode)

        self._act_bal_mode = QAction("&Balloon Mode", self, checkable=True,
                                      shortcut="B")
        self._act_bal_mode.triggered.connect(lambda: self._set_mode(ViewMode.BALLOON))
        tools_menu.addAction(self._act_bal_mode)

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        tb.addAction(self._act_open)
        tb.addAction(self._act_save)
        tb.addSeparator()

        tb.addAction(QAction("−", self, triggered=self._viewer.zoom_out))
        tb.addAction(QAction("+", self, triggered=self._viewer.zoom_in))
        tb.addAction(QAction("Fit", self, triggered=self._viewer.fit_to_page))
        tb.addSeparator()

        tb.addAction(QAction("◄", self, triggered=self._viewer.prev_page))
        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setMaximum(1)
        self._page_spin.setFixedWidth(55)
        self._page_spin.valueChanged.connect(lambda v: self._viewer.set_page(v - 1))
        tb.addWidget(self._page_spin)
        tb.addAction(QAction("►", self, triggered=self._viewer.next_page))
        tb.addSeparator()

        tb.addAction(QAction("↻ CW", self, triggered=self._viewer.rotate_page_cw))
        tb.addAction(QAction("↺ CCW", self, triggered=self._viewer.rotate_page_ccw))
        tb.addSeparator()

        self._mode_btn = QPushButton("Mode: Navigate")
        self._mode_btn.setCheckable(True)
        self._mode_btn.setFixedWidth(130)
        self._mode_btn.toggled.connect(self._on_mode_btn_toggled)
        tb.addWidget(self._mode_btn)

        # --- Balloon options toolbar ---
        opt_tb = QToolBar("Balloon Options")
        opt_tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, opt_tb)

        opt_tb.addWidget(QLabel("  Style: "))
        self._style_combo = QComboBox()
        self._style_combo.addItems([
            "Default (white)",
            "Red filled circle",
            "Outline only",
            "Red circle, no arrow",
        ])
        self._style_combo.setFixedWidth(155)
        self._style_combo.currentIndexChanged.connect(self._on_style_changed)
        opt_tb.addWidget(self._style_combo)

        opt_tb.addWidget(QLabel("  Size: "))
        self._size_spin = QDoubleSpinBox()
        self._size_spin.setRange(4.0, 300.0)
        self._size_spin.setValue(36.0)
        self._size_spin.setSingleStep(2.0)
        self._size_spin.setDecimals(1)
        self._size_spin.setSuffix(" pt")
        self._size_spin.setFixedWidth(85)
        self._size_spin.valueChanged.connect(self._on_size_changed)
        opt_tb.addWidget(self._size_spin)

        opt_tb.addWidget(QLabel("  Font: "))
        self._font_spin = QDoubleSpinBox()
        self._font_spin.setRange(0.0, 100.0)
        self._font_spin.setValue(0.0)
        self._font_spin.setSingleStep(1.0)
        self._font_spin.setDecimals(1)
        self._font_spin.setSpecialValueText("Auto")
        self._font_spin.setFixedWidth(80)
        self._font_spin.valueChanged.connect(self._on_font_size_changed)
        opt_tb.addWidget(self._font_spin)

        opt_tb.addSeparator()
        opt_tb.addAction(QAction("Renumber", self,
                                  triggered=self._renumber_balloons))

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._viewer.balloon_requested.connect(self._on_balloon_requested)
        self._viewer.balloon_moved.connect(self._on_balloon_moved)
        self._viewer.balloon_deleted.connect(self._on_balloon_deleted)
        self._viewer.balloon_desc_changed.connect(self._on_balloon_desc_changed)
        self._viewer.balloon_num_changed.connect(self._on_balloon_num_changed)
        self._viewer.page_changed.connect(self._on_page_changed)
        self._viewer.zoom_changed.connect(self._on_zoom_changed)

        self._table.balloon_selected.connect(self._viewer.scroll_to_balloon)
        self._table.balloon_selected.connect(self._on_balloon_selected)
        self._table.description_changed.connect(self._on_balloon_desc_changed)

        self._gdt_panel.apply_description.connect(self._on_gdt_apply)

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------

    def _set_mode(self, mode: ViewMode):
        self._viewer.set_mode(mode)
        is_balloon = mode == ViewMode.BALLOON
        self._mode_btn.setChecked(is_balloon)
        self._mode_btn.setText("Mode: Balloon" if is_balloon else "Mode: Navigate")
        self._act_nav_mode.setChecked(not is_balloon)
        self._act_bal_mode.setChecked(is_balloon)

    def _on_mode_btn_toggled(self, checked: bool):
        self._set_mode(ViewMode.BALLOON if checked else ViewMode.NAVIGATE)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if not path:
            return
        self._pdf_path = path
        self._balloons.clear()
        self._selected_balloon_uid = ""
        self._gdt_panel.clear_selection()
        self._undo_stack.clear()
        self._table.clear_all()
        self._viewer.load_pdf(path)
        self.setWindowTitle(f"PDF Ballooner — {Path(path).name}")

        sidecar = Path(path).with_suffix(".balloons.json")
        if sidecar.exists():
            reply = QMessageBox.question(
                self, "Load Session",
                f"Found balloon session file:\n{sidecar}\n\nLoad it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._load_sidecar(sidecar)

    def export_pdf(self):
        if not self._pdf_path:
            QMessageBox.warning(self, "No PDF", "Open a PDF first.")
            return
        default = str(Path(self._pdf_path).with_stem(
            Path(self._pdf_path).stem + "_ballooned"
        ))
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Ballooned PDF", default, "PDF Files (*.pdf)"
        )
        if not path:
            return
        try:
            export_pdf(self._pdf_path, path, list(self._balloons.values()))
            QMessageBox.information(self, "Done", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def export_csv(self):
        if not self._balloons:
            QMessageBox.information(self, "No Balloons", "No balloons to export.")
            return
        default = str(Path(self._pdf_path).with_suffix(".csv")) if self._pdf_path else "balloons.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Balloon List", default, "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            export_csv(path, list(self._balloons.values()))
            QMessageBox.information(self, "Done", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def export_excel_sheet(self):
        if not self._balloons:
            QMessageBox.information(self, "No Balloons", "No balloons to export.")
            return
        default = str(Path(self._pdf_path).with_suffix(".xlsx")) if self._pdf_path else "inspection.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Inspection Sheet", default, "Excel Files (*.xlsx)"
        )
        if not path:
            return
        try:
            drawing_name = Path(self._pdf_path).stem if self._pdf_path else ""
            export_excel(path, list(self._balloons.values()), drawing_name)
            QMessageBox.information(self, "Done", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def save_session(self):
        if not self._pdf_path:
            QMessageBox.warning(self, "No PDF", "Open a PDF first.")
            return
        default = str(Path(self._pdf_path).with_suffix(".balloons.json"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session", default, "JSON Files (*.json)"
        )
        if not path:
            return
        data = {
            "pdf": self._pdf_path,
            "balloons": [b.to_dict() for b in self._balloons.values()],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        QMessageBox.information(self, "Saved", f"Session saved to:\n{path}")

    def load_session(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Session", "", "JSON Files (*.json)"
        )
        if not path:
            return
        self._load_sidecar(Path(path))

    def _load_sidecar(self, path: Path):
        try:
            with open(path) as f:
                raw = json.load(f)
            for d in raw.get("balloons", []):
                data = BalloonData.from_dict(d)
                self._do_add_balloon(data)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    # ------------------------------------------------------------------
    # Balloon operations
    # ------------------------------------------------------------------

    def _do_add_balloon(self, data: BalloonData):
        self._balloons[data.uid] = data
        self._viewer.add_balloon(data)
        self._table.add_balloon(data)
        self._update_count()

    def _do_remove_balloon(self, uid: str):
        if uid == self._selected_balloon_uid:
            self._selected_balloon_uid = ""
            self._gdt_panel.clear_selection()
        self._balloons.pop(uid, None)
        self._viewer.remove_balloon(uid)
        self._table.remove_balloon(uid)
        self._update_count()

    def _do_move_balloon(self, uid: str, new_center: QPointF, new_target: QPointF):
        data = self._balloons.get(uid)
        if not data:
            return
        data.balloon_center = new_center
        data.target_point = new_target
        self._viewer.update_balloon(data)
        self._table.update_balloon(data)

    # ------------------------------------------------------------------
    # Numbering helpers
    # ------------------------------------------------------------------

    def _next_free_number(self) -> int:
        """Return the lowest positive integer not currently used by any balloon."""
        used = {b.number for b in self._balloons.values()}
        n = 1
        while n in used:
            n += 1
        return n

    def _renumber_balloons(self):
        """Renumber all balloons sequentially sorted by page → top-to-bottom."""
        if not self._balloons:
            return
        sorted_bs = sorted(
            self._balloons.values(),
            key=lambda b: (b.page, -b.balloon_center.y(), b.balloon_center.x()),
        )
        for i, b in enumerate(sorted_bs, 1):
            b.number = i
            item = self._viewer._balloon_items.get(b.uid)
            if item:
                item.set_number(i)
        # Rebuild table in one pass
        self._table.clear_all()
        for b in sorted(self._balloons.values(), key=lambda b: (b.page, b.number)):
            self._table.add_balloon(b)
        # Refresh GD&T panel if the renumbered balloon is selected
        if self._selected_balloon_uid:
            data = self._balloons.get(self._selected_balloon_uid)
            if data:
                self._gdt_panel.set_balloon(data.number, data.description)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_style_changed(self, idx: int):
        styles = ["default", "red", "outline", "no_arrow"]
        self._default_style = styles[idx]

    def _on_size_changed(self, value: float):
        self._default_diameter = value

    def _on_font_size_changed(self, value: float):
        self._default_font_size = value

    def _on_balloon_requested(self, target_pdf: QPointF, page: int):
        # For no-arrow style the circle sits exactly at the click point.
        # For styles with a leader the circle is offset so the arrow has room.
        if self._default_style == "no_arrow":
            center_pdf = target_pdf
        else:
            center_pdf = QPointF(target_pdf.x() + 40, target_pdf.y() + 40)
        data = BalloonData(
            number=self._next_free_number(),
            page=page,
            target_point=target_pdf,
            balloon_center=center_pdf,
            diameter=self._default_diameter,
            style=self._default_style,
            font_size_override=self._default_font_size,
        )
        cmd = PlaceBalloonCommand(self, data)
        self._undo_stack.push(cmd)

    def _on_balloon_moved(self, uid: str, new_center: QPointF, new_target: QPointF):
        data = self._balloons.get(uid)
        if data:
            self._table.update_balloon(data)

    def _on_balloon_deleted(self, uid: str):
        data = self._balloons.get(uid)
        if not data:
            return
        cmd = DeleteBalloonCommand(self, data)
        self._undo_stack.push(cmd)

    def _on_balloon_desc_changed(self, uid: str, desc: str):
        data = self._balloons.get(uid)
        if data:
            data.description = desc
            self._table.update_balloon(data)
            # Keep GD&T panel in sync if this balloon is selected
            if uid == self._selected_balloon_uid:
                self._gdt_panel.set_balloon(data.number, desc)

    def _on_balloon_num_changed(self, uid: str, num: int):
        data = self._balloons.get(uid)
        if data:
            data.number = num
            self._table.update_balloon(data)

    def _on_balloon_selected(self, uid: str):
        """Called when a balloon row is clicked in the table."""
        self._selected_balloon_uid = uid
        data = self._balloons.get(uid)
        if data:
            self._gdt_panel.set_balloon(data.number, data.description)

    def _on_gdt_apply(self, desc: str):
        """Apply the description from the GD&T builder to the selected balloon."""
        uid = self._selected_balloon_uid
        data = self._balloons.get(uid)
        if not data:
            return
        data.description = desc
        self._table.update_balloon(data)
        item = self._viewer._balloon_items.get(uid)
        if item:
            item.set_description(desc)

    def _on_page_changed(self, current: int, total: int):
        self._status_page.setText(f"Page {current + 1} / {total}")
        self._page_spin.blockSignals(True)
        self._page_spin.setMaximum(total)
        self._page_spin.setValue(current + 1)
        self._page_spin.blockSignals(False)

    def _on_zoom_changed(self, zoom: float):
        self._status_zoom.setText(f"Zoom: {int(zoom * 100)}%")

    def _update_count(self):
        self._status_count.setText(f"Balloons: {len(self._balloons)}")
