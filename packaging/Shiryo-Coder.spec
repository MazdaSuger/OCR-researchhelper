# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec（リポジトリ直下から `pyinstaller packaging/Shiryo-Coder.spec`）。

- パッケージ同梱データ `shiryo_coder/db/schema.sql` を datas に含める。
- OCR/NLP 等のオプション依存は導入済みのときだけ収集する（未導入でも spec は通る）。
- macOS では BUNDLE で .app を生成（他 OS では onedir まで）。
"""

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# パスは spec ファイルの位置（SPECPATH = packaging/）を基準に解決する
ROOT = os.path.dirname(SPECPATH)          # リポジトリ直下
ENTRY = os.path.join(SPECPATH, "entry.py")

# アイコン（make_icon.sh で生成。無ければ既定アイコン）
_icns = os.path.join(SPECPATH, "Shiryo-Coder.icns")
ICON = _icns if os.path.exists(_icns) else None

# 必須の同梱データ（importlib.resources 経由で参照される）
datas = [(os.path.join(ROOT, "shiryo_coder", "db", "schema.sql"), "shiryo_coder/db")]
hiddenimports = ["shiryo_coder"]

# 導入されていれば収集する任意パッケージ（辞書データ・サブモジュール）
for pkg in ("sudachipy", "sudachidict_core", "openpyxl"):
    try:
        datas += collect_data_files(pkg)
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

block_cipher = None

a = Analysis(
    [ENTRY],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="Shiryo-Coder",
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
    icon=ICON,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Shiryo-Coder",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Shiryo-Coder.app",
        icon=ICON,
        bundle_identifier="jp.shiryo.coder",
        version="0.1.0",
        info_plist={
            "CFBundleName": "Shiryō-Coder",
            "CFBundleDisplayName": "Shiryō-Coder",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
