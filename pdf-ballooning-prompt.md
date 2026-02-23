# PDF Ballooning Tool — Claude Code Build Prompt

## Project Overview

Build a desktop PDF ballooning application using **Python 3.12+, PyQt6, and PyMuPDF (fitz)**. This tool is used in aerospace manufacturing/quality inspection to add numbered balloon callouts to technical drawings and documents (similar to First Article Inspection ballooning).

## Core Functionality

1. **Open PDF** — File dialog to open any PDF file, render pages in a scrollable/zoomable canvas
2. **Place Balloons** — Click anywhere on the PDF to place a numbered balloon (auto-incrementing circle with number inside)
3. **Leader Lines** — Each balloon has a draggable leader line (arrow) pointing from the balloon to the feature being called out
4. **Balloon Table** — Side panel showing a table of all balloons (number, page, optional description field the user can type into)
5. **Export PDF** — Save a new PDF with all balloons and leader lines burned into the document, preserving original quality
6. **Export Balloon List** — Optional: export the balloon table as a CSV or Excel file

## Technical Requirements

### Dependencies
- `PyQt6` — GUI framework
- `PyMuPDF` (import as `fitz`) — PDF rendering and manipulation
- `Pillow` — Image handling if needed

### PDF Rendering
- Render each PDF page as a high-resolution QPixmap using PyMuPDF's `page.get_pixmap(matrix=zoom_matrix)`
- Display in a `QGraphicsScene` / `QGraphicsView` for smooth pan and zoom
- Support multi-page PDFs with page navigation (prev/next buttons or page selector dropdown)
- Zoom controls: zoom in, zoom out, fit-to-width, fit-to-page (minimum: Ctrl+scroll wheel zoom)

### Balloon Placement
- **Mode toggle**: Switch between "Navigate" mode (pan/scroll) and "Balloon" mode (click to place)
- In Balloon mode, clicking on the PDF canvas places a balloon at that location
- Balloons are numbered sequentially starting from 1 (auto-increment)
- Balloon appearance:
  - Circle with configurable diameter (default ~30px at 100% zoom, but scales with zoom)
  - White fill with black border (2px)
  - Black number centered inside, bold font
  - Red leader line (arrow) from circle edge to the clicked point
- Default leader line: the balloon circle is offset ~40px up-right from the click point, with the leader line connecting the circle to the exact click point
- Balloons are draggable — user can reposition the circle (leader line endpoint stays fixed, or both move)
- Right-click balloon → context menu with "Delete balloon", "Edit number", "Edit description"

### Coordinate System
- **Critical**: Maintain proper mapping between screen coordinates (pixels at current zoom) and PDF coordinates (points, origin at bottom-left)
- Store balloon positions in PDF coordinate space so they export correctly regardless of zoom level
- When rendering balloons on screen, transform PDF coords → screen coords using current zoom/pan state

### Balloon Table (Side Panel)
- Dockable side panel (QDockWidget) with a table showing:
  - Balloon # | Page # | X | Y | Description (editable text field)
- Clicking a row in the table should navigate to and highlight that balloon
- Support reordering/renumbering balloons
- "Add description" field for each balloon (useful for inspection reports)

### Export to PDF
- Create a new PDF file (never modify the original)
- For each page, draw balloons and leader lines onto the PDF using PyMuPDF's drawing API:
  - `page.draw_circle()` for balloon circles
  - `page.insert_text()` for balloon numbers
  - `page.draw_line()` for leader lines
  - Use `page.new_shape()` for grouped drawing operations
- Balloons must be drawn in PDF coordinate space (points) — use the stored PDF coordinates directly
- Preserve original PDF quality (don't rasterize the original content)
- File dialog for save location, default filename: `{original_name}_ballooned.pdf`

### Keyboard Shortcuts
- `Ctrl+O` — Open PDF
- `Ctrl+S` — Export ballooned PDF
- `Ctrl+Z` — Undo last balloon placement
- `Ctrl+Shift+Z` — Redo
- `Delete` — Delete selected balloon
- `Ctrl++` / `Ctrl+-` — Zoom in/out
- `Ctrl+0` — Fit to page
- `B` — Toggle balloon placement mode
- `Escape` — Back to navigate mode

### UI Layout
```
┌─────────────────────────────────────────────────────────┐
│ Menu Bar: File | Edit | View | Tools                    │
├─────────────┬───────────────────────────────────────────┤
│ Toolbar:    │ Open | Save | Zoom+/- | Mode: Nav/Balloon │
├─────────────┼─────────────────────────┬─────────────────┤
│             │                         │ Balloon Table   │
│             │                         │ ┌──┬──┬───────┐ │
│             │     PDF Canvas          │ │# │Pg│ Desc  │ │
│             │     (QGraphicsView)     │ │1 │1 │       │ │
│             │                         │ │2 │1 │       │ │
│             │                         │ │3 │2 │       │ │
│             │                         │ └──┴──┴───────┘ │
├─────────────┼─────────────────────────┼─────────────────┤
│ Status Bar: │ Page 1/5 | Zoom: 150%  │ Balloons: 12    │
└─────────────┴─────────────────────────┴─────────────────┘
```

### Page Navigation
- Page selector: dropdown or spinbox showing current page / total pages
- Previous/Next page buttons in toolbar
- All balloons are stored per-page
- When switching pages, show only that page's balloons

## Project Structure
```
pdf_ballooner/
├── main.py              # Entry point, QApplication setup
├── app/
│   ├── __init__.py
│   ├── main_window.py   # QMainWindow, menus, toolbar, layout
│   ├── pdf_viewer.py    # QGraphicsView/Scene, PDF rendering, zoom/pan
│   ├── balloon.py       # Balloon data model and QGraphicsItem
│   ├── balloon_table.py # Side panel QDockWidget with QTableWidget
│   ├── exporter.py      # PDF export logic using PyMuPDF
│   └── utils.py         # Coordinate transforms, helpers
├── requirements.txt     # PyQt6, PyMuPDF, Pillow
└── README.md
```

## Balloon Data Model
```python
@dataclass
class BalloonData:
    number: int
    page: int                    # 0-indexed page number
    target_point: QPointF        # PDF coords where the arrow points (the feature)
    balloon_center: QPointF      # PDF coords of the balloon circle center
    description: str = ""
    diameter: float = 20.0       # in PDF points
    uid: str = ""                # unique ID (use uuid4)
```

## Important Implementation Notes

1. **Don't rasterize the PDF on export** — use PyMuPDF's vector drawing API to add balloons as overlay drawings, keeping the original PDF content intact and searchable
2. **Zoom-independent balloon sizes** — balloons should appear the same visual size regardless of zoom level (scale the QGraphicsItem inversely with zoom), but export at a fixed PDF-point size
3. **Handle large PDFs** — aerospace drawings can be A0/A1 size, so render at appropriate DPI and handle memory efficiently (render only visible pages)
4. **Undo/Redo** — implement with a simple command pattern (QUndoStack)
5. **Save/Load session** — bonus: save balloon positions to a JSON sidecar file so you can resume work without re-placing balloons

## Nice-to-Have Features (implement if time allows)
- Balloon style customization (color, size, font)
- Snap-to-grid option
- Balloon numbering format options (1,2,3 vs A,B,C vs custom prefix like "B-1, B-2")
- Multi-page overview / thumbnail sidebar
- Print ballooned PDF directly
- Dark mode / light mode toggle
- Import balloon list from CSV (for pre-planned inspections)

## Testing
- Test with a multi-page PDF (3+ pages)
- Test with a large format drawing (A1/A0 size PDF)
- Test zoom in/out with balloons maintaining correct positions
- Test export and verify balloons appear at correct positions in the output PDF
- Test undo/redo for balloon placement and deletion
