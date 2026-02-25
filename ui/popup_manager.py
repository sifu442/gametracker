from __future__ import annotations

from collections import deque
import platform
import shutil
import subprocess

from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import QApplication, QStyle, QSystemTrayIcon, QWidget

from steam.models import UnlockEvent
from ui.achievement_popup import AchievementPopup


class PopupManager:
    """Queue-based popup manager to prevent overlap chaos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self.parent = parent
        self.queue: deque[UnlockEvent] = deque()
        self.showing = False
        self._tray: QSystemTrayIcon | None = None

    def enqueue(self, event: UnlockEvent) -> None:
        """Queue one unlock popup event."""

        self.queue.append(event)
        self._show_system_notification(event)
        self._pump()

    def _ensure_tray(self) -> QSystemTrayIcon | None:
        if self._tray is not None:
            return self._tray
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        app = QApplication.instance()
        if app is None:
            return None

        icon = app.windowIcon()
        if icon.isNull():
            icon = app.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        tray = QSystemTrayIcon(QIcon(icon), app)
        tray.setVisible(True)
        self._tray = tray
        return self._tray

    def _show_system_notification(self, event: UnlockEvent) -> None:
        if platform.system().lower() == "linux" and self._show_linux_libnotify(event):
            return

        tray = self._ensure_tray()
        if tray is None:
            return
        title = f"{event.game} • Achievement Unlocked"
        text = event.achievement if not event.description else f"{event.achievement}\n{event.description}"
        tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _show_linux_libnotify(self, event: UnlockEvent) -> bool:
        notify_send = shutil.which("notify-send")
        if not notify_send:
            return False

        title = f"{event.game} - Achievement Unlocked"
        body = event.achievement if not event.description else f"{event.achievement}\n{event.description}"
        cmd = [
            notify_send,
            "--app-name=GameTracker",
            "--expire-time=4000",
            "--icon=applications-games",
            title,
            body,
        ]
        try:
            subprocess.Popen(cmd)
            return True
        except Exception:
            return False

    def _anchor_point(self) -> QPoint:
        # Prefer app window geometry so popup appears above in-app content ("games" area).
        win = QGuiApplication.focusWindow() or QGuiApplication.activeWindow()
        if win:
            g = win.geometry()
            x = g.left() + max(16, int((g.width() - 360) / 2))
            y = g.top() + 64
            return QPoint(x, y)

        screen = QGuiApplication.primaryScreen()
        geom = screen.availableGeometry() if screen else None
        if not geom:
            return QPoint(24, 24)
        return QPoint(geom.right() - 390, geom.bottom() - 140)

    def _pump(self) -> None:
        if self.showing or not self.queue:
            return
        self.showing = True
        event = self.queue.popleft()
        popup = AchievementPopup(
            title=f"{event.game} • Achievement Unlocked",
            description=(f"{event.achievement}\n{event.description}" if event.description else event.achievement),
            parent=self.parent,
        )
        anchor = self._anchor_point()
        popup.show_animated(anchor, hold_ms=2800)

        def done() -> None:
            self.showing = False
            self._pump()

        QTimer.singleShot(3150, done)
