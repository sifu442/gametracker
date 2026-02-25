from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class AchievementPopup(QFrame):
    """Frameless animated popup for unlock notifications."""

    def __init__(self, title: str, description: str, icon_path: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AchievementPopup")
        self.setWindowFlags(
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(360, 110)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon_lbl = QLabel("")
        icon_lbl.setFixedSize(48, 48)
        icon_lbl.setStyleSheet("background: transparent;")
        pm = QPixmap(icon_path) if icon_path else QPixmap()
        if not pm.isNull():
            icon_lbl.setPixmap(
                pm.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color:#ffffff; font-weight:700;")
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color:#c7d5e0;")
        text_col.addWidget(title_lbl)
        text_col.addWidget(desc_lbl)
        layout.addLayout(text_col, 1)

        self.setStyleSheet(
            """
            #AchievementPopup {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1f344a,
                    stop:0.45 #192a3d,
                    stop:1 #12202f
                );
                border: 1px solid #3b6a96;
                border-radius: 10px;
            }
            """
        )

        self._slide_in = QPropertyAnimation(self, b"pos")
        self._slide_in.setDuration(220)
        self._slide_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in.setDuration(220)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)

        self._slide_out = QPropertyAnimation(self, b"pos")
        self._slide_out.setDuration(220)
        self._slide_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(220)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.close)

    def show_animated(self, anchor: QPoint, hold_ms: int = 2600) -> None:
        """Show popup with slide/fade animations."""

        start = QPoint(anchor.x() + 28, anchor.y())
        self.move(start)
        self.show()

        self._slide_in.stop()
        self._fade_in.stop()
        self._slide_in.setStartValue(start)
        self._slide_in.setEndValue(anchor)
        self._slide_in.start()
        self._fade_in.start()

        QTimer.singleShot(hold_ms, lambda: self.hide_animated(anchor))

    def hide_animated(self, current: QPoint) -> None:
        """Hide popup with slide/fade animations."""

        end = QPoint(current.x() + 28, current.y())
        self._slide_out.stop()
        self._fade_out.stop()
        self._slide_out.setStartValue(current)
        self._slide_out.setEndValue(end)
        self._slide_out.start()
        self._fade_out.start()
