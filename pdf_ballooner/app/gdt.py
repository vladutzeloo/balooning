"""GD&T annotation data model (kept for session-file backwards compatibility)."""
from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF

from app.utils import make_uid


@dataclass
class GDTAnnotation:
    symbol: str
    page: int
    position: QPointF
    font_size: float = 16.0
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
