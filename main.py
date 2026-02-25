#!/usr/bin/env python3
"""
Game Library Tracker - Main Entry Point
Cross-platform game library with IGDB cover art and playtime tracking
"""
import os
import base64
import sys
import argparse
import PyQt6
from pathlib import Path
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtQml import QQmlApplicationEngine

from backend.game_manager import GameManager
from backend.controllers import AppController

def main():
    """Application entry point"""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--launch-game-id", dest="launch_game_id", default="")
    parser.add_argument("--launch-game-id-b64", dest="launch_game_id_b64", default="")
    parser.add_argument("--start-minimized", dest="start_minimized", action="store_true")
    args, qt_argv = parser.parse_known_args(sys.argv[1:])

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")
    app = QApplication([sys.argv[0], *qt_argv])

    # Set JetBrains Mono font for the entire application
    font = QFont("Inter", 10)
    app.setFont(font)
    app_icon = Path(__file__).parent / "ui" / "assets" / "gamepad.svg"
    app.setWindowIcon(QIcon(str(app_icon)))

    engine = QQmlApplicationEngine()
    qml_import_path = Path(PyQt6.__file__).resolve().parent / "Qt6" / "qml"
    engine.addImportPath(str(qml_import_path))

    game_manager = GameManager()
    controller = AppController(game_manager)
    engine.rootContext().setContextProperty("backend", controller)

    qml_path = Path(__file__).parent / "ui" / "main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        sys.exit(1)

    launch_game_id = (args.launch_game_id or "").strip()
    launch_game_id_b64 = (args.launch_game_id_b64 or "").strip()
    if not launch_game_id and launch_game_id_b64:
        try:
            launch_game_id = base64.urlsafe_b64decode(launch_game_id_b64.encode("ascii")).decode("utf-8")
        except Exception:
            launch_game_id = ""
    if launch_game_id:
        QTimer.singleShot(0, lambda gid=launch_game_id: controller.launch_game_by_id(gid))
    if args.start_minimized:
        def _minimize_root_windows():
            for root in engine.rootObjects():
                if hasattr(root, "showMinimized"):
                    root.showMinimized()
        QTimer.singleShot(0, _minimize_root_windows)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
