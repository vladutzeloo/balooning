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
    QGraphicsItem, QMenu, QInputDialog,
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
    diameter: float = 36.0        # PDF points (controls both on-screen & export size)
    style: str = "default"        # "default" | "red" | "outline" | "no_arrow"
    font_size_override: float = 0.0  # 0 = auto-size based on radius
    uid: str = field(default_factory=make_uid)

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "page": self.page,
            "target_point": [self.target_point.x(), self.target_point.y()],
            "balloon_center": [self.balloon_center.x(), self.balloon_center.y()],
            "description": self.description,
            "diameter": self.diameter,
            "style": self.style,
            "font_size_override": self.font_size_override,
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
            diameter=d.get("diameter", 36.0),
            style=d.get("style", "default"),
            font_size_override=d.get("font_size_override", 0.0),
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

ARROW_HEAD_SIZE = 6  # screen pixels


class BalloonItem(QGraphicsItem):
    """A self-contained balloon: circle + number label + leader line + arrowhead.

    The item lives in *scene* coordinates (PDF-point space after Y-flip).
    Its origin is the *balloon centre*.  The target point (arrow tip) is stored
    separately and drawn as an absolute scene position.

    Visual size is driven by ``data.diameter`` so the on-screen balloon
    matches the size that will be exported to PDF.
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

        self._scene_center = sc
        self._scene_target = st

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
        self.setScale(1.0 / self._zoom)

    # ------------------------------------------------------------------
    # Bounding rect (in local coords, before scale)
    # ------------------------------------------------------------------

    def _radius(self) -> float:
        """Radius in local/scene PDF-point units."""
        return self._data.diameter / 2.0

    def boundingRect(self) -> QRectF:
        r = self._radius()
        if self._data.style == "no_arrow":
            # No leader line — bounding rect is just the circle
            return QRectF(-r - 2, -r - 2, 2 * r + 4, 2 * r + 4)
        target_local = self._target_local()
        min_x = min(-r, target_local.x()) - ARROW_HEAD_SIZE
        min_y = min(-r, target_local.y()) - ARROW_HEAD_SIZE
        max_x = max(r, target_local.x()) + ARROW_HEAD_SIZE
        max_y = max(r, target_local.y()) + ARROW_HEAD_SIZE
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def _target_local(self) -> QPointF:
        return self._scene_target - self.pos()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._radius()
        style = self._data.style

        # Resolve colours and flags by style
        if style == "red":
            circle_fill = QColor("red")
            circle_border = QColor("black")
            text_color = QColor("white")
            leader_color = QColor("red")
            draw_leader = True
        elif style == "outline":
            circle_fill = None  # transparent
            circle_border = QColor("black")
            text_color = QColor("black")
            leader_color = QColor("red")
            draw_leader = True
        elif style == "no_arrow":
            circle_fill = None  # transparent
            circle_border = QColor("red")
            text_color = QColor("red")
            leader_color = QColor("red")
            draw_leader = False
        else:  # "default"
            circle_fill = None  # transparent
            circle_border = QColor("black")
            text_color = QColor("black")
            leader_color = QColor("red")
            draw_leader = True

        # --- Leader line + arrowhead ---
        if draw_leader:
            tl = self._target_local()
            pen = QPen(leader_color)
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLine(QPointF(0, 0), tl)
            self._draw_arrowhead(painter, QPointF(0, 0), tl, leader_color)

        # --- Circle ---
        if self.isSelected():
            border_pen = QPen(QColor("#0078d7"), 2)
        else:
            border_pen = QPen(circle_border, 2)
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        if circle_fill is None:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            painter.setBrush(QBrush(circle_fill))
        painter.drawEllipse(QPointF(0, 0), r, r)

        # --- Number ---
        if self._data.font_size_override > 0:
            font_size = max(1, int(self._data.font_size_override))
        else:
            font_size = max(6, int(r * 0.9))
        font = QFont("Arial", font_size)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(text_color))
        painter.drawText(
            QRectF(-r, -r, 2 * r, 2 * r),
            Qt.AlignmentFlag.AlignCenter,
            str(self._data.number),
        )

    def _draw_arrowhead(self, painter: QPainter, from_pt: QPointF, to_pt: QPointF,
                        color: QColor = None):
        if color is None:
            color = QColor("red")
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
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([to_pt, left, right]))

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._scene_center = self.pos()
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
        resize_action = menu.addAction("Resize…")

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
        elif action == resize_action:
            d, ok = QInputDialog.getDouble(
                None, "Resize balloon", "Diameter (pt):",
                self._data.diameter, 4.0, 300.0, 1,
            )
            if ok:
                self.prepareGeometryChange()
                self._data.diameter = d
                self.update()
