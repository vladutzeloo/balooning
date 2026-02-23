"""Balloon data model and QGraphicsItem."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, Qt, QRectF, pyqtSignal, QObject
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPen, QPainter, QPolygonF,
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsItemGroup, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsTextItem, QMenu, QInputDialog,
    QGraphicsSceneMouseEvent,
)

from app.utils import make_uid

if TYPE_CHECKING:
    from app.pdf_viewer import PDFViewer


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BalloonData:
    number: int
    page: int                     # 0-indexed
    target_point: QPointF         # PDF coords — where the arrow tip points
    balloon_center: QPointF       # PDF coords — centre of the circle
    description: str = ""
    diameter: float = 20.0        # PDF points
    uid: str = field(default_factory=make_uid)

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "page": self.page,
            "target_point": [self.target_point.x(), self.target_point.y()],
            "balloon_center": [self.balloon_center.x(), self.balloon_center.y()],
            "description": self.description,
            "diameter": self.diameter,
            "uid": self.uid,
        }

    @staticmethod
    def from_dict(d: dict) -> "BalloonData":
        return BalloonData(
            number=d["number"],
            page=d["page"],
            target_point=QPointF(*d["target_point"]),
            balloon_center=QPointF(*d["balloon_center"]),
            description=d.get("description", ""),
            diameter=d.get("diameter", 20.0),
            uid=d["uid"],
        )


# ---------------------------------------------------------------------------
# Signals companion (QGraphicsItem can't inherit QObject directly)
# ---------------------------------------------------------------------------

class BalloonSignals(QObject):
    moved = pyqtSignal(str, QPointF, QPointF)   # uid, new_balloon_center(pdf), new_target(pdf)
    deleted = pyqtSignal(str)                   # uid
    description_changed = pyqtSignal(str, str)  # uid, new_description
    number_changed = pyqtSignal(str, int)        # uid, new_number


# ---------------------------------------------------------------------------
# Graphics item
# ---------------------------------------------------------------------------

BALLOON_VISUAL_RADIUS_PX = 18   # visual radius in *screen* pixels at zoom=1
ARROW_HEAD_SIZE = 6              # pixels


class BalloonItem(QGraphicsItem):
    """A self-contained balloon: circle + number label + leader line + arrowhead.

    The item lives in *scene* coordinates (PDF-point space after Y-flip).
    Its origin is the *balloon centre*.  The target point (arrow tip) is stored
    separately and drawn as an absolute scene position.
    """

    def __init__(
        self,
        data: BalloonData,
        page_height: float,
        zoom: float = 1.0,
    ):
        super().__init__()
        self.signals = BalloonSignals()
        self._data = data
        self._page_height = page_height
        self._zoom = zoom

        # Scene coords (Y-flipped PDF coords)
        from app.utils import pdf_to_scene
        sc = pdf_to_scene(data.balloon_center, page_height)
        st = pdf_to_scene(data.target_point, page_height)

        self._scene_center = sc     # balloon circle centre in scene space
        self._scene_target = st     # arrow tip in scene space

        self.setPos(sc)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(10)

        self._update_scale()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def uid(self) -> str:
        return self._data.uid

    @property
    def data(self) -> BalloonData:
        return self._data

    def set_number(self, n: int):
        self._data.number = n
        self.update()

    def set_description(self, desc: str):
        self._data.description = desc

    def set_zoom(self, zoom: float):
        self._zoom = zoom
        self._update_scale()

    def _update_scale(self):
        # Scale item so balloon appears the same screen size at every zoom level
        self.setScale(1.0 / self._zoom)

    # ------------------------------------------------------------------
    # Bounding rect (in local coords, before scale)
    # ------------------------------------------------------------------

    def _radius(self) -> float:
        """Visual radius in scene points (pre-scale)."""
        return BALLOON_VISUAL_RADIUS_PX

    def boundingRect(self) -> QRectF:
        r = self._radius()
        # Include the leader line by computing offset to target in local coords
        target_local = self._target_local()
        min_x = min(-r, target_local.x()) - ARROW_HEAD_SIZE
        min_y = min(-r, target_local.y()) - ARROW_HEAD_SIZE
        max_x = max(r, target_local.x()) + ARROW_HEAD_SIZE
        max_y = max(r, target_local.y()) + ARROW_HEAD_SIZE
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def _target_local(self) -> QPointF:
        """Target point in this item's local coordinate space."""
        return self._scene_target - self.pos()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._radius()
        tl = self._target_local()

        # --- Leader line ---
        pen = QPen(QColor("red"))
        pen.setWidth(2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLine(QPointF(0, 0), tl)

        # Arrow head at target
        self._draw_arrowhead(painter, QPointF(0, 0), tl)

        # --- Circle ---
        if self.isSelected():
            pen = QPen(QColor("#0078d7"), 2)
        else:
            pen = QPen(QColor("black"), 2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor("white")))
        painter.drawEllipse(QPointF(0, 0), r, r)

        # --- Number ---
        font = QFont("Arial", int(r * 0.9))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("black")))
        painter.drawText(
            QRectF(-r, -r, 2 * r, 2 * r),
            Qt.AlignmentFlag.AlignCenter,
            str(self._data.number),
        )

    def _draw_arrowhead(self, painter: QPainter, from_pt: QPointF, to_pt: QPointF):
        dx = to_pt.x() - from_pt.x()
        dy = to_pt.y() - from_pt.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        s = ARROW_HEAD_SIZE
        left = QPointF(to_pt.x() - s * ux + s * 0.5 * uy,
                       to_pt.y() - s * uy - s * 0.5 * ux)
        right = QPointF(to_pt.x() - s * ux - s * 0.5 * uy,
                        to_pt.y() - s * uy + s * 0.5 * ux)
        painter.setBrush(QBrush(QColor("red")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([to_pt, left, right]))

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._scene_center = self.pos()
            # Update stored PDF coords
            from app.utils import scene_to_pdf
            self._data.balloon_center = scene_to_pdf(self.pos(), self._page_height)
            self.signals.moved.emit(
                self._data.uid,
                self._data.balloon_center,
                self._data.target_point,
            )
        return super().itemChange(change, value)

    def contextMenuEvent(self, event: QGraphicsSceneMouseEvent):
        menu = QMenu()
        delete_action = menu.addAction("Delete balloon")
        edit_number_action = menu.addAction("Edit number")
        edit_desc_action = menu.addAction("Edit description")

        action = menu.exec(event.screenPos())
        if action == delete_action:
            self.signals.deleted.emit(self._data.uid)
        elif action == edit_number_action:
            num, ok = QInputDialog.getInt(
                None, "Edit number", "Balloon number:",
                self._data.number, 1, 9999,
            )
            if ok:
                self._data.number = num
                self.signals.number_changed.emit(self._data.uid, num)
                self.update()
        elif action == edit_desc_action:
            desc, ok = QInputDialog.getText(
                None, "Edit description", "Description:",
                text=self._data.description,
            )
            if ok:
                self._data.description = desc
                self.signals.description_changed.emit(self._data.uid, desc)
