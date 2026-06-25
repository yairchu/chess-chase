# -*- mode: python ; coding: utf-8 -*-

import os

codesign_identity = os.environ.get('CODESIGN_IDENTITY')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('chess-chase-pieces.png', '.'),
        ('background.jpg', '.'),
        ('logo.png', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Chess Chase',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=codesign_identity,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Chess Chase',
)
app = BUNDLE(
    coll,
    name='Chess Chase.app',
    icon='build/icons/Chess Chase.icns',
    bundle_identifier='org.yairchu.chesschase',
    codesign_identity=codesign_identity,
    entitlements_file=None,
    info_plist={
        'CFBundleShortVersionString': '1.2.1',
        'CFBundleVersion': '1.2.1',
    },
)
