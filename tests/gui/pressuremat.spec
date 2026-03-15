# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PressureMat — onedir build with firmware bundle."""

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
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PressureMat',
    icon='assets/icon.ico',
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='PressureMat',
)
