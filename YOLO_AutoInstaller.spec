# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['e:\\程序\\一键安装 yolov\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('repos.yaml', '.'), ('assets', 'assets'), ('modules', 'modules')],
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
    a.binaries,
    a.datas,
    [],
    name='YOLO_AutoInstaller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['e:\\程序\\一键安装 yolov\\assets\\app.ico'],
)
