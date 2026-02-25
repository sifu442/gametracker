# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all


project_root = Path(globals().get("SPECPATH", ".")).resolve()


def add_tree(rel_path):
    p = project_root / rel_path
    return [(str(p), rel_path)] if p.exists() else []


def build_windows_icon_from_svg():
    """
    Render ui/assets/gamepad.svg to a PNG so PyInstaller can convert it to .ico.
    Falls back to default icon if rendering fails.
    """
    svg_path = project_root / "ui" / "assets" / "gamepad.svg"
    if not svg_path.exists():
        return None
    try:
        from PyQt6.QtGui import QImage, QPainter
        from PyQt6.QtSvg import QSvgRenderer

        out_dir = project_root / "build"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_png = out_dir / "gamepad_icon_256.png"

        image = QImage(256, 256, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        renderer = QSvgRenderer(str(svg_path))
        renderer.render(painter)
        painter.end()
        if image.save(str(out_png), "PNG"):
            return str(out_png)
    except Exception:
        pass
    return None


datas = []
for folder in ("ui", "covers", "logos", "heroes", "temp_covers", "xpak_cache"):
    datas += add_tree(folder)

for file_name in ("config.json", "game_library.json", "emulators.json", "process_tracking.json"):
    p = project_root / file_name
    if p.exists():
        datas.append((str(p), "."))

pyqt_datas, pyqt_binaries, pyqt_hiddenimports = collect_all("PyQt6")
datas += pyqt_datas
binaries = pyqt_binaries
hiddenimports = pyqt_hiddenimports + [
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtNetwork",
]

app_icon = build_windows_icon_from_svg()


a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="GameTracker",
    icon=app_icon,
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
)
