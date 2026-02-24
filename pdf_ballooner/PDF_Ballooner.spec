# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for PDF Ballooner
# Run with:  pyinstaller PDF_Ballooner.spec

from PyInstaller.utils.hooks import collect_all, collect_data_files

# --------------------------------------------------------------------------
# Collect runtime data / binaries for the heavy dependencies
# --------------------------------------------------------------------------

# PyQt6 – Qt platform plugins (windows, xcb, …), imageformats, translations
qt_datas, qt_bins, qt_hidden = collect_all("PyQt6")

# PyMuPDF (fitz) – embedded CMap tables, fonts, and native libs
fitz_datas, fitz_bins, fitz_hidden = collect_all("fitz")

# openpyxl – ships an XML template that must travel with the package
oxl_datas = collect_data_files("openpyxl")

# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=qt_bins + fitz_bins,
    datas=qt_datas + fitz_datas + oxl_datas,
    hiddenimports=(
        qt_hidden
        + fitz_hidden
        + [
            "openpyxl",
            "openpyxl.cell",
            "openpyxl.styles",
            "openpyxl.styles.fills",
            "openpyxl.styles.fonts",
            "openpyxl.styles.borders",
            "openpyxl.styles.alignment",
            "openpyxl.utils",
            "openpyxl.writer.excel",
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trim packages that are never needed in a GUI app to keep the
    # dist folder smaller.
    excludes=[
        "tkinter", "_tkinter",
        "unittest", "doctest", "pydoc",
        "email", "html", "http", "urllib", "xml",
        "multiprocessing",
        "IPython", "notebook", "matplotlib",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data)

# --------------------------------------------------------------------------
# EXE  (the launcher stub inside the output folder)
# --------------------------------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # binaries go into COLLECT below
    name="PDF Ballooner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                       # UPX compresses DLLs; safe to set False
    upx_exclude=["vcruntime*.dll", "msvcp*.dll", "Qt6*.dll"],
    console=False,                  # no black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    # icon="icon.ico",              # uncomment + add icon.ico to enable
)

# --------------------------------------------------------------------------
# COLLECT  (the final dist/PDF Ballooner/ folder)
# --------------------------------------------------------------------------

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime*.dll", "msvcp*.dll", "Qt6*.dll"],
    name="PDF Ballooner",
)
