"""GD&T annotation: data model and QGraphicsItem."""
from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, Qt, QRectF, pyqtSignal, QObject
from PyQt6.QtGui import QBrush, QColor, QFont, QPen, QPainter
from PyQt6.QtWidgets import QGraphicsItem, QMenu

from app.utils import make_uid, pdf_to_scene, scene_to_pdf


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class GDTAnnotation:
    symbol: str
    page: int
    position: QPointF        # PDF coords (origin bottom-left, Y up)
    font_size: float = 16.0  # in PDF-point units
    uid: str = field(default_factory=make_uid)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "page": self.page,
            "position": [self.position.x(), self.position.y()],
            "font_size": self.font_size,
            "uid": self.uid,
        }

    @staticmethod
    def from_dict(d: dict) -> "GDTAnnotation":
        return GDTAnnotation(
            symbol=d["symbol"],
            page=d["page"],
            position=QPointF(*d["position"]),
            font_size=d.get("font_size", 16.0),
            uid=d["uid"],
        )


# ---------------------------------------------------------------------------
# Signals companion
# ---------------------------------------------------------------------------

class GDTSignals(QObject):
    moved   = pyqtSignal(str, QPointF)  # uid, new_position_pdf
    deleted = pyqtSignal(str)           # uid


# ---------------------------------------------------------------------------
# Graphics item
# ---------------------------------------------------------------------------

class GDTAnnotationItem(QGraphicsItem):
    """A movable GD&T symbol text box drawn on the PDF canvas."""

    _PAD = 4  # pixel padding around the symbol text

    def __init__(self, data: GDTAnnotation, page_height: float, zoom: float = 1.0):
        super().__init__()
        self.signals = GDTSignals()
        self._data = data
        self._page_height = page_height
        self._zoom = zoom

        sc = pdf_to_scene(data.position, page_height)
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
    def data(self) -> GDTAnnotation:
        return self._data

    def set_zoom(self, zoom: float):
        self._zoom = zoom
        self._update_scale()

    def _update_scale(self):
        self.setScale(1.0 / self._zoom)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def _box(self) -> QRectF:
        fs = self._data.font_size
        w = fs * max(1, len(self._data.symbol)) * 0.75 + self._PAD * 2
        h = fs + self._PAD * 2
        return QRectF(-w / 2, -h / 2, w, h)

    def boundingRect(self) -> QRectF:
        return self._box().adjusted(-1, -1, 1, 1)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = self._box()
        border = QColor("#0078d7") if self.isSelected() else QColor("#333")
        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(QColor(255, 255, 210)))
        painter.drawRect(box)

        font = QFont("Arial", int(self._data.font_size))
        painter.setFont(font)
        painter.setPen(QPen(QColor("black")))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, self._data.symbol)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._data.position = scene_to_pdf(self.pos(), self._page_height)
            self.signals.moved.emit(self._data.uid, self._data.position)
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        menu = QMenu()
        del_act = menu.addAction("Delete GD&T annotation")
        if menu.exec(event.screenPos()) == del_act:
            self.signals.deleted.emit(self._data.uid)
