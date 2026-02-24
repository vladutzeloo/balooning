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
from app.pdf_viewer import PDFViewer, ViewMode
from app.exporter import export_pdf, export_csv


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
        self._next_balloon_number = 1
        self._pdf_path: str = ""
        self._balloons: dict[str, BalloonData] = {}   # uid -> data
        # For move undo: store position at mouse-press
        self._move_origin: dict[str, tuple[QPointF, QPointF]] = {}

        # Balloon style defaults (applied to newly placed balloons)
        self._default_style: str = "default"
        self._default_diameter: float = 20.0
        self._default_font_size: float = 0.0  # 0 = auto

        # -- Central viewer --
        self._viewer = PDFViewer(self)
        self.setCentralWidget(self._viewer)

        # -- Side panel --
        self._table = BalloonTableWidget(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._table)

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

        # Zoom controls
        tb.addAction(QAction("−", self, triggered=self._viewer.zoom_out))
        tb.addAction(QAction("+", self, triggered=self._viewer.zoom_in))
        tb.addAction(QAction("Fit", self, triggered=self._viewer.fit_to_page))
        tb.addSeparator()

        # Page navigation
        tb.addAction(QAction("◄", self, triggered=self._viewer.prev_page))
        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setMaximum(1)
        self._page_spin.setFixedWidth(55)
        self._page_spin.valueChanged.connect(
            lambda v: self._viewer.set_page(v - 1)
        )
        tb.addWidget(self._page_spin)
        tb.addAction(QAction("►", self, triggered=self._viewer.next_page))
        tb.addSeparator()

        # Rotation buttons
        tb.addAction(QAction("↻ CW", self, triggered=self._viewer.rotate_page_cw))
        tb.addAction(QAction("↺ CCW", self, triggered=self._viewer.rotate_page_ccw))
        tb.addSeparator()

        # Mode button
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
        self._style_combo.addItems(["Default (white)", "Red circle", "Outline only"])
        self._style_combo.setFixedWidth(130)
        self._style_combo.currentIndexChanged.connect(self._on_style_changed)
        opt_tb.addWidget(self._style_combo)

        opt_tb.addWidget(QLabel("  Size: "))
        self._size_spin = QDoubleSpinBox()
        self._size_spin.setRange(6.0, 200.0)
        self._size_spin.setValue(20.0)
        self._size_spin.setSingleStep(2.0)
        self._size_spin.setDecimals(1)
        self._size_spin.setSuffix(" pt")
        self._size_spin.setFixedWidth(80)
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
        self._table.description_changed.connect(self._on_balloon_desc_changed)

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
        self._next_balloon_number = 1
        self._undo_stack.clear()
        self._table.clear_all()
        self._viewer.load_pdf(path)
        self.setWindowTitle(f"PDF Ballooner — {Path(path).name}")

        # Auto-load sidecar if present
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
        data = [b.to_dict() for b in self._balloons.values()]
        with open(path, "w") as f:
            json.dump({"pdf": self._pdf_path, "balloons": data}, f, indent=2)
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
                if data.number >= self._next_balloon_number:
                    self._next_balloon_number = data.number + 1
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    # ------------------------------------------------------------------
    # Balloon operations (called by undo commands and signals)
    # ------------------------------------------------------------------

    def _do_add_balloon(self, data: BalloonData):
        self._balloons[data.uid] = data
        self._viewer.add_balloon(data)
        self._table.add_balloon(data)
        self._update_count()

    def _do_remove_balloon(self, uid: str):
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
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_style_changed(self, idx: int):
        styles = ["default", "red", "outline"]
        self._default_style = styles[idx]

    def _on_size_changed(self, value: float):
        self._default_diameter = value

    def _on_font_size_changed(self, value: float):
        self._default_font_size = value

    def _on_balloon_requested(self, target_pdf: QPointF, page: int):
        # Balloon circle is offset ~50 pts up-right from click
        center_pdf = QPointF(target_pdf.x() + 40, target_pdf.y() + 40)
        data = BalloonData(
            number=self._next_balloon_number,
            page=page,
            target_point=target_pdf,
            balloon_center=center_pdf,
            diameter=self._default_diameter,
            style=self._default_style,
            font_size_override=self._default_font_size,
        )
        self._next_balloon_number += 1
        cmd = PlaceBalloonCommand(self, data)
        self._undo_stack.push(cmd)

    def _on_balloon_moved(self, uid: str, new_center: QPointF, new_target: QPointF):
        data = self._balloons.get(uid)
        if not data:
            return
        # The viewer already updated its own copy; sync table
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

    def _on_balloon_num_changed(self, uid: str, num: int):
        data = self._balloons.get(uid)
        if data:
            data.number = num
            self._table.update_balloon(data)

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
