# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_dynamic_libs

a = Analysis(
    ['rb.py'],
    pathex=['.'],
    # torchvision loads _C_stable.so (nms, needed by easyocr) at run time,
    # so PyInstaller does not find it by itself; on macOS the default
    # patterns would only match *.dylib
    binaries=collect_dynamic_libs('torchvision', search_patterns=['*.dylib', '*.so']),
    datas=[('docs/MANUAL.md', 'docs'), ('docs/img', 'docs/img')],	# Help ▸ User Guide
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
    name='rb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='rb',
)
# the version About shows (version.py), for Info.plist too
VERSION = {}
exec(open(os.path.join(SPECPATH, 'version.py')).read(), VERSION)
VERSION = VERSION['VERSION']
app = BUNDLE(
    coll,
    name='rb2.app',
    icon='icon.icns',
    bundle_identifier=None,
    version=VERSION,	# what Finder's Get Info shows
)
