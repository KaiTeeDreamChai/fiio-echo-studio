# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification for FiiO Echo Studio
Packages React Frontend (dist/), Embedded Static Binaries (engine/bin/),
and Python Core Engine into a standalone native macOS .app Bundle.
"""

import os

block_cipher = None
project_root = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(project_root, 'dist'), 'dist'),
    (os.path.join(project_root, 'engine', 'bin'), os.path.join('engine', 'bin')),
    (os.path.join(project_root, 'assets', 'icon.icns'), 'assets'),
]

hidden_imports = [
    'mutagen',
    'mutagen.flac',
    'PIL',
    'PIL.Image',
    'webview',
    'webview.platforms.cocoa',
    'objc',
    'AppKit',
    'WebKit',
    'Foundation',
    'sqlite3',
    'json',
    'http.server',
    'urllib.parse',
]

a = Analysis(
    ['app_launcher.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FiiO Echo Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'assets', 'icon.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FiiO Echo Studio',
)

app = BUNDLE(
    coll,
    name='FiiO Echo Studio.app',
    icon=os.path.join(project_root, 'assets', 'icon.icns'),
    bundle_identifier='com.fiio.echostudio',
    info_plist={
        'CFBundleShortVersionString': '1.1.0',
        'CFBundleVersion': '1.1.0',
        'CFBundleDisplayName': 'FiiO Echo Studio',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '11.0',
        'NSRequiresAquaSystemAppearance': 'False',
        'NSHumanReadableCopyright': 'Copyright © 2026 FiiO Echo Studio',
    },
)
