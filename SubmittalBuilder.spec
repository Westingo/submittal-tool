# PyInstaller spec — Metro Submittal Builder desktop app (onedir).
#
#   build (debuggable, shows console):  set SB_CONSOLE=1 then
#       .venv\Scripts\pyinstaller SubmittalBuilder.spec --noconfirm
#   build (final, windowed/no console):  leave SB_CONSOLE unset.
#
# Bundles only code + small resources (static/, assets/, fonts/). The
# spec-sheet library and presets are NOT bundled — they ship as external
# folders next to the .exe so the library can grow and jobs can be written
# without rebuilding (see paths.py).
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []

# shipped read-only resources
datas += [("static", "static"), ("assets", "assets")]
if os.path.isdir("fonts"):
    datas += [("fonts", "fonts")]

# pull everything these packages need (lazy/auto imports defeat static analysis)
for pkg in ("webview", "uvicorn", "fastapi", "starlette", "pydantic",
            "pydantic_core", "fitz", "pymupdf", "yaml", "multipart",
            "python_multipart", "anyio", "clr_loader", "pythonnet"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += collect_submodules("uvicorn")

a = Analysis(
    ["desktop.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
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
    name="SubmittalBuilder",
    debug=False,
    strip=False,
    upx=False,
    console=bool(os.environ.get("SB_CONSOLE")),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SubmittalBuilder",
)
