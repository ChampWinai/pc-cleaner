# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_web.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# onedir (not onefile): the exe launches instantly straight from disk
# instead of self-extracting its ~30MB of bundled DLLs into a fresh
# %TEMP% folder on every single startup, which is what made the app feel
# like it was hanging when opened (that fresh extraction gets re-scanned
# by antivirus each time since the binary isn't code-signed).
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PCCleaner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PCCleaner',
)
