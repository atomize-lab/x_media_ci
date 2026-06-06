# PyInstaller spec for the x_media CI DESKTOP app.
#
# Output (Windows):
#   app_desktop/dist/x_media_ci_app.exe   (single file, no console)
#
# Output (Linux):
#   app_desktop/dist/x_media_ci_app       (single binary, no console)
#
# Build:
#   pyinstaller --noconfirm --clean app_desktop/tweet_gui.spec

# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Pull in tkinter dynamically. On Windows / Linux, PyInstaller usually
# includes it automatically when it sees the import.
hiddenimports = collect_submodules("tkinter")

# Bundle the whole <tools> tree so the frozen app can find
# x_media_ci.py + scripts/. We exclude the heavier server package
# (FastAPI) and the Flutter app skeleton.
app_dir = Path(SPECPATH).resolve()           # app_desktop/
tools_root = app_dir.parent                  # tools/

# Build a list of (source, dest_in_bundle) pairs.
datas: list[tuple[str, str]] = []

# Whole <tools>/scripts/ — required by x_media_ci
datas.append((str(tools_root / "scripts"), "scripts"))

# x_media_ci.py + the rest of tools/* (server, etc.) — only the files
# we actually need.
for fname in ("x_media_ci.py",
              "fetch_tweet.py",
              "fetch_x.py",
              "Makefile", "make.cmd",
              "requirements.txt",
              ".env.example"):
    p = tools_root / fname
    if p.is_file():
        datas.append((str(p), "."))

# Re-bundle app_desktop's own .py (so spec + source live in one place)
for fname in ("tweet_fetcher.py",):
    p = app_dir / fname
    if p.is_file():
        datas.append((str(p), "."))

a = Analysis(
    [str(app_dir / "tweet_gui.py")],
    pathex=[str(app_dir), str(tools_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "PIL.ImageQt",
        "uvicorn",
        "fastapi",
        "starlette",
        "anyio",
        "pydantic",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use --onedir (one-folder) instead of --onefile so the bundled
# `fetch_tweet.py` / `fetch_x.py` / `scripts/` live next to the exe.
# This is what the GUI's subprocess (system python) will call when
# actually fetching from x.com.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="x_media_ci_app",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,                # GUI app: no console popup
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="x_media_ci_app",
)
