#!/usr/bin/env python3
"""
Game Library Tracker - Main Entry Point
Cross-platform game library with IGDB cover art and playtime tracking
"""
import os
import base64
import sys
import argparse
import json
import PyQt6
from pathlib import Path
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from backend.game_manager import GameManager
from backend.controllers import AppController
from utils.helpers import debug_log


SINGLE_INSTANCE_SERVER = "GameTracker.SingleInstance"


def _build_startup_payload(args) -> dict:
    launch_game_id = (args.launch_game_id or "").strip()
    launch_game_id_b64 = (args.launch_game_id_b64 or "").strip()
    if not launch_game_id and launch_game_id_b64:
        try:
            launch_game_id = base64.urlsafe_b64decode(launch_game_id_b64.encode("ascii")).decode("utf-8")
        except Exception:
            launch_game_id = ""
    return {
        "launch_game_id": launch_game_id,
        "start_minimized": bool(args.start_minimized),
    }


def _send_to_running_instance(payload: dict) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_SERVER)
    if not socket.waitForConnected(300):
        return False
    data = json.dumps(payload).encode("utf-8")
    socket.write(data)
    socket.flush()
    socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


def main():
    """Application entry point"""
    def _log_unhandled(exc_type, exc_value, exc_tb):
        try:
            import traceback
            log_path = Path(__file__).parent / "crash_trace.log"
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("\n--- Unhandled Exception ---\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _log_unhandled
    debug_log(f"[debug] main entry argv={sys.argv!r}")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--launch-game-id", dest="launch_game_id", default="")
    parser.add_argument("--launch-game-id-b64", dest="launch_game_id_b64", default="")
    parser.add_argument("--start-minimized", dest="start_minimized", action="store_true")
    args, qt_argv = parser.parse_known_args(sys.argv[1:])

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")
    app = QApplication([sys.argv[0], *qt_argv])
    startup_payload = _build_startup_payload(args)
    debug_log(f"[debug] startup payload={startup_payload!r}")

    # Single-instance handoff: if another instance is running, forward request and quit.
    if _send_to_running_instance(startup_payload):
        debug_log("[debug] handoff to existing instance succeeded; exiting current process")
        return
    debug_log("[debug] no existing instance detected; starting primary instance")

    # Set JetBrains Mono font for the entire application
    font = QFont("Inter", 10)
    app.setFont(font)
    app_icon = Path(__file__).parent / "ui" / "assets" / "halo.svg"
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

    def _show_main_window():
        for root in engine.rootObjects():
            try:
                root.showNormal()
                root.raise_()
                root.requestActivate()
            except Exception:
                pass

    if startup_payload.get("launch_game_id"):
        QTimer.singleShot(0, lambda gid=startup_payload["launch_game_id"]: controller.launch_game_by_id(gid))
    if startup_payload.get("start_minimized"):
        def _minimize_root_windows():
            for root in engine.rootObjects():
                if hasattr(root, "showMinimized"):
                    root.showMinimized()
        QTimer.singleShot(0, _minimize_root_windows)

    # Primary instance server: accept handoff from future launches.
    server = QLocalServer()
    QLocalServer.removeServer(SINGLE_INSTANCE_SERVER)
    if server.listen(SINGLE_INSTANCE_SERVER):
        def _handle_new_connection():
            socket = server.nextPendingConnection()
            if not socket:
                return
            if not socket.waitForReadyRead(300):
                socket.disconnectFromServer()
                return
            try:
                payload = json.loads(bytes(socket.readAll()).decode("utf-8"))
            except Exception:
                payload = {}
            socket.disconnectFromServer()
            _show_main_window()
            game_id = str(payload.get("launch_game_id") or "").strip()
            if game_id:
                controller.launch_game_by_id(game_id)

        server.newConnection.connect(_handle_new_connection)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
