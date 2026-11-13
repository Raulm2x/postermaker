# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

datas = [
    ('postermaker/static', 'postermaker/static'),
]

a = Analysis(
    ['postermaker/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PIL',
        'PIL._imaging',
        'img2pdf',
        'flask',
        'werkzeug',
        'jinja2',
        'postermaker',
        'postermaker.web',
        'postermaker.updater',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'tkinter', 'unittest'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='postermaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
