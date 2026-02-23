"""Coordinate transforms and shared helpers."""
from uuid import uuid4
from PyQt6.QtCore import QPointF


def make_uid() -> str:
    return str(uuid4())


def pdf_to_scene(pdf_pt: QPointF, page_height: float) -> QPointF:
    """Convert a PDF coordinate (origin bottom-left, Y up) to scene/screen
    coordinate (origin top-left, Y down).  No zoom factor — the scene itself
    is expressed in PDF-point units and the QGraphicsView applies the zoom via
    its transform.
    """
    return QPointF(pdf_pt.x(), page_height - pdf_pt.y())


def scene_to_pdf(scene_pt: QPointF, page_height: float) -> QPointF:
    """Inverse of pdf_to_scene."""
    return QPointF(scene_pt.x(), page_height - scene_pt.y())
