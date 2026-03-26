# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PressureMat — single EXE with firmware bundle."""

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app.html', '.'),
        ('assets', 'assets'),
        ('firmware', 'firmware'),
    ],
    hiddenimports=[
        'serial.tools.list_ports_windows',
        'serial.tools.list_ports_common',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'tkinter', 'unittest', 'test',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PressureMat',
    console=True,
    disable_windowed_traceback=False,
    strip=False,
    upx=False,
)
