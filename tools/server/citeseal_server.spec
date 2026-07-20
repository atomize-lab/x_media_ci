# PyInstaller spec for the CiteSeal server.
#
# We build TWO executables so users can pick their preferred style:
#
#   citeseal_server.exe          (console)   <- DEFAULT for the typical
#                                                "double-click and see what
#                                                 happens" experience
#   citeseal_server_windowed.exe (no console) <- for users who want a
#                                                 silent tray-style launcher
#
# Build:
#   pyinstaller --noconfirm --clean server/citeseal_server.spec
#
# Output (Windows):
#   server/dist/citeseal_server.exe
#   server/dist/citeseal_server_windowed.exe

# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

server_dir = Path(SPECPATH).resolve()  # directory holding this .spec
tools_root = server_dir.parent
scripts_pkg = tools_root / "scripts"
citeseal_py = tools_root / "citeseal.py"

# Analyze every helper module even though the embedded CLI loads its entry
# scripts with runpy. This lets PyInstaller collect transitive dependencies
# such as Pillow and ReportLab instead of treating the scripts as inert data.
script_modules = sorted(
    path.stem for path in scripts_pkg.glob("*.py") if path.name != "__init__.py"
)
hiddenimports = ["citeseal"]
hiddenimports += script_modules
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("starlette")

# Bundle script sources as data for runpy and for useful path/error reporting.
datas = [
    (str(scripts_pkg), "scripts"),
]
if citeseal_py.is_file():
    datas.append((str(citeseal_py), "."))

# The bundled start.cmd sits next to the exe so the user has a "one
# click + black window" experience.
start_cmd = tools_root / "server" / "start.cmd"
if start_cmd.is_file():
    datas.append((str(start_cmd), "."))

a = Analysis(
    [str(server_dir / "_frozen_entry.py")],
    pathex=[str(server_dir), str(tools_root), str(scripts_pkg)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy.tests",
        "PIL.ImageQt",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Console build: default for the typical "I just want to double-click"
# use case. Errors and access logs are visible.
exe_console = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="citeseal_server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# Windowed build: same binary, but no console popup. Logs go to
# citeseal_server.log next to the exe. Useful for a silent launcher.
exe_windowed = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="citeseal_server_windowed",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
