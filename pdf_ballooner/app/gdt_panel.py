"""GD&T Feature Control Frame builder, Dimension entry, and Surface Roughness panel.

Three tabs:
  • GD&T    — compose a feature control frame (symbol, tolerance, modifiers,
               datum references) with a live preview.
  • 123     — compose a dimension callout (type, nominal, tolerance band).
  • Surface — compose a surface roughness callout (ISO 1302 / ASME Y14.36M):
               parameter, value, units, lay, process method.

Clicking "Enter ✓" emits ``apply_description(str)`` which the main window
uses to save the text as the selected balloon's description.  The description
is then exported to the CSV / Excel inspection sheet.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QGridLayout, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout, QLineEdit,
    QComboBox, QFrame, QTabWidget,
)

# ── GD&T characteristic symbols ─────────────────────────────────────────────
GDT_CHARACTERISTICS = [
    ("⊕",  "True Position"),
    ("⏤",  "Straightness"),
    ("⏥",  "Flatness"),
    ("○",   "Circularity"),
    ("⌭",  "Cylindricity"),
    ("⌒",  "Profile of a Line"),
    ("⌓",  "Profile of a Surface"),
    ("⊥",  "Perpendicularity"),
    ("∠",  "Angularity"),
    ("∥",  "Parallelism"),
    ("◎",  "Concentricity"),
    ("⌯",  "Symmetry"),
    ("↗",  "Circular Runout"),
    ("⇗",  "Total Runout"),
]

# ── Modifier buttons: (label, tooltip, group) ─────────────────────────────
# group "mat"  = mutually exclusive (M/L/S)
# group "zone" = independent toggle
MODIFIERS = [
    ("Ⓜ",  "Max Material Condition (MMC)",   "mat"),
    ("Ⓛ",  "Least Material Condition (LMC)", "mat"),
    ("Ⓢ",  "Regardless of Feature Size",     "mat"),
    ("F",   "Free State",                     "zone"),
    ("T",   "Tangent Plane",                  "zone"),
    ("P",   "Projected Tolerance Zone",        "zone"),
    ("ST",  "Statistical Tolerance",           "zone"),
]

# ── Dimension types ──────────────────────────────────────────────────────────
DIMENSION_TYPES = [
    ("",   "Linear"),
    ("⌀",  "Diameter"),
    ("R",  "Radius"),
    ("□",  "Square / Width"),
    ("∠",  "Angular  (°)"),
]

# ── Surface roughness ────────────────────────────────────────────────────────
# Process restriction → symbol prefix (closest Unicode approximation)
SURFACE_PROCESS = [
    ("√",  "Any process"),
    ("√̄",  "Machining required"),
    ("⊙√", "No machining / as-cast"),
]

SURFACE_PARAMS = ["Ra", "Rz", "Rmax", "Rt", "Rq", "Rsk", "Rku"]

SURFACE_GRADES = [
    ("",      "Custom value"),
    ("0.025", "N1"),
    ("0.05",  "N2"),
    ("0.1",   "N3"),
    ("0.2",   "N4"),
    ("0.4",   "N5"),
    ("0.8",   "N6  ← typical machined"),
    ("1.6",   "N7"),
    ("3.2",   "N8"),
    ("6.3",   "N9"),
    ("12.5",  "N10"),
    ("25",    "N11"),
    ("50",    "N12"),
]

SURFACE_LAY = [
    ("",  "—  (not specified)"),
    ("=", "=   Parallel to projection plane"),
    ("⊥", "⊥  Perpendicular"),
    ("X", "X   Crossed"),
    ("M", "M   Multidirectional"),
    ("C", "C   Circular"),
    ("R", "R   Radial"),
    ("P", "P   Particulate / non-directional"),
]


class GDTPanelWidget(QDockWidget):
    """Feature control frame builder + dimension entry dock panel."""

    apply_description = pyqtSignal(str)   # formatted string → balloon description

    def __init__(self, parent=None):
        super().__init__("GD&T / Dimension Builder", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setMinimumWidth(310)

        root = QWidget()
        root_vl = QVBoxLayout(root)
        root_vl.setContentsMargins(4, 4, 4, 4)
        root_vl.setSpacing(4)

        # ── Balloon identification header ────────────────────────────────
        self._balloon_label = QLabel("No balloon selected")
        self._balloon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lf = self._balloon_label.font()
        lf.setBold(True)
        self._balloon_label.setFont(lf)
        root_vl.addWidget(self._balloon_label)

        self._current_desc_label = QLabel("")
        self._current_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._current_desc_label.setWordWrap(True)
        self._current_desc_label.setStyleSheet("color:#555; font-style:italic; font-size:10px;")
        root_vl.addWidget(self._current_desc_label)

        # ── Tabs ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        root_vl.addWidget(self._tabs)
        self._tabs.addTab(self._build_gdt_tab(), "GD&T")
        self._tabs.addTab(self._build_dim_tab(), "123 Dimension")
        self._tabs.addTab(self._build_surface_tab(), "⊙ Surface")

        root_vl.addStretch()
        self.setWidget(root)

        self._update_gdt_preview()
        self._update_dim_preview()
        self._update_surface_preview()

    # ────────────────────────────────────────────────────────────────────
    # GD&T tab
    # ────────────────────────────────────────────────────────────────────

    def _build_gdt_tab(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(4, 6, 4, 4)
        vl.setSpacing(6)

        # ── Symbol selector ──────────────────────────────────────────────
        sym_frame = QFrame()
        sym_frame.setFrameShape(QFrame.Shape.StyledPanel)
        sg = QGridLayout(sym_frame)
        sg.setSpacing(4)

        sg.addWidget(QLabel("Symbol:"), 0, 0)
        self._sym_combo = QComboBox()
        self._sym_combo.setFont(QFont("Arial", 12))
        for sym, name in GDT_CHARACTERISTICS:
            self._sym_combo.addItem(f"{sym}  {name}", sym)
        self._sym_combo.currentIndexChanged.connect(self._update_gdt_preview)
        sg.addWidget(self._sym_combo, 0, 1, 1, 5)

        # Diameter prefix toggle + tolerance value
        self._dia_btn = QPushButton("⌀")
        self._dia_btn.setFont(QFont("Arial", 12))
        self._dia_btn.setToolTip("Prefix tolerance with ⌀ (diameter symbol)")
        self._dia_btn.setCheckable(True)
        self._dia_btn.setFixedSize(34, 28)
        self._dia_btn.toggled.connect(self._update_gdt_preview)
        sg.addWidget(self._dia_btn, 1, 0)

        sg.addWidget(QLabel("Tol.:"), 1, 1)
        self._tol_edit = QLineEdit("0.05")
        self._tol_edit.setFixedWidth(70)
        self._tol_edit.textChanged.connect(self._update_gdt_preview)
        sg.addWidget(self._tol_edit, 1, 2)

        vl.addWidget(sym_frame)

        # ── Modifier buttons ─────────────────────────────────────────────
        mod_frame = QFrame()
        mod_frame.setFrameShape(QFrame.Shape.StyledPanel)
        mg = QGridLayout(mod_frame)
        mg.setSpacing(3)
        mg.addWidget(QLabel("Modifiers:"), 0, 0, 1, 4)

        self._mod_btns: dict[str, QPushButton] = {}
        mat_group: list[QPushButton] = []

        for idx, (label, tip, group) in enumerate(MODIFIERS):
            btn = QPushButton(label)
            btn.setFont(QFont("Arial", 10))
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.toggled.connect(self._update_gdt_preview)
            mg.addWidget(btn, 1 + idx // 4, idx % 4)
            self._mod_btns[label] = btn
            if group == "mat":
                mat_group.append(btn)

        # Material condition buttons are mutually exclusive
        def _make_exclusive(me, others):
            def _h(checked):
                if checked:
                    for b in others:
                        b.setChecked(False)
            return _h

        for btn in mat_group:
            others = [b for b in mat_group if b is not btn]
            btn.toggled.connect(_make_exclusive(btn, others))

        vl.addWidget(mod_frame)

        # ── Datum references ─────────────────────────────────────────────
        dat_frame = QFrame()
        dat_frame.setFrameShape(QFrame.Shape.StyledPanel)
        dg = QGridLayout(dat_frame)
        dg.setSpacing(4)
        dg.addWidget(QLabel("Datum references:"), 0, 0, 1, 3)

        self._datum_edits: list[QLineEdit] = []
        bold_f = QFont("Arial", 12)
        bold_f.setBold(True)
        for col, lbl_text in enumerate(["Primary", "Secondary", "Tertiary"]):
            lbl = QLabel(lbl_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dg.addWidget(lbl, 1, col)
            edit = QLineEdit()
            edit.setFont(bold_f)
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.setMaxLength(3)
            edit.setPlaceholderText("–")
            edit.textChanged.connect(self._update_gdt_preview)
            dg.addWidget(edit, 2, col)
            self._datum_edits.append(edit)

        vl.addWidget(dat_frame)

        # ── Live preview ─────────────────────────────────────────────────
        prev_frame = QFrame()
        prev_frame.setFrameShape(QFrame.Shape.StyledPanel)
        prev_frame.setStyleSheet("QFrame { background:#eef3ff; border-radius:4px; }")
        pfl = QVBoxLayout(prev_frame)
        pfl.setContentsMargins(6, 6, 6, 6)
        self._gdt_preview = QLabel()
        self._gdt_preview.setFont(QFont("Arial", 12))
        self._gdt_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gdt_preview.setWordWrap(True)
        pfl.addWidget(self._gdt_preview)
        vl.addWidget(prev_frame)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        clr = QPushButton("Clear")
        clr.clicked.connect(self._clear_gdt)
        self._gdt_apply_btn = QPushButton("Enter ✓")
        self._gdt_apply_btn.setEnabled(False)
        self._gdt_apply_btn.clicked.connect(self._apply_gdt)
        btn_row.addWidget(clr)
        btn_row.addWidget(self._gdt_apply_btn)
        vl.addLayout(btn_row)

        return w

    # ────────────────────────────────────────────────────────────────────
    # Dimension tab
    # ────────────────────────────────────────────────────────────────────

    def _build_dim_tab(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(4, 6, 4, 4)
        vl.setSpacing(6)

        frm = QFrame()
        frm.setFrameShape(QFrame.Shape.StyledPanel)
        fg = QGridLayout(frm)
        fg.setSpacing(4)

        fg.addWidget(QLabel("Type:"), 0, 0)
        self._dim_type_combo = QComboBox()
        for prefix, name in DIMENSION_TYPES:
            label = f"{prefix}  {name}" if prefix else name
            self._dim_type_combo.addItem(label, prefix)
        self._dim_type_combo.currentIndexChanged.connect(self._update_dim_preview)
        fg.addWidget(self._dim_type_combo, 0, 1, 1, 2)

        fg.addWidget(QLabel("Nominal:"), 1, 0)
        self._dim_nominal = QLineEdit("0.000")
        self._dim_nominal.textChanged.connect(self._update_dim_preview)
        fg.addWidget(self._dim_nominal, 1, 1, 1, 2)

        fg.addWidget(QLabel("Upper tol.:"), 2, 0)
        self._dim_upper = QLineEdit("+0.000")
        self._dim_upper.textChanged.connect(self._update_dim_preview)
        fg.addWidget(self._dim_upper, 2, 1, 1, 2)

        fg.addWidget(QLabel("Lower tol.:"), 3, 0)
        self._dim_lower = QLineEdit("-0.000")
        self._dim_lower.textChanged.connect(self._update_dim_preview)
        fg.addWidget(self._dim_lower, 3, 1, 1, 2)

        vl.addWidget(frm)

        prev_frame = QFrame()
        prev_frame.setFrameShape(QFrame.Shape.StyledPanel)
        prev_frame.setStyleSheet("QFrame { background:#eef3ff; border-radius:4px; }")
        pfl = QVBoxLayout(prev_frame)
        pfl.setContentsMargins(6, 6, 6, 6)
        self._dim_preview = QLabel()
        self._dim_preview.setFont(QFont("Arial", 12))
        self._dim_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pfl.addWidget(self._dim_preview)
        vl.addWidget(prev_frame)

        btn_row = QHBoxLayout()
        clr = QPushButton("Clear")
        clr.clicked.connect(self._clear_dim)
        self._dim_apply_btn = QPushButton("Enter ✓")
        self._dim_apply_btn.setEnabled(False)
        self._dim_apply_btn.clicked.connect(self._apply_dim)
        btn_row.addWidget(clr)
        btn_row.addWidget(self._dim_apply_btn)
        vl.addLayout(btn_row)
        vl.addStretch()

        return w

    # ────────────────────────────────────────────────────────────────────
    # String builders
    # ────────────────────────────────────────────────────────────────────

    def _build_gdt_string(self) -> str:
        sym = self._sym_combo.currentData() or "?"
        tol = self._tol_edit.text().strip()
        dia = "⌀" if self._dia_btn.isChecked() else ""

        # Mutually-exclusive material condition modifier
        mat_mod = ""
        for key in ("Ⓜ", "Ⓛ", "Ⓢ"):
            if self._mod_btns.get(key) and self._mod_btns[key].isChecked():
                mat_mod = key
                break

        # Independent zone modifiers
        zone = "".join(
            key for key in ("F", "T", "P", "ST")
            if self._mod_btns.get(key) and self._mod_btns[key].isChecked()
        )
        zone_str = f"({zone})" if zone else ""

        tol_cell = f"{dia}{tol}{mat_mod}{zone_str}"
        datums = [e.text().strip().upper() for e in self._datum_edits]
        parts = [sym, tol_cell] + [d for d in datums if d]
        return "| " + " | ".join(parts) + " |"

    def _build_dim_string(self) -> str:
        prefix = self._dim_type_combo.currentData() or ""
        nominal = self._dim_nominal.text().strip()
        upper = self._dim_upper.text().strip()
        lower = self._dim_lower.text().strip()
        s = f"{prefix}{nominal}"
        if upper != "+0.000" or lower != "-0.000":
            # Bilateral symmetric tolerance
            if upper.lstrip("+") == lower.lstrip("-"):
                s += f" ±{upper.lstrip('+')}"
            else:
                s += f"  {upper} / {lower}"
        return s

    # ────────────────────────────────────────────────────────────────────
    # Preview updaters
    # ────────────────────────────────────────────────────────────────────

    def _update_gdt_preview(self):
        self._gdt_preview.setText(self._build_gdt_string())

    def _update_dim_preview(self):
        self._dim_preview.setText(self._build_dim_string())

    # ────────────────────────────────────────────────────────────────────
    # Clear
    # ────────────────────────────────────────────────────────────────────

    def _clear_gdt(self):
        self._tol_edit.setText("0.05")
        self._dia_btn.setChecked(False)
        for btn in self._mod_btns.values():
            btn.setChecked(False)
        for edit in self._datum_edits:
            edit.clear()
        self._update_gdt_preview()

    def _clear_dim(self):
        self._dim_nominal.setText("0.000")
        self._dim_upper.setText("+0.000")
        self._dim_lower.setText("-0.000")
        self._update_dim_preview()

    # ────────────────────────────────────────────────────────────────────
    # Apply (emit to main window)
    # ────────────────────────────────────────────────────────────────────

    def _apply_gdt(self):
        self.apply_description.emit(self._build_gdt_string())

    def _apply_dim(self):
        self.apply_description.emit(self._build_dim_string())

    # ────────────────────────────────────────────────────────────────────
    # Surface Roughness tab  (ISO 1302 / ASME Y14.36M)
    # ────────────────────────────────────────────────────────────────────

    def _build_surface_tab(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(4, 6, 4, 4)
        vl.setSpacing(6)

        # ── Symbol / process restriction ─────────────────────────────────
        sym_frame = QFrame()
        sym_frame.setFrameShape(QFrame.Shape.StyledPanel)
        sg = QGridLayout(sym_frame)
        sg.setSpacing(4)

        sg.addWidget(QLabel("Process:"), 0, 0)
        self._surf_process_combo = QComboBox()
        self._surf_process_combo.setFont(QFont("Arial", 11))
        for sym, name in SURFACE_PROCESS:
            self._surf_process_combo.addItem(f"{sym}  {name}", sym)
        self._surf_process_combo.currentIndexChanged.connect(self._update_surface_preview)
        sg.addWidget(self._surf_process_combo, 0, 1, 1, 3)

        # ── Parameter + value ────────────────────────────────────────────
        sg.addWidget(QLabel("Parameter:"), 1, 0)
        self._surf_param_combo = QComboBox()
        for p in SURFACE_PARAMS:
            self._surf_param_combo.addItem(p)
        self._surf_param_combo.currentIndexChanged.connect(self._update_surface_preview)
        sg.addWidget(self._surf_param_combo, 1, 1)

        sg.addWidget(QLabel("Grade:"), 2, 0)
        self._surf_grade_combo = QComboBox()
        self._surf_grade_combo.setFixedWidth(160)
        for val, label in SURFACE_GRADES:
            self._surf_grade_combo.addItem(f"{label}" if val else label, val)
        self._surf_grade_combo.currentIndexChanged.connect(self._on_grade_selected)
        sg.addWidget(self._surf_grade_combo, 2, 1, 1, 3)

        sg.addWidget(QLabel("Value:"), 3, 0)
        self._surf_value_edit = QLineEdit("0.8")
        self._surf_value_edit.setFixedWidth(70)
        self._surf_value_edit.textChanged.connect(self._update_surface_preview)
        sg.addWidget(self._surf_value_edit, 3, 1)

        sg.addWidget(QLabel("Units:"), 3, 2)
        self._surf_units_combo = QComboBox()
        self._surf_units_combo.addItems(["μm", "μin"])
        self._surf_units_combo.currentIndexChanged.connect(self._update_surface_preview)
        sg.addWidget(self._surf_units_combo, 3, 3)

        vl.addWidget(sym_frame)

        # ── Lay direction ────────────────────────────────────────────────
        lay_frame = QFrame()
        lay_frame.setFrameShape(QFrame.Shape.StyledPanel)
        lg = QGridLayout(lay_frame)
        lg.setSpacing(4)
        lg.addWidget(QLabel("Lay direction:"), 0, 0)
        self._surf_lay_combo = QComboBox()
        self._surf_lay_combo.setFont(QFont("Arial", 11))
        for sym, name in SURFACE_LAY:
            self._surf_lay_combo.addItem(name, sym)
        self._surf_lay_combo.currentIndexChanged.connect(self._update_surface_preview)
        lg.addWidget(self._surf_lay_combo, 0, 1)
        vl.addWidget(lay_frame)

        # ── Process / method note (optional) ─────────────────────────────
        met_frame = QFrame()
        met_frame.setFrameShape(QFrame.Shape.StyledPanel)
        mfl = QGridLayout(met_frame)
        mfl.setSpacing(4)
        mfl.addWidget(QLabel("Method (opt.):"), 0, 0)
        self._surf_method_edit = QLineEdit()
        self._surf_method_edit.setPlaceholderText("e.g. Ground, Turned, Milled…")
        self._surf_method_edit.textChanged.connect(self._update_surface_preview)
        mfl.addWidget(self._surf_method_edit, 0, 1)
        vl.addWidget(met_frame)

        # ── Live preview ─────────────────────────────────────────────────
        prev_frame = QFrame()
        prev_frame.setFrameShape(QFrame.Shape.StyledPanel)
        prev_frame.setStyleSheet("QFrame { background:#eef3ff; border-radius:4px; }")
        pfl = QVBoxLayout(prev_frame)
        pfl.setContentsMargins(6, 6, 6, 6)
        self._surf_preview = QLabel()
        self._surf_preview.setFont(QFont("Arial", 12))
        self._surf_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._surf_preview.setWordWrap(True)
        pfl.addWidget(self._surf_preview)
        vl.addWidget(prev_frame)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        clr = QPushButton("Clear")
        clr.clicked.connect(self._clear_surface)
        self._surf_apply_btn = QPushButton("Enter ✓")
        self._surf_apply_btn.setEnabled(False)
        self._surf_apply_btn.clicked.connect(self._apply_surface)
        btn_row.addWidget(clr)
        btn_row.addWidget(self._surf_apply_btn)
        vl.addLayout(btn_row)
        vl.addStretch()

        return w

    def _on_grade_selected(self, idx: int):
        val = self._surf_grade_combo.itemData(idx)
        if val:  # pre-set grade → push value into the line edit
            self._surf_value_edit.setText(val)
        self._update_surface_preview()

    def _build_surface_string(self) -> str:
        sym   = self._surf_process_combo.currentData() or "√"
        param = self._surf_param_combo.currentText()
        value = self._surf_value_edit.text().strip()
        units = self._surf_units_combo.currentText()
        lay   = self._surf_lay_combo.currentData() or ""
        meth  = self._surf_method_edit.text().strip()

        parts = [f"{sym} {param} {value} {units}"]
        if lay:
            parts.append(f"Lay: {lay}")
        if meth:
            parts.append(meth)
        return "  |  ".join(parts)

    def _update_surface_preview(self):
        self._surf_preview.setText(self._build_surface_string())

    def _clear_surface(self):
        self._surf_process_combo.setCurrentIndex(0)
        self._surf_param_combo.setCurrentIndex(0)
        self._surf_grade_combo.setCurrentIndex(0)
        self._surf_value_edit.setText("0.8")
        self._surf_units_combo.setCurrentIndex(0)
        self._surf_lay_combo.setCurrentIndex(0)
        self._surf_method_edit.clear()
        self._update_surface_preview()

    def _apply_surface(self):
        self.apply_description.emit(self._build_surface_string())

    # ────────────────────────────────────────────────────────────────────
    # Public API (called by MainWindow)
    # ────────────────────────────────────────────────────────────────────

    def set_balloon(self, number: int, description: str):
        self._balloon_label.setText(f"Editing: Balloon #{number}")
        self._current_desc_label.setText(
            f"Current: {description}" if description else ""
        )
        self._gdt_apply_btn.setEnabled(True)
        self._dim_apply_btn.setEnabled(True)
        self._surf_apply_btn.setEnabled(True)

    def clear_selection(self):
        self._balloon_label.setText("No balloon selected")
        self._current_desc_label.setText("")
        self._gdt_apply_btn.setEnabled(False)
        self._dim_apply_btn.setEnabled(False)
        self._surf_apply_btn.setEnabled(False)
