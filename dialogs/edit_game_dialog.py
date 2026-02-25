"""
Edit Game Dialog - Comprehensive game editing interface
"""
from pathlib import Path
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QSpinBox, QPushButton, QTabWidget, QWidget,
    QLabel, QGroupBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from core.constants import COVERS_DIR, LOGOS_DIR, HEROES_DIR
from utils.helpers import fix_path_str


class EditGameDialog(QDialog):
    game_updated = pyqtSignal(dict)  # will send updated data back

    def __init__(self, game_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Game")
        self.setMinimumWidth(400)

        self.game_data = game_data
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Tab widget for different sections
        tabs = QTabWidget()
        
        # --- Basic Info Tab ---
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)

        # Main horizontal layout: only the form (cover moved to Media tab)
        main_h = QHBoxLayout()

        # --- Right: Form fields ---
        form = QFormLayout()

        self.name_input = QLineEdit(self.game_data.get("name", ""))
        self.genre_input = QLineEdit(self.game_data.get("genre", ""))
        self.platform_input = QLineEdit(self.game_data.get("platform", ""))
        self.notes_input = QTextEdit(self.game_data.get("notes", ""))

        self.playtime_input = QSpinBox()
        self.playtime_input.setRange(0, 100000)
        self.playtime_input.setValue(self.game_data.get("playtime", 0))

        form.addRow("Name:", self.name_input)
        form.addRow("Genre:", self.genre_input)
        form.addRow("Platform:", self.platform_input)
        form.addRow("Playtime (mins):", self.playtime_input)
        form.addRow("Notes:", self.notes_input)

        # Exe path fields - platform specific
        exe_paths = self.game_data.get('exe_paths', {})
        # Support old format
        if isinstance(exe_paths, str):
            exe_paths = {'Windows': '', 'Linux': ''}
        
        self.exe_input_windows = QLineEdit(exe_paths.get('Windows', ''))
        self.exe_input_windows.setPlaceholderText("Windows .exe path")
        win_layout = QHBoxLayout()
        win_layout.addWidget(self.exe_input_windows)
        win_browse_btn = QPushButton("Browse")
        win_browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a66cc;
            }
        """)
        win_browse_btn.clicked.connect(lambda: self.browse_exe('Windows'))
        win_layout.addWidget(win_browse_btn)
        form.addRow("Windows Exe:", win_layout)
        
        self.exe_input_linux = QLineEdit(exe_paths.get('Linux', ''))
        self.exe_input_linux.setPlaceholderText("Linux executable path")
        linux_layout = QHBoxLayout()
        linux_layout.addWidget(self.exe_input_linux)
        linux_browse_btn = QPushButton("Browse")
        linux_browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a66cc;
            }
        """)
        linux_browse_btn.clicked.connect(lambda: self.browse_exe('Linux'))
        linux_layout.addWidget(linux_browse_btn)
        form.addRow("Linux Exe:", linux_layout)

        main_h.addLayout(form, 1)

        basic_layout.addLayout(main_h)

        tabs.addTab(basic_tab, "Basic Info")

        # --- Media Tab ---
        media_tab = QWidget()
        media_layout = QVBoxLayout(media_tab)

        # Cover section
        cover_group = QGroupBox("Cover")
        cover_section = QVBoxLayout(cover_group)
        
        cover_preview_label = QLabel()
        cover_preview_label.setFixedSize(150, 200)
        cover_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_preview_label.setStyleSheet("background-color: transparent; color: white;")
        self.media_cover_preview = cover_preview_label
        cover_section.addWidget(cover_preview_label)

        cover_input_layout = QHBoxLayout()
        self.media_cover_input = QLineEdit()
        self.media_cover_input.setPlaceholderText("File path or URL")
        cover_input_layout.addWidget(self.media_cover_input)
        cover_browse_media_btn = QPushButton("Browse")
        cover_browse_media_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a66cc;
            }
        """)
        cover_browse_media_btn.clicked.connect(lambda: self.browse_media_file('cover'))
        cover_input_layout.addWidget(cover_browse_media_btn)
        
        cover_download_btn = QPushButton("Download")
        cover_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #FB8C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        cover_download_btn.clicked.connect(lambda: self.download_media('cover'))
        cover_input_layout.addWidget(cover_download_btn)
        cover_section.addLayout(cover_input_layout)

        media_layout.addWidget(cover_group)

        # Logo section
        logo_group = QGroupBox("Logo")
        logo_section = QVBoxLayout(logo_group)
        
        logo_preview_label = QLabel()
        logo_preview_label.setFixedSize(150, 100)
        logo_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_preview_label.setStyleSheet("background-color: transparent; color: white;")
        self.media_logo_preview = logo_preview_label
        logo_section.addWidget(logo_preview_label)

        logo_input_layout = QHBoxLayout()
        self.media_logo_input = QLineEdit()
        self.media_logo_input.setPlaceholderText("File path or URL")
        logo_input_layout.addWidget(self.media_logo_input)
        logo_browse_media_btn = QPushButton("Browse")
        logo_browse_media_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a66cc;
            }
        """)
        logo_browse_media_btn.clicked.connect(lambda: self.browse_media_file('logo'))
        logo_input_layout.addWidget(logo_browse_media_btn)
        
        download_logo_btn = QPushButton("Download")
        download_logo_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #FB8C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        download_logo_btn.clicked.connect(lambda: self.download_media('logo'))
        logo_input_layout.addWidget(download_logo_btn)
        logo_section.addLayout(logo_input_layout)

        media_layout.addWidget(logo_group)

        # Hero section
        hero_group = QGroupBox("Hero Image")
        hero_section = QVBoxLayout(hero_group)
        
        hero_preview_label = QLabel()
        hero_preview_label.setFixedSize(300, 150)
        hero_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_preview_label.setStyleSheet("background-color: transparent; color: white;")
        self.media_hero_preview = hero_preview_label
        hero_section.addWidget(hero_preview_label)

        hero_input_layout = QHBoxLayout()
        self.media_hero_input = QLineEdit()
        self.media_hero_input.setPlaceholderText("File path or URL")
        hero_input_layout.addWidget(self.media_hero_input)
        hero_browse_media_btn = QPushButton("Browse")
        hero_browse_media_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a66cc;
            }
        """)
        hero_browse_media_btn.clicked.connect(lambda: self.browse_media_file('hero'))
        hero_input_layout.addWidget(hero_browse_media_btn)
        
        download_hero_btn = QPushButton("Download")
        download_hero_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #FB8C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        download_hero_btn.clicked.connect(lambda: self.download_media('hero'))
        hero_input_layout.addWidget(download_hero_btn)
        hero_section.addLayout(hero_input_layout)

        media_layout.addWidget(hero_group)
        media_layout.addStretch()

        tabs.addTab(media_tab, "Media")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")

        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3a8b40;
            }
        """)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c2160b;
            }
        """)

        save_btn.clicked.connect(self.save_game)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def browse_cover(self):
        """Browse for a new cover image for editing"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image", "",
            "Image files (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*.*)"
        )
        if filename:
            # Put selected cover into Media tab inputs and update media preview
            try:
                self.media_cover_input.setText(filename)
                self.update_media_preview('cover', filename)
            except Exception:
                pass

    def browse_media_file(self, media_type):
        """Browse for media file (cover or logo) in Media tab"""
        filename, _ = QFileDialog.getOpenFileName(
            self, f"Select {media_type.title()}", "",
            "Image files (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*.*)"
        )
        if filename:
            if media_type == 'cover':
                self.media_cover_input.setText(filename)
                self.update_media_preview('cover', filename)
            elif media_type == 'logo':
                self.media_logo_input.setText(filename)
                self.update_media_preview('logo', filename)
            elif media_type == 'hero':
                self.media_hero_input.setText(filename)
                self.update_media_preview('hero', filename)

    def download_media(self, media_type):
        """Download media from URL and save locally"""
        if media_type == 'cover':
            url_input = self.media_cover_input
        elif media_type == 'logo':
            url_input = self.media_logo_input
        else:  # hero
            url_input = self.media_hero_input
        
        url = url_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Error", f"Please enter a {media_type} URL")
            return
        
        if not url.startswith(('http://', 'https://')):
            QMessageBox.warning(self, "Error", "URL must start with http:// or https://")
            return
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Determine file extension from URL or content-type
                ext = '.jpg'
                if 'content-type' in response.headers:
                    ctype = response.headers['content-type'].lower()
                    if 'png' in ctype:
                        ext = '.png'
                    elif 'gif' in ctype:
                        ext = '.gif'
                
                # Save to appropriate directory
                if media_type == 'cover':
                    target_dir = COVERS_DIR
                elif media_type == 'logo':
                    target_dir = LOGOS_DIR
                else:  # hero
                    target_dir = HEROES_DIR
                    
                filename = f"{self.game_data.get('name', 'media').replace(' ', '_')}{ext}"
                filepath = target_dir / filename
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                url_input.setText(str(filepath))
                self.update_media_preview(media_type, str(filepath))
                QMessageBox.information(self, "Success", f"{media_type.title()} downloaded and saved!")
            else:
                QMessageBox.critical(self, "Error", f"Failed to download: HTTP {response.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Download failed: {e}")

    def update_media_preview(self, media_type, image_path):
        """Update media preview in Media tab"""
        if media_type == 'cover':
            preview_label = self.media_cover_preview
            size = (150, 200)
        elif media_type == 'logo':
            preview_label = self.media_logo_preview
            size = (150, 100)
        else:  # hero
            preview_label = self.media_hero_preview
            size = (300, 150)
        
        pixmap = QPixmap(Path(fix_path_str(image_path)).as_posix())
        if not pixmap.isNull():
            scaled = pixmap.scaled(size[0], size[1], Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            preview_label.setPixmap(scaled)
        else:
            preview_label.setText("Invalid image")

    def browse_exe(self, platform='Windows'):
        """Browse for game executable"""
        filename, _ = QFileDialog.getOpenFileName(
            self, f"Select {platform} Game Executable", "",
            "Executable files (*.exe *.sh);;All files (*.*)"
        )
        if filename:
            if platform == 'Windows':
                self.exe_input_windows.setText(filename)
            else:
                self.exe_input_linux.setText(filename)

    def update_preview(self, image_path):
        """Proxy to update media cover preview (kept for compatibility)."""
        try:
            # Treat update_preview as updating the Media tab cover preview
            self.media_cover_input.setText(image_path)
            self.update_media_preview('cover', image_path)
        except Exception:
            pass

    def save_game(self):
        # Read cover from Media tab (cover removed from Basic Info)
        cover_temp = self.media_cover_input.text().strip()
        # Only treat as a new cover when different from existing stored cover
        if cover_temp == self.game_data.get('cover', ''):
            cover_temp = ""
        
        # Get logo from Media tab
        logo_temp = self.media_logo_input.text().strip()
        if logo_temp == self.game_data.get('logo', ''):
            logo_temp = ""
        
        # Get hero from Media tab
        hero_temp = self.media_hero_input.text().strip()
        if hero_temp == self.game_data.get('hero', ''):
            hero_temp = ""

        updated_data = {
            "name": self.name_input.text(),
            "genre": self.genre_input.text(),
            "platform": self.platform_input.text(),
            "playtime": self.playtime_input.value(),
            "notes": self.notes_input.toPlainText(),
            "exe_paths": {
                "Windows": self.exe_input_windows.text().strip(),
                "Linux": self.exe_input_linux.text().strip()
            },
            # cover_temp contains the path to a newly selected cover (if any)
            "cover_temp": cover_temp,
            "logo_temp": logo_temp,
            "hero_temp": hero_temp
        }

        self.game_updated.emit(updated_data)
        self.accept()
