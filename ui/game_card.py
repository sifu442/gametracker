"""
GameCard widget for displaying individual game information
"""
from pathlib import Path
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from core.constants import SCRIPT_DIR
from utils.helpers import fix_path_str


class GameCard(QFrame):
    """Widget representing a single game card"""
    play_clicked = pyqtSignal(str)
    remove_clicked = pyqtSignal(str)
    edit_clicked = pyqtSignal(str)
    stop_clicked = pyqtSignal(str)
    
    def __init__(self, game_id, game_data, total_playtime, is_playing=False):
        super().__init__()
        self.game_id = game_id
        self.is_playing = is_playing
        self.buttons_widget = None
        self.setMouseTracking(True)
        self.setup_ui(game_data, total_playtime)
        
    def setup_ui(self, game_data, total_playtime):
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(2)
        self.setMaximumWidth(200)
        
        layout = QVBoxLayout()
        
        # Cover image container with buttons overlay
        cover_container = QWidget()
        cover_container.setFixedSize(180, 240)
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.setSpacing(0)
        
        cover_label = QLabel()
        cover_label.setFixedSize(180, 240)
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setStyleSheet("background-color: transparent; color: white;")
        
        cover_path = game_data.get('cover')
        if cover_path:
            cover_file = Path(fix_path_str(cover_path))
            if not cover_file.is_absolute():
                cover_file = SCRIPT_DIR / cover_file
            
            if cover_file.exists():
                pixmap = QPixmap(cover_file.as_posix())
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        180, 240, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    cover_label.setPixmap(scaled_pixmap)
                else:
                    cover_label.setText("[No Cover]")
            else:
                cover_label.setText("[No Cover]")
        else:
            cover_label.setText("[No Cover]")
        
        cover_layout.addWidget(cover_label)
        
        # Create buttons overlay - hidden by default
        self.buttons_widget = QWidget()
        self.buttons_widget.setVisible(self.is_playing)
        buttons_layout = QHBoxLayout(self.buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 5)
        buttons_layout.setSpacing(3)
        buttons_layout.addStretch()
        
        if self.is_playing:
            stop_btn = QPushButton("⏹")
            stop_btn.setFixedSize(32, 32)
            stop_btn.setStyleSheet(
                "background-color: #FF9800; color: white; border: none; "
                "border-radius: 16px; font-weight: bold; font-size: 14px;"
            )
            stop_btn.clicked.connect(lambda: self.stop_clicked.emit(self.game_id))
            buttons_layout.addWidget(stop_btn)
        else:
            play_btn = QPushButton("▶")
            play_btn.setFixedSize(32, 32)
            play_btn.setStyleSheet(
                "background-color: #4CAF50; color: white; border: none; "
                "border-radius: 16px; font-weight: bold; font-size: 14px;"
            )
            play_btn.clicked.connect(lambda: self.play_clicked.emit(self.game_id))
            buttons_layout.addWidget(play_btn)
            
            edit_btn = QPushButton("✏")
            edit_btn.setFixedSize(32, 32)
            edit_btn.setStyleSheet(
                "background-color: #2196F3; color: white; border: none; "
                "border-radius: 16px; font-weight: bold; font-size: 14px;"
            )
            edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.game_id))
            buttons_layout.addWidget(edit_btn)
            
            remove_btn = QPushButton("🗑")
            remove_btn.setFixedSize(32, 32)
            remove_btn.setStyleSheet(
                "background-color: #f44336; color: white; border: none; "
                "border-radius: 16px; font-weight: bold; font-size: 14px;"
            )
            remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.game_id))
            buttons_layout.addWidget(remove_btn)
        
        buttons_layout.addStretch()
        
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_layout.addStretch()
        cover_layout.addWidget(
            self.buttons_widget, 
            alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter
        )
        
        layout.addWidget(cover_container)
        
        # Game name
        name_label = QLabel(game_data['name'])
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(name_label)
        
        # Playtime
        playtime_label = QLabel(f"⏱ {self.format_time(total_playtime)}")
        playtime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        playtime_label.setStyleSheet("color: #666;")
        layout.addWidget(playtime_label)
        
        self.setLayout(layout)
    
    def enterEvent(self, event):
        """Show buttons on mouse hover (if not playing)"""
        if not self.is_playing:
            self.buttons_widget.setVisible(True)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide buttons when mouse leaves (if not playing)"""
        if not self.is_playing:
            self.buttons_widget.setVisible(False)
        super().leaveEvent(event)
    
    def set_playing(self, is_playing):
        """Update playing state and refresh button visibility"""
        self.is_playing = is_playing
        if hasattr(self, 'buttons_widget'):
            self.buttons_widget.setParent(None)
            self.buttons_widget.deleteLater()
        self.buttons_widget.setVisible(is_playing)
    
    def format_time(self, seconds):
        """Format time in seconds to readable string"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return f"{int(seconds)}s"
