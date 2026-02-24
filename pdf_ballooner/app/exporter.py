"""PDF and CSV export logic using PyMuPDF's vector drawing API."""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from app.balloon import BalloonData
from app.gdt import GDTAnnotation


def export_pdf(
    src_path: str,
    dst_path: str,
    balloons: list[BalloonData],
    gdt_annotations: Optional[list[GDTAnnotation]] = None,
) -> None:
    """Write a new PDF to *dst_path* with balloons and GD&T annotations as vector overlays."""
    if Path(src_path).resolve() == Path(dst_path).resolve():
        raise ValueError("Cannot overwrite the original PDF. Choose a different output path.")

    gdt_annotations = gdt_annotations or []
    doc = fitz.open(src_path)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_balloons = [b for b in balloons if b.page == page_idx]
        page_gdts     = [a for a in gdt_annotations if a.page == page_idx]

        if not page_balloons and not page_gdts:
            continue

        shape = page.new_shape()

        # --- Balloons ---
        for b in page_balloons:
            tx = b.target_point.x()
            ty = b.target_point.y()
            cx = b.balloon_center.x()
            cy = b.balloon_center.y()
            r  = b.diameter / 2.0
            style = b.style

            # Resolve colours by style
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
                circle_stroke = (0.8, 0, 0)
                circle_fill   = (0.8, 0, 0)
                text_color    = (1, 1, 1)
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
                if dist > 0:
                    edge = fitz.Point(cx + dx / dist * r, cy + dy / dist * r)
                else:
                    edge = fitz.Point(cx, cy - r)

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
            if b.font_size_override > 0:
                font_size = b.font_size_override
            else:
                font_size = max(4.0, r * 1.1)

            text  = str(b.number)
            est_w = 0.6 * font_size * len(text)
            text_x = cx - est_w / 2
            text_y = cy + font_size * 0.35
            page.insert_text(
                fitz.Point(text_x, text_y),
                text,
                fontname="hebo",   # Helvetica Bold
                fontsize=font_size,
                color=text_color,
            )

        shape.commit()

        # --- GD&T annotations ---
        for a in page_gdts:
            ax = a.position.x()
            ay = a.position.y()
            fs = a.font_size
            # Estimate box width
            w = fs * max(1, len(a.symbol)) * 0.65
            h = fs
            # Draw bounding box
            rect_shape = page.new_shape()
            box = fitz.Rect(ax - w / 2, ay - h / 2, ax + w / 2, ay + h / 2)
            rect_shape.draw_rect(box)
            rect_shape.finish(color=(0.2, 0.2, 0.2), fill=(1, 1, 0.85), width=0.5)
            rect_shape.commit()
            # Draw symbol text
            page.insert_text(
                fitz.Point(ax - w / 2 + 1, ay + fs * 0.35),
                a.symbol,
                fontname="helv",
                fontsize=fs,
                color=(0, 0, 0),
            )

    doc.save(dst_path, garbage=4, deflate=True)
    doc.close()


def _draw_arrowhead(shape: fitz.Shape, from_pt: fitz.Point,
                    to_pt: fitz.Point, size: float = 6,
                    color: tuple = (0.8, 0, 0)) -> None:
    """Draw a filled triangular arrowhead at *to_pt* pointing away from *from_pt*."""
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
