"""PDF and CSV export logic using PyMuPDF's vector drawing API."""
from __future__ import annotations

import csv
import math
from pathlib import Path

import fitz  # PyMuPDF

from app.balloon import BalloonData


def export_pdf(src_path: str, dst_path: str, balloons: list[BalloonData]) -> None:
    """Write a new PDF to *dst_path* with balloons drawn as vector overlays.

    The original PDF content is preserved exactly; balloons are added using
    PyMuPDF's shape API so the output remains searchable and vector-quality.
    """
    if Path(src_path).resolve() == Path(dst_path).resolve():
        raise ValueError("Cannot overwrite the original PDF. Choose a different output path.")

    doc = fitz.open(src_path)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_balloons = [b for b in balloons if b.page == page_idx]
        if not page_balloons:
            continue

        # PyMuPDF PDF coords: origin bottom-left, Y up (same as our stored PDF coords)
        shape = page.new_shape()

        for b in page_balloons:
            tx = b.target_point.x()
            ty = b.target_point.y()
            cx = b.balloon_center.x()
            cy = b.balloon_center.y()
            r = b.diameter / 2.0

            target = fitz.Point(tx, ty)
            center = fitz.Point(cx, cy)

            # --- Leader line ---
            # Compute the point on the circle edge closest to the target
            dx = tx - cx
            dy = ty - cy
            dist = math.hypot(dx, dy)
            if dist > 0:
                edge = fitz.Point(cx + dx / dist * r, cy + dy / dist * r)
            else:
                edge = fitz.Point(cx, cy - r)

            shape.draw_line(edge, target)
            shape.finish(color=(0.8, 0, 0), width=1.5, stroke_opacity=1.0)

            # Arrow head at target point
            _draw_arrowhead(shape, edge, target, size=5)

            # --- Balloon circle ---
            shape.draw_circle(center, r)
            shape.finish(
                color=(0, 0, 0),
                fill=(1, 1, 1),
                width=1.5,
                fill_opacity=1.0,
            )

            # --- Number label ---
            font_size = max(4.0, r * 1.1)
            # insert_text origin is bottom-left of the text baseline
            # Centre it approximately in the circle
            text = str(b.number)
            # Estimate text width: ~0.6 * font_size per character
            est_w = 0.6 * font_size * len(text)
            text_x = cx - est_w / 2
            text_y = cy + font_size * 0.35   # slight upward shift for visual centring
            page.insert_text(
                fitz.Point(text_x, text_y),
                text,
                fontname="hebo",   # Helvetica Bold
                fontsize=font_size,
                color=(0, 0, 0),
            )

        shape.commit()

    doc.save(dst_path, garbage=4, deflate=True)
    doc.close()


def _draw_arrowhead(shape: fitz.Shape, from_pt: fitz.Point,
                    to_pt: fitz.Point, size: float = 6) -> None:
    """Draw a filled triangular arrowhead at *to_pt* pointing away from *from_pt*."""
    dx = to_pt.x - from_pt.x
    dy = to_pt.y - from_pt.y
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    # Perpendicular
    px, py = -uy, ux
    half = size * 0.45
    left  = fitz.Point(to_pt.x - size * ux + half * px,
                        to_pt.y - size * uy + half * py)
    right = fitz.Point(to_pt.x - size * ux - half * px,
                        to_pt.y - size * uy - half * py)
    shape.draw_polyline([to_pt, left, right, to_pt])
    shape.finish(color=(0.8, 0, 0), fill=(0.8, 0, 0), width=0)


def export_csv(dst_path: str, balloons: list[BalloonData]) -> None:
    """Write balloon data to a CSV file."""
    with open(dst_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Number", "Page", "X (pts)", "Y (pts)", "Description"])
        for b in sorted(balloons, key=lambda x: (x.page, x.number)):
            writer.writerow([
                b.number,
                b.page + 1,
                round(b.balloon_center.x(), 2),
                round(b.balloon_center.y(), 2),
                b.description,
            ])
