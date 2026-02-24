"""PDF canvas: QGraphicsView that renders PDF pages and handles balloon placement."""
from __future__ import annotations

from enum import Enum, auto
from typing import Optional

import fitz  # PyMuPDF
from PyQt6.QtCore import pyqtSignal, Qt, QPointF, QRectF
from PyQt6.QtGui import QImage, QPainter, QPixmap, QTransform, QWheelEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
)

from app.balloon import BalloonData, BalloonItem
from app.utils import pdf_to_scene, scene_to_pdf


class ViewMode(Enum):
    NAVIGATE = auto()
    BALLOON  = auto()


_BASE_DPI   = 150          # render resolution (pixels per inch for display)
_POINTS_PER_INCH = 72.0


class PDFViewer(QGraphicsView):
    """Displays one PDF page at a time with zoom/pan.  Emits signals for balloon
    placement and passes balloon interactions back to the main window.
    """

    balloon_requested    = pyqtSignal(QPointF, int)   # pdf_point, page_index
    balloon_moved        = pyqtSignal(str, QPointF, QPointF)  # uid, new_center(pdf), new_target(pdf)
    balloon_deleted      = pyqtSignal(str)
    balloon_desc_changed = pyqtSignal(str, str)
    balloon_num_changed  = pyqtSignal(str, int)
    page_changed         = pyqtSignal(int, int)       # current, total
    zoom_changed         = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._doc: Optional[fitz.Document] = None
        self._pdf_path: str = ""
        self._current_page: int = 0
        self._zoom: float = 1.0          # view zoom (applied via QGraphicsView transform)
        self._page_height: float = 0.0   # PDF page height in points
        self._mode: ViewMode = ViewMode.NAVIGATE
        self._page_rotations: dict[int, int] = {}  # page_idx -> rotation degrees (0/90/180/270)

        # uid -> BalloonItem for the *current page only*
        self._balloon_items: dict[str, BalloonItem] = {}

        # All balloon data across all pages: uid -> BalloonData
        self._all_balloons: dict[str, BalloonData] = {}

        self._pixmap_item: Optional[QGraphicsPixmapItem] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_pdf(self, path: str):
        self._doc = fitz.open(path)
        self._pdf_path = path
        self._all_balloons.clear()
        self._page_rotations.clear()
        self._current_page = 0
        self._zoom = 1.0
        self._render_page(self._current_page)
        self.page_changed.emit(self._current_page, len(self._doc))
        self.zoom_changed.emit(self._zoom)

    def rotate_page_cw(self):
        """Rotate the current page 90° clockwise."""
        self._rotate_current(90)

    def rotate_page_ccw(self):
        """Rotate the current page 90° counter-clockwise."""
        self._rotate_current(-90)

    def _rotate_current(self, delta: int):
        idx = self._current_page
        current = self._page_rotations.get(idx, 0)
        self._page_rotations[idx] = (current + delta) % 360
        self._render_page(idx)

    def set_page(self, idx: int):
        if self._doc is None:
            return
        idx = max(0, min(idx, len(self._doc) - 1))
        self._current_page = idx
        self._render_page(idx)
        self.page_changed.emit(self._current_page, len(self._doc))

    def next_page(self):
        if self._doc:
            self.set_page(self._current_page + 1)

    def prev_page(self):
        if self._doc:
            self.set_page(self._current_page - 1)

    def set_mode(self, mode: ViewMode):
        self._mode = mode
        if mode == ViewMode.NAVIGATE:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)

    @property
    def mode(self) -> ViewMode:
        return self._mode

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def page_count(self) -> int:
        return len(self._doc) if self._doc else 0

    def zoom_in(self):
        self._apply_zoom(self._zoom * 1.25)

    def zoom_out(self):
        self._apply_zoom(self._zoom / 1.25)

    def fit_to_page(self):
        if self._pixmap_item is None:
            return
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        # Calculate the resulting zoom
        rect = self._pixmap_item.boundingRect()
        view_rect = self.viewport().rect()
        scale_x = view_rect.width() / rect.width() if rect.width() else 1
        scale_y = view_rect.height() / rect.height() if rect.height() else 1
        self._zoom = min(scale_x, scale_y)
        self._update_balloon_scales()
        self.zoom_changed.emit(self._zoom)

    def fit_to_width(self):
        if self._pixmap_item is None:
            return
        rect = self._pixmap_item.boundingRect()
        view_rect = self.viewport().rect()
        scale = view_rect.width() / rect.width() if rect.width() else 1
        self._apply_zoom(scale)

    # Balloon management (called by MainWindow)

    def add_balloon(self, data: BalloonData):
        self._all_balloons[data.uid] = data
        if data.page == self._current_page:
            self._add_item(data)

    def remove_balloon(self, uid: str):
        self._all_balloons.pop(uid, None)
        item = self._balloon_items.pop(uid, None)
        if item:
            self._scene.removeItem(item)

    def update_balloon(self, data: BalloonData):
        self._all_balloons[data.uid] = data
        item = self._balloon_items.get(data.uid)
        if item:
            item._data = data
            item.update()

    def all_balloons(self) -> list[BalloonData]:
        return list(self._all_balloons.values())

    def scroll_to_balloon(self, uid: str):
        data = self._all_balloons.get(uid)
        if not data:
            return
        if data.page != self._current_page:
            self.set_page(data.page)
        item = self._balloon_items.get(uid)
        if item:
            self.centerOn(item)
            self._scene.clearSelection()
            item.setSelected(True)

    def clear_all_balloons(self):
        for uid, item in list(self._balloon_items.items()):
            self._scene.removeItem(item)
        self._balloon_items.clear()
        self._all_balloons.clear()

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _render_page(self, page_idx: int):
        # Remove existing balloon items from scene (they stay in _all_balloons)
        for item in self._balloon_items.values():
            self._scene.removeItem(item)
        self._balloon_items.clear()
        self._scene.clear()
        self._pixmap_item = None

        if self._doc is None:
            return

        page = self._doc[page_idx]
        rotation = self._page_rotations.get(page_idx, 0)

        # Render at BASE_DPI with rotation applied
        scale = _BASE_DPI / _POINTS_PER_INCH
        mat = fitz.Matrix(scale, scale).prerotate(rotation)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # After rotation, width/height may be swapped
        if rotation in (90, 270):
            self._page_height = page.rect.width
        else:
            self._page_height = page.rect.height

        img = QImage(pix.samples, pix.width, pix.height,
                     pix.stride, QImage.Format.Format_RGB888)
        qpix = QPixmap.fromImage(img)

        self._pixmap_item = QGraphicsPixmapItem(qpix)
        # After rotation, the rendered pixmap dimensions may be swapped.
        # Use the actual pixmap dimensions to determine the scene rect size.
        if rotation in (90, 270):
            pt_w = page.rect.height
            pt_h = page.rect.width
        else:
            pt_w = page.rect.width
            pt_h = page.rect.height
        self._pixmap_item.setScale(1.0)  # will set transform below
        # Transform: pixmap px -> pdf pts
        px_to_pt = pt_w / pix.width
        self._pixmap_item.setTransform(QTransform().scale(px_to_pt, px_to_pt))
        self._scene.addItem(self._pixmap_item)
        self._scene.setSceneRect(QRectF(0, 0, pt_w, pt_h))

        # Apply current view zoom
        self.setTransform(QTransform().scale(self._zoom, self._zoom))

        # Re-add balloons for this page
        for data in self._all_balloons.values():
            if data.page == page_idx:
                self._add_item(data)

    def _add_item(self, data: BalloonData):
        item = BalloonItem(data, self._page_height, self._zoom)
        item.signals.moved.connect(self._on_balloon_moved)
        item.signals.deleted.connect(self.balloon_deleted)
        item.signals.description_changed.connect(self.balloon_desc_changed)
        item.signals.number_changed.connect(self.balloon_num_changed)
        self._scene.addItem(item)
        self._balloon_items[data.uid] = item

    # ------------------------------------------------------------------
    # Zoom helpers
    # ------------------------------------------------------------------

    def _apply_zoom(self, zoom: float):
        zoom = max(0.05, min(zoom, 20.0))
        self._zoom = zoom
        self.setTransform(QTransform().scale(zoom, zoom))
        self._update_balloon_scales()
        self.zoom_changed.emit(zoom)

    def _update_balloon_scales(self):
        for item in self._balloon_items.values():
            item.set_zoom(self._zoom)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_balloon_moved(self, uid: str, new_center: QPointF, new_target: QPointF):
        if uid in self._all_balloons:
            self._all_balloons[uid].balloon_center = new_center
        self.balloon_moved.emit(uid, new_center, new_target)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            self._apply_zoom(self._zoom * factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if (self._mode == ViewMode.BALLOON and
                event.button() == Qt.MouseButton.LeftButton and
                self._doc is not None):
            # Map viewport coords -> scene coords -> PDF coords
            scene_pt = self.mapToScene(event.pos())
            pdf_pt = scene_to_pdf(scene_pt, self._page_height)
            # Balloon circle offset: 50 pts up-right from click point
            offset = QPointF(40, 40)
            center_scene = QPointF(scene_pt.x() + offset.x(),
                                   scene_pt.y() - offset.y())
            center_pdf = scene_to_pdf(center_scene, self._page_height)
            # We emit the target (click) point; MainWindow will build BalloonData
            self.balloon_requested.emit(pdf_pt, self._current_page)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete:
            for item in self._scene.selectedItems():
                if isinstance(item, BalloonItem):
                    self.balloon_deleted.emit(item.uid)
        super().keyPressEvent(event)
