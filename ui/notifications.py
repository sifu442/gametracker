from __future__ import annotations

from collections import deque
from pathlib import Path
import platform
import shutil
import subprocess

from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import QApplication, QStyle, QSystemTrayIcon, QWidget

from core.constants import SCRIPT_DIR
from steam.image_fetcher import resolve_icon_path
from steam.models import UnlockEvent
from ui.achievement_popup import AchievementPopup


class PopupManager:
    """Queue-based notifications with in-app popup + system notification."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self.parent = parent
        self.queue: deque[UnlockEvent] = deque()
        self.showing = False
        self._tray: QSystemTrayIcon | None = None
        self._fallback_icon = SCRIPT_DIR / "ui" / "assets" / "placeholder_achievement.png"
        self._active_popup: AchievementPopup | None = None

    def enqueue(self, event: UnlockEvent) -> None:
        self.queue.append(event)
        try:
            self._show_system_notification(event)
        except Exception:
            # Never let system notification failures block in-app popup delivery.
            pass
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
        icon_path = self._resolve_icon(event)
        title = f"{event.game} • Achievement Unlocked"
        text = event.achievement if not event.description else f"{event.achievement}\n{event.description}"

        if platform.system() == "Windows":
            if self._show_windows_toast(title, text, icon_path):
                return

        # Linux native notifications can show a custom image icon via notify-send.
        if platform.system() == "Linux" and shutil.which("notify-send"):
            cmd = ["notify-send", "-a", "GameTracker", title, text]
            if icon_path:
                cmd.extend(["-i", icon_path])
            try:
                subprocess.Popen(cmd)
                return
            except Exception:
                pass

        tray = self._ensure_tray()
        if tray is None:
            return
        tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 4000)

    @staticmethod
    def _xml_escape(value: str) -> str:
        return (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _show_windows_toast(self, title: str, text: str, icon_path: str) -> bool:
        if not shutil.which("powershell"):
            return False
        try:
            image_xml = ""
            if icon_path and Path(icon_path).exists():
                uri = Path(icon_path).resolve().as_uri()
                image_xml = (
                    f"<image placement='appLogoOverride' hint-crop='none' src='{self._xml_escape(uri)}'/>"
                )
            xml = (
                "<toast><visual><binding template='ToastGeneric'>"
                f"{image_xml}"
                f"<text>{self._xml_escape(title)}</text>"
                f"<text>{self._xml_escape(text)}</text>"
                "</binding></visual></toast>"
            )
            xml_ps = xml.replace("'", "''")
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
                "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null; "
                "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument; "
                f"$xml.LoadXml('{xml_ps}'); "
                "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
                "$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('GameTracker'); "
                "$notifier.Show($toast);"
            )
            creationflags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                creationflags=creationflags,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _anchor_point(self) -> QPoint:
        screen = QGuiApplication.primaryScreen()
        geom = screen.availableGeometry() if screen else None
        if not geom:
            return QPoint(24, 24)
        popup_w = 360
        popup_h = 110
        margin = 20
        return QPoint(geom.right() - popup_w - margin, geom.bottom() - popup_h - margin)

    def _resolve_icon(self, event: UnlockEvent) -> str:
        icon = str(event.icon_path or "").strip()
        if icon and Path(icon).exists():
            return icon
        if icon:
            try:
                resolved = resolve_icon_path(str(event.appid or ""), icon, SCRIPT_DIR / "cache")
                if resolved and resolved.exists():
                    return str(resolved)
            except Exception:
                pass
        if self._fallback_icon.exists():
            return str(self._fallback_icon)
        return ""

    def _pump(self) -> None:
        if self.showing or not self.queue:
            return
        self.showing = True
        event = self.queue.popleft()
        popup = AchievementPopup(
            title=f"{event.game} • Achievement Unlocked",
            description=(f"{event.achievement}\n{event.description}" if event.description else event.achievement),
            icon_path=self._resolve_icon(event),
            parent=self.parent,
        )
        self._active_popup = popup
        anchor = self._anchor_point()
        popup.show_animated(anchor, hold_ms=10000)

        def done() -> None:
            self._active_popup = None
            self.showing = False
            self._pump()

        QTimer.singleShot(10350, done)
