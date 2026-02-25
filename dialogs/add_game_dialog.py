"""
Add Game Dialog - Wizard for adding new games to library
"""
import shutil
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from core.constants import (
    IS_WINDOWS, IS_LINUX, DEFAULT_PROTON_PATH, 
    COVERS_DIR, SCRIPT_DIR
)
from threads.igdb_downloader import IGDBDownloader
from ui.styles import BUTTON_PRIMARY, BUTTON_SUCCESS, BUTTON_WARNING
from utils.helpers import fix_path_str


class AddGameWidget(QWidget):
    """Widget for adding new games to the library"""
    
    def __init__(self, game_manager, config, parent=None):
        super().__init__(parent)
        self.game_manager = game_manager
        self.config = config
        self.download_thread = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the add game interface"""
        layout = QVBoxLayout(self)
        
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        
        # Title
        title = QLabel("Add New Game")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        form_layout.addRow(title)
        
        # Game name with IGDB search
        name_layout = QHBoxLayout()
        self.game_name_input = QLineEdit()
        name_layout.addWidget(self.game_name_input)
        
        search_btn = QPushButton("🔍 Search IGDB")
        search_btn.setStyleSheet(BUTTON_WARNING)
        search_btn.clicked.connect(self.search_igdb)
        name_layout.addWidget(search_btn)
        
        form_layout.addRow("Game Name:", name_layout)
        
        # Executable path
        exe_layout = QHBoxLayout()
        self.exe_input = QLineEdit()
        exe_layout.addWidget(self.exe_input)
        
        exe_browse_btn = QPushButton("Browse")
        exe_browse_btn.setStyleSheet(BUTTON_PRIMARY)
        exe_browse_btn.clicked.connect(self.browse_exe)
        exe_layout.addWidget(exe_browse_btn)
        
        form_layout.addRow("Executable Path:", exe_layout)
        
        # Cover image
        cover_layout = QHBoxLayout()
        self.cover_temp_input = QLineEdit()
        self.cover_temp_input.setReadOnly(True)
        self.cover_temp_input.setPlaceholderText("Download from IGDB or browse manually")
        cover_layout.addWidget(self.cover_temp_input)
        
        cover_browse_btn = QPushButton("Browse")
        cover_browse_btn.setStyleSheet(BUTTON_PRIMARY)
        cover_browse_btn.clicked.connect(self.browse_cover)
        cover_layout.addWidget(cover_browse_btn)
        
        form_layout.addRow("Cover Image:", cover_layout)
        
        # Proton path (Linux only)
        if IS_LINUX:
            proton_layout = QHBoxLayout()
            self.proton_input = QLineEdit()
            self.proton_input.setText(str(DEFAULT_PROTON_PATH))
            proton_layout.addWidget(self.proton_input)
            
            proton_browse_btn = QPushButton("Browse")
            proton_browse_btn.setStyleSheet(BUTTON_PRIMARY)
            proton_browse_btn.clicked.connect(self.browse_proton)
            proton_layout.addWidget(proton_browse_btn)
            
            form_layout.addRow("Proton Path:", proton_layout)
        
        # Cover preview
        preview_group = QGroupBox("Cover Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.cover_preview = QLabel()
        self.cover_preview.setFixedSize(200, 300)
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setStyleSheet("background-color: transparent; color: white;")
        self.cover_preview.setText("No image")
        preview_layout.addWidget(self.cover_preview, alignment=Qt.AlignmentFlag.AlignCenter)
        
        form_layout.addRow(preview_group)
        
        # Add button
        add_btn = QPushButton("➕ Add Game to Library")
        add_btn.setStyleSheet(BUTTON_SUCCESS)
        add_btn.clicked.connect(self.add_game)
        form_layout.addRow(add_btn)
        
        layout.addWidget(form_widget)
        layout.addStretch()
    
    def browse_exe(self):
        """Browse for game executable"""
        file_filter = "Executable files (*.exe);;All files (*.*)" if IS_WINDOWS else "All files (*.*)"
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Game Executable", "", file_filter
        )
        if filename:
            self.exe_input.setText(filename)
            # Auto-fill name if empty
            if not self.game_name_input.text():
                self.game_name_input.setText(Path(filename).stem)
    
    def browse_cover(self):
        """Browse for cover image"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image", "",
            "Image files (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*.*)"
        )
        if filename:
            self.cover_temp_input.setText(filename)
            self.update_preview(filename)
    
    def browse_proton(self):
        """Browse for Proton directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Proton Directory")
        if directory:
            self.proton_input.setText(directory)
    
    def update_preview(self, image_path):
        """Update cover preview"""
        pixmap = QPixmap(Path(fix_path_str(image_path)).as_posix())
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                200, 300, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_preview.setPixmap(scaled)
        else:
            self.cover_preview.setText("Invalid image")
    
    def search_igdb(self):
        """Search IGDB for game cover"""
        game_name = self.game_name_input.text().strip()
        if not game_name:
            QMessageBox.warning(self, "Error", "Please enter a game name first")
            return
        
        client_id = self.config.get('igdb_client_id')
        client_secret = self.config.get('igdb_client_secret')
        
        if not client_id or not client_secret:
            QMessageBox.warning(
                self, "Error", 
                "Please configure IGDB API in Settings tab first"
            )
            return
        
        if hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(f"Searching IGDB for '{game_name}'...")
        
        # Create and start download thread
        self.download_thread = IGDBDownloader(game_name, client_id, client_secret)
        self.download_thread.finished.connect(self.on_igdb_download_finished)
        self.download_thread.start()
    
    def on_igdb_download_finished(self, success, image_path, game_name):
        """Handle IGDB download completion"""
        if success:
            self.cover_temp_input.setText(image_path)
            self.update_preview(image_path)
            if hasattr(self.parent(), 'statusBar'):
                self.parent().statusBar().showMessage(f"✓ Cover downloaded for '{game_name}'")
            QMessageBox.information(self, "Success", f"Cover downloaded for '{game_name}'!")
        else:
            if hasattr(self.parent(), 'statusBar'):
                self.parent().statusBar().showMessage("No cover found")
            QMessageBox.warning(
                self, "Not Found", 
                f"No cover found for '{self.game_name_input.text()}'.\n\n"
                "Try a different name or upload manually."
            )
    
    def add_game(self):
        """Add game to library"""
        name = self.game_name_input.text().strip()
        exe_path = self.exe_input.text().strip()
        temp_cover = self.cover_temp_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a game name")
            return
        
        if not exe_path or not Path(exe_path).exists():
            QMessageBox.warning(self, "Error", "Please select a valid executable file")
            return
        
        # Copy cover to permanent location
        final_cover_path = None
        if temp_cover and Path(temp_cover).exists():
            cover_ext = Path(temp_cover).suffix
            final_cover_name = f"{name.replace(' ', '_')}{cover_ext}"
            final_cover_path = COVERS_DIR / final_cover_name
            
            try:
                shutil.copy(temp_cover, final_cover_path)
                # Store as relative path from SCRIPT_DIR
                final_cover_path = str(final_cover_path.relative_to(SCRIPT_DIR))
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Failed to copy cover: {e}")
                final_cover_path = None
        
        # Get proton path for Linux
        proton_path = None
        if IS_LINUX:
            proton_path = self.proton_input.text().strip()
        
        # Prepare game data
        game_data = {
            'name': name,
            'exe_paths': {
                'Windows': exe_path if IS_WINDOWS else '',
                'Linux': exe_path if IS_LINUX else ''
            },
            'cover': final_cover_path,
            'proton_path': proton_path,
            'process_name': Path(exe_path).stem,
            'added_date': time.time(),
            'genre': '',
            'platform': 'Windows' if IS_WINDOWS else 'Linux',
            'notes': '',
            'playtime': 0
        }
        
        # Add to library using game manager
        success, game_id, message = self.game_manager.add_game(game_data)
        
        if success:
            # Clear form
            self.game_name_input.clear()
            self.exe_input.clear()
            self.cover_temp_input.clear()
            self.cover_preview.clear()
            self.cover_preview.setText("No image")
            if IS_LINUX:
                self.proton_input.setText(str(DEFAULT_PROTON_PATH))
            
            QMessageBox.information(self, "Success", message)
            
            # Notify parent to refresh library
            if hasattr(self.parent(), 'refresh_library'):
                self.parent().refresh_library()
        else:
            QMessageBox.warning(self, "Error", message)
