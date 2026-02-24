"""PDF and CSV export logic using PyMuPDF's vector drawing API."""
from __future__ import annotations

import csv
import math
from pathlib import Path

import fitz  # PyMuPDF

from app.balloon import BalloonData


def export_pdf(src_path: str, dst_path: str, balloons: list[BalloonData]) -> None:
    """Write a new PDF to *dst_path* with balloons drawn as vector overlays."""
    if Path(src_path).resolve() == Path(dst_path).resolve():
        raise ValueError("Cannot overwrite the original PDF. Choose a different output path.")

    doc = fitz.open(src_path)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_balloons = [b for b in balloons if b.page == page_idx]
        if not page_balloons:
            continue

        shape = page.new_shape()

        for b in page_balloons:
            tx = b.target_point.x()
            ty = b.target_point.y()
            cx = b.balloon_center.x()
            cy = b.balloon_center.y()
            r  = b.diameter / 2.0
            style = b.style

            # Resolve colours and leader flag by style
            if style == "red":
                leader_color  = (0.8, 0, 0)
                circle_stroke = (0, 0, 0)
                circle_fill   = (1, 0, 0)
                text_color    = (1, 1, 1)
                draw_leader   = True
            elif style == "outline":
                leader_color  = (0.8, 0, 0)
                circle_stroke = (0, 0, 0)
                circle_fill   = None
                text_color    = (0, 0, 0)
                draw_leader   = True
            elif style == "no_arrow":
                leader_color  = (0.8, 0, 0)
                circle_stroke = (0.8, 0, 0)  # red outline
                circle_fill   = (1, 1, 1)    # white fill (not a disc)
                text_color    = (0.8, 0, 0)  # red number
                draw_leader   = False
            else:  # "default"
                leader_color  = (0.8, 0, 0)
                circle_stroke = (0, 0, 0)
                circle_fill   = (1, 1, 1)
                text_color    = (0, 0, 0)
                draw_leader   = True

            target = fitz.Point(tx, ty)
            center = fitz.Point(cx, cy)

            # --- Leader line + arrowhead ---
            if draw_leader:
                dx = tx - cx
                dy = ty - cy
                dist = math.hypot(dx, dy)
                edge = fitz.Point(cx + dx / dist * r, cy + dy / dist * r) if dist > 0 \
                       else fitz.Point(cx, cy - r)
                shape.draw_line(edge, target)
                shape.finish(color=leader_color, width=1.5, stroke_opacity=1.0)
                _draw_arrowhead(shape, edge, target, size=5, color=leader_color)

            # --- Circle ---
            shape.draw_circle(center, r)
            if circle_fill is not None:
                shape.finish(color=circle_stroke, fill=circle_fill, width=1.5, fill_opacity=1.0)
            else:
                shape.finish(color=circle_stroke, width=1.5, fill_opacity=0.0)

            # --- Number label ---
            font_size = b.font_size_override if b.font_size_override > 0 else max(4.0, r * 1.1)
            text  = str(b.number)
            est_w = 0.6 * font_size * len(text)
            page.insert_text(
                fitz.Point(cx - est_w / 2, cy + font_size * 0.35),
                text,
                fontname="hebo",
                fontsize=font_size,
                color=text_color,
            )

        shape.commit()

    doc.save(dst_path, garbage=4, deflate=True)
    doc.close()


def _draw_arrowhead(shape: fitz.Shape, from_pt: fitz.Point,
                    to_pt: fitz.Point, size: float = 6,
                    color: tuple = (0.8, 0, 0)) -> None:
    dx = to_pt.x - from_pt.x
    dy = to_pt.y - from_pt.y
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    half = size * 0.45
    left  = fitz.Point(to_pt.x - size * ux + half * px,
                        to_pt.y - size * uy + half * py)
    right = fitz.Point(to_pt.x - size * ux - half * px,
                        to_pt.y - size * uy - half * py)
    shape.draw_polyline([to_pt, left, right, to_pt])
    shape.finish(color=color, fill=color, width=0)


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
