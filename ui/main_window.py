"""
Main Application Window - Game Library Tracker
"""
import subprocess
import shutil
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

import psutil
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QScrollArea, QGridLayout, QFrame,
    QMessageBox, QSizePolicy, QStackedLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPixmap

from core.constants import (
    IS_WINDOWS, IS_LINUX, LIBRARY_FILE, TRACKING_FILE, CONFIG_FILE,
    COVERS_DIR, SCRIPT_DIR
)
from core.game_manager import GameManager
from ui.game_card import GameCard
from dialogs.edit_game_dialog import EditGameDialog
from dialogs.add_game_dialog import AddGameWidget
from dialogs.settings_dialog import SettingsWidget
from threads.process_monitor import ProcessMonitor
from utils.helpers import load_json, save_json, format_playtime, fix_path_str, resolve_user_path
from utils.game_launcher import GameLauncher


class GameLibraryTracker(QMainWindow):
    """Main application window for Game Library Tracker"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Library Tracker")
        self.setMinimumSize(1000, 700)
        
        # Initialize game manager
        self.game_manager = GameManager()
        self.config = load_json(CONFIG_FILE, {})
        
        # Tracking state
        self.is_monitoring = False
        self.monitor_thread = None
        self.current_game_id = None
        self.current_pid = None
        self.session_start = None
        
        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        
        # View mode
        self.current_view_mode = 'grid'  # 'grid' or 'details'
        
        self.setup_ui()
        self.refresh_library()
    
    def setup_ui(self):
        """Setup main user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Library tab
        library_tab = QWidget()
        self.setup_library_tab(library_tab)
        tabs.addTab(library_tab, "📚 Library")
        
        # Add game tab
        add_tab = QWidget()
        self.setup_add_tab(add_tab)
        tabs.addTab(add_tab, "➕ Add Game")
        
        # Now playing tab
        playing_tab = QWidget()
        self.setup_playing_tab(playing_tab)
        tabs.addTab(playing_tab, "🎮 Now Playing")
        
        # Settings tab
        settings_tab = QWidget()
        self.setup_settings_tab(settings_tab)
        tabs.addTab(settings_tab, "⚙️ Settings")
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def setup_library_tab(self, parent):
        """Setup library tab with game grid"""
        layout = QVBoxLayout(parent)
        
        # Header with controls
        header = QHBoxLayout()
        title = QLabel("My Game Library")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        # View mode buttons
        grid_view_btn = QPushButton("📊 Grid View")
        grid_view_btn.setCheckable(True)
        grid_view_btn.setChecked(True)
        grid_view_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #333;
                border-radius: 4px;
                background-color: #2a2a2a;
                color: white;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #555;
            }
            QPushButton:checked {
                background-color: #4CAF50;
                color: white;
                border: 1px solid #45a049;
            }
        """)
        grid_view_btn.clicked.connect(lambda: self.switch_view_mode('grid'))
        header.addWidget(grid_view_btn)
        
        details_view_btn = QPushButton("📋 Details View")
        details_view_btn.setCheckable(True)
        details_view_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #333;
                border-radius: 4px;
                background-color: #2a2a2a;
                color: white;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #555;
            }
            QPushButton:checked {
                background-color: #4CAF50;
                color: white;
                border: 1px solid #45a049;
            }
        """)
        details_view_btn.clicked.connect(lambda: self.switch_view_mode('details'))
        header.addWidget(details_view_btn)
        
        # Store button references
        self.grid_view_btn = grid_view_btn
        self.details_view_btn = details_view_btn
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #333;
                border-radius: 4px;
                background-color: #2a2a2a;
                color: white;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #555;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_library)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # Scrollable area for views
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Grid view container
        self.library_container = QWidget()
        self.library_layout = QGridLayout(self.library_container)
        self.library_layout.setSpacing(20)

        # Details view container (left list + right detail panel)
        self.details_container = QWidget()
        self.details_split_layout = QHBoxLayout(self.details_container)
        self.details_split_layout.setContentsMargins(0, 0, 0, 0)

        self.details_left_widget = QWidget()
        self.details_left_layout = QVBoxLayout(self.details_left_widget)
        self.details_left_layout.setContentsMargins(0, 0, 0, 0)

        self.details_right_widget = QWidget()
        self.details_right_layout = QVBoxLayout(self.details_right_widget)
        self.details_right_layout.setContentsMargins(10, 10, 10, 10)

        self.details_split_layout.addWidget(self.details_left_widget, 40)
        self.details_split_layout.addWidget(self.details_right_widget, 60)

        # View stack (swap between grid and details)
        self.view_stack = QWidget()
        self.view_layout = QVBoxLayout(self.view_stack)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.addWidget(self.library_container)  # default view

        scroll.setWidget(self.view_stack)
        layout.addWidget(scroll)
    
    def setup_add_tab(self, parent):
        """Setup add game tab"""
        layout = QVBoxLayout(parent)
        self.add_game_widget = AddGameWidget(self.game_manager, self.config, self)
        layout.addWidget(self.add_game_widget)
    
    def setup_playing_tab(self, parent):
        """Setup now playing tab"""
        layout = QVBoxLayout(parent)
        
        # Title
        title = QLabel("🎮 Now Playing")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)
        
        # Game info display
        self.playing_label = QLabel("No game currently running")
        self.playing_label.setStyleSheet("font-size: 14pt; padding: 20px;")
        self.playing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.playing_label)
        
        # Session info
        self.session_label = QLabel("")
        self.session_label.setStyleSheet("font-size: 12pt; padding: 10px;")
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.session_label)
        
        # Stop button
        self.stop_game_btn = QPushButton("⏹ Stop Game")
        self.stop_game_btn.setEnabled(False)
        self.stop_game_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12pt;
            }
            QPushButton:hover:enabled {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c2160b;
            }
            QPushButton:disabled {
                background-color: #666;
            }
        """)
        self.stop_game_btn.clicked.connect(self.stop_playing_from_tab)
        layout.addWidget(self.stop_game_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()
    
    def setup_settings_tab(self, parent):
        """Setup settings tab"""
        layout = QVBoxLayout(parent)
        self.settings_widget = SettingsWidget(self.config, self)
        layout.addWidget(self.settings_widget)
    
    def switch_view_mode(self, mode):
        """Switch between grid and details view"""
        self.current_view_mode = mode
        
        # Update button states
        self.grid_view_btn.setChecked(mode == 'grid')
        self.details_view_btn.setChecked(mode == 'details')

        # Clear the view layout
        while self.view_layout.count():
            item = self.view_layout.takeAt(0)
            if item.widget():
                item.widget().hide()

        # Show the appropriate container
        if mode == 'grid':
            self.view_layout.addWidget(self.library_container)
            self.library_container.show()
        else:
            self.view_layout.addWidget(self.details_container)
            self.details_container.show()

        self.refresh_library()

    def _with_linux_game_performance(self, cmd):
        if IS_LINUX and cmd and cmd[0] != "game-performance":
            return ["game-performance"] + cmd
        return cmd
    
    def refresh_library(self):
        """Refresh the library display"""
        if self.current_view_mode == 'grid':
            self.refresh_grid_view()
        else:
            self.refresh_details_view()
    
    def refresh_grid_view(self):
        """Refresh library in grid view"""
        # Clear existing cards
        while self.library_layout.count():
            item = self.library_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        library_data = self.game_manager.get_all_games()

        if not library_data:
            # Show empty state
            empty_label = QLabel("No games in library Add games using the '➕ Add Game' tab")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("font-size: 14pt; color: #666; padding: 40px;")
            self.library_layout.addWidget(empty_label, 0, 0)
            return

        # Add game cards
        row, col = 0, 0
        max_cols = 4

        for game_id, game_data in library_data.items():
            # Get playtime
            process_name = game_data.get('process_name', '')
            total_playtime = self.game_manager.get_total_playtime(process_name)

            # Check if this game is currently playing
            is_playing = (self.is_monitoring and self.current_game_id == game_id)

            # Create game card
            card = GameCard(game_id, game_data, total_playtime, is_playing)
            card.play_clicked.connect(self.play_game)
            card.remove_clicked.connect(self.remove_game)
            card.edit_clicked.connect(self.edit_game)
            card.stop_clicked.connect(self.stop_playing)

            self.library_layout.addWidget(card, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Add stretch to push cards to top
        self.library_layout.setRowStretch(row + 1, 1)

    def refresh_details_view(self):
        """Refresh details view with left list and right details panel"""
        # Clear existing items in left and right columns
        for layout in (self.details_left_layout, self.details_right_layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        library_data = self.game_manager.get_all_games()

        if not library_data:
            label = QLabel("No games in library. Add some in the '➕ Add Game' tab!")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: gray; font-size: 12pt;")
            self.details_left_layout.addWidget(label)
            return

        # Store game row widgets and name buttons for later selection highlighting
        self.game_row_widgets = {}
        self.game_row_name_buttons = {}

        for game_id, game_data in library_data.items():
            # Create a row for logo + clickable name
            game_row = QWidget()
            game_row_layout = QHBoxLayout(game_row)
            game_row_layout.setContentsMargins(2, 2, 2, 2)
            game_row_layout.setSpacing(8)
            game_row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            # Logo (left side)
            logo_label = QLabel()
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("background-color: transparent;")
            logo_label.setFixedSize(24, 24)
            logo_label.setScaledContents(False)

            logo_path = game_data.get('logo')
            if logo_path:
                logo_file = Path(fix_path_str(logo_path))
                if not logo_file.is_absolute():
                    logo_file = SCRIPT_DIR / logo_file
                if logo_file.exists():
                    pixmap = QPixmap(logo_file.as_posix())
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        logo_label.setPixmap(scaled)
                    else:
                        logo_label.setText("Logo")
                else:
                    logo_label.setText("Logo")
            else:
                logo_label.setText("Logo")

            game_row_layout.addWidget(logo_label)

            # Clickable name button (right side)
            name_btn = QPushButton(game_data.get('name', game_id))
            name_btn.setFlat(True)
            name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            name_btn.setStyleSheet("text-align: left; font-weight: bold; font-size: 11pt; padding: 2px 6px; border: none;")
            name_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            name_btn.clicked.connect(lambda checked, gid=game_id: self.show_game_details(gid))
            game_row_layout.addWidget(name_btn, 1)

            # Store row widget and name button reference for highlighting
            self.game_row_widgets[game_id] = game_row
            self.game_row_name_buttons[game_id] = name_btn

            self.details_left_layout.addWidget(game_row)

        self.details_left_layout.addStretch()

        # Right panel default placeholder
        placeholder = QLabel("Select a game to see details...")
        placeholder.setStyleSheet("color: #999;")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.details_right_layout.addWidget(placeholder)
        self.details_right_layout.addStretch()

    def show_game_details(self, game_id):
        """Populate right details panel with Steam-like hero layout"""
        # Clear right layout
        while self.details_right_layout.count():
            item = self.details_right_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        library_data = self.game_manager.get_all_games()
        tracking_data = self.game_manager.tracking_data

        # Highlight selected game in left list (75% opacity)
        for gid, row_widget in self.game_row_widgets.items():
            logo_path = library_data.get(gid, {}).get('logo')
            has_logo = False
            if logo_path:
                logo_file = Path(fix_path_str(logo_path))
                if not logo_file.is_absolute():
                    logo_file = SCRIPT_DIR / logo_file
                has_logo = logo_file.exists()

            name_btn = self.game_row_name_buttons.get(gid)

            if gid == game_id:
                if has_logo:
                    row_widget.setStyleSheet("background-color: rgba(76, 175, 80, 0.75); border-radius: 3px;")
                    if name_btn:
                        name_btn.setStyleSheet("text-align: left; font-weight: bold; font-size: 11pt; padding: 2px 6px; border: none; background-color: transparent;")
                else:
                    row_widget.setStyleSheet("background-color: transparent;")
                    if name_btn:
                        name_btn.setStyleSheet("text-align: left; font-weight: bold; font-size: 11pt; padding: 2px 6px; border: none; background-color: rgba(76, 175, 80, 0.75); border-radius: 3px;")
            else:
                row_widget.setStyleSheet("background-color: transparent;")
                if name_btn:
                    name_btn.setStyleSheet("text-align: left; font-weight: bold; font-size: 11pt; padding: 2px 6px; border: none;")

        game_data = library_data.get(game_id)
        if not game_data:
            return

        # Main scrollable container
        main_container = QWidget()
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === HERO SECTION ===
        hero_container = QWidget()
        hero_container.setMinimumHeight(350)
        hero_container.setStyleSheet("background-color: #000;")
        hero_layout = QVBoxLayout(hero_container)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(0)

        # Hero background
        hero_bg_label = QLabel()
        hero_bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_bg_label.setScaledContents(False)

        hero_path = game_data.get('hero')
        if hero_path:
            hero_file = Path(fix_path_str(hero_path))
            if not hero_file.is_absolute():
                hero_file = SCRIPT_DIR / hero_file
            if hero_file.exists():
                hero_pixmap = QPixmap(hero_file.as_posix())
                if not hero_pixmap.isNull():
                    scaled_hero = hero_pixmap.scaledToWidth(900, Qt.TransformationMode.SmoothTransformation)
                    hero_bg_label.setPixmap(scaled_hero)
                    hero_bg_label.setMinimumHeight(int(scaled_hero.height() * 0.7))

        hero_bg_label.setStyleSheet("background-color: rgba(0, 0, 0, 0.6);")
        hero_layout.addWidget(hero_bg_label, 1)

        # Content overlay on hero
        hero_content = QWidget()
        hero_content.setStyleSheet("background-color: transparent;")
        hero_content_layout = QHBoxLayout(hero_content)
        hero_content_layout.setContentsMargins(30, 30, 30, 30)
        hero_content_layout.setSpacing(25)

        # Left: Cover image
        cover_label = QLabel()
        cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_label.setStyleSheet("background-color: #1a1a1a;")
        cover_label.setFixedSize(180, 260)

        cover_path = game_data.get('cover')
        if cover_path:
            cover_file = Path(fix_path_str(cover_path))
            if not cover_file.is_absolute():
                cover_file = SCRIPT_DIR / cover_file
            if cover_file.exists():
                pixmap = QPixmap(cover_file.as_posix())
                if not pixmap.isNull():
                    scaled = pixmap.scaled(180, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    cover_label.setPixmap(scaled)
                else:
                    cover_label.setText("[No Cover]")
            else:
                cover_label.setText("[No Cover]")
        else:
            cover_label.setText("[No Cover]")

        hero_content_layout.addWidget(cover_label, 0, Qt.AlignmentFlag.AlignTop)

        # Right: Title and action buttons
        right_section = QWidget()
        right_section.setStyleSheet("background-color: transparent;")
        right_layout = QVBoxLayout(right_section)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # Game title
        title_label = QLabel(game_data.get('name', ''))
        title_label.setStyleSheet("font-weight: bold; font-size: 18pt; color: white;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setWordWrap(True)
        right_layout.addWidget(title_label)

        # Action buttons row
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(10)

        play_btn = QPushButton("▶ Play")
        play_btn.setFixedHeight(40)
        play_btn.setMinimumWidth(120)
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3a8b40;
            }
        """)
        play_btn.clicked.connect(lambda _, gid=game_id: self.play_game(gid))

        edit_btn = QPushButton("✏ Edit")
        edit_btn.setFixedHeight(40)
        edit_btn.setMinimumWidth(100)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a66cc;
            }
        """)
        edit_btn.clicked.connect(lambda _, gid=game_id: self.edit_game(gid))

        remove_btn = QPushButton("🗑 Remove")
        remove_btn.setFixedHeight(40)
        remove_btn.setMinimumWidth(120)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c2160b;
            }
        """)
        remove_btn.clicked.connect(lambda _, gid=game_id: self.remove_game(gid))

        buttons_layout.addWidget(play_btn)
        buttons_layout.addWidget(edit_btn)
        buttons_layout.addWidget(remove_btn)
        buttons_layout.addStretch()

        right_layout.addWidget(buttons_container)

        # Stats section
        stats_container = QWidget()
        stats_container.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border-radius: 6px; padding: 15px;")
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(30)

        # Playtime stat
        process_name = game_data.get('process_name', '')
        total_seconds = 0
        if process_name in tracking_data:
            total_seconds = tracking_data[process_name].get('total_runtime', 0)

        playtime_hours = int(total_seconds // 3600)
        playtime_mins = int((total_seconds % 3600) // 60)

        last_played_text = "Never"
        if process_name in tracking_data:
            last_ts = tracking_data[process_name].get('last_session_end')
            if last_ts:
                try:
                    last_dt = datetime.fromtimestamp(last_ts)
                    delta = datetime.now() - last_dt
                    days = delta.days
                    if days <= 0:
                        last_played_text = "Today"
                    else:
                        last_played_text = f"{days}d ago"
                except Exception:
                    last_played_text = "Unknown"

        last_played_stat = QWidget()
        last_played_stat.setStyleSheet("background-color: transparent;")
        last_played_stat_layout = QVBoxLayout(last_played_stat)
        last_played_stat_layout.setContentsMargins(12, 12, 12, 12)
        last_played_stat_layout.setSpacing(4)
        last_played_title = QLabel("📅 Last Played")
        last_played_title.setStyleSheet("color: #999; font-size: 9pt;")
        last_played_value = QLabel(last_played_text)
        last_played_value.setStyleSheet("color: #fff; font-weight: bold; font-size: 12pt;")
        last_played_stat_layout.addWidget(last_played_title)
        last_played_stat_layout.addWidget(last_played_value)
        stats_layout.addWidget(last_played_stat)

        playtime_stat = QWidget()
        playtime_stat.setStyleSheet("background-color: transparent;")
        playtime_stat_layout = QVBoxLayout(playtime_stat)
        playtime_stat_layout.setContentsMargins(12, 12, 12, 12)
        playtime_stat_layout.setSpacing(4)
        playtime_label_title = QLabel("⏱ Time Played")
        playtime_label_title.setStyleSheet("color: #999; font-size: 9pt;")
        playtime_label_value = QLabel(f"{playtime_hours}h {playtime_mins}m")
        playtime_label_value.setStyleSheet("color: #fff; font-weight: bold; font-size: 12pt;")
        playtime_stat_layout.addWidget(playtime_label_title)
        playtime_stat_layout.addWidget(playtime_label_value)
        stats_layout.addWidget(playtime_stat)

        # Genre stat
        genre_stat = QWidget()
        genre_stat.setStyleSheet("background-color: transparent;")
        genre_stat_layout = QVBoxLayout(genre_stat)
        genre_stat_layout.setContentsMargins(12, 12, 12, 12)
        genre_stat_layout.setSpacing(4)
        genre_label_title = QLabel("🏷️ Genre")
        genre_label_title.setStyleSheet("color: #999; font-size: 9pt;")
        genre_label_value = QLabel(game_data.get('genre', 'N/A'))
        genre_label_value.setStyleSheet("color: #fff; font-weight: bold; font-size: 12pt;")
        genre_stat_layout.addWidget(genre_label_title)
        genre_stat_layout.addWidget(genre_label_value)
        stats_layout.addWidget(genre_stat)

        # Platform stat
        platform_stat = QWidget()
        platform_stat.setStyleSheet("background-color: transparent;")
        platform_stat_layout = QVBoxLayout(platform_stat)
        platform_stat_layout.setContentsMargins(12, 12, 12, 12)
        platform_stat_layout.setSpacing(4)
        platform_label_title = QLabel("💻 Platform")
        platform_label_title.setStyleSheet("color: #999; font-size: 9pt;")
        platform_label_value = QLabel(game_data.get('platform', 'N/A'))
        platform_label_value.setStyleSheet("color: #fff; font-weight: bold; font-size: 12pt;")
        platform_stat_layout.addWidget(platform_label_title)
        platform_stat_layout.addWidget(platform_label_value)
        stats_layout.addWidget(platform_stat)

        stats_layout.addStretch()
        right_layout.addWidget(stats_container)
        right_layout.addStretch()

        hero_content_layout.addWidget(right_section, 1)

        # Position overlay on hero
        hero_position = QWidget()
        hero_position_layout = QVBoxLayout(hero_position)
        hero_position_layout.setContentsMargins(0, 0, 0, 0)
        hero_position_layout.addWidget(hero_content)
        hero_position_layout.addStretch()
        hero_layout.addWidget(hero_position, 0)

        main_layout.addWidget(hero_container)

        # === INFO SECTION ===
        info_container = QWidget()
        info_container.setStyleSheet("background-color: #0f0f0f;")
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(30, 20, 30, 20)
        info_layout.setSpacing(12)

        # Notes section
        if game_data.get('notes'):
            notes_title = QLabel("Notes")
            notes_title.setStyleSheet("font-weight: bold; color: #ccc; font-size: 11pt;")
            notes_text = QLabel(game_data.get('notes', ''))
            notes_text.setStyleSheet("color: #999; font-size: 10pt;")
            notes_text.setWordWrap(True)
            info_layout.addWidget(notes_title)
            info_layout.addWidget(notes_text)
            info_layout.addSpacing(10)

        main_layout.addWidget(info_container)
        main_layout.addStretch()

        self.details_right_layout.addWidget(main_container)
        self.details_right_layout.addStretch()

    def get_exe_path_for_platform(self, game_data):
        """Get executable path for current platform"""
        exe_paths = game_data.get('exe_paths', {})
        
        if isinstance(exe_paths, str):
            # Old format - single exe_path
            return exe_paths
        
        # New format - platform-specific
        if IS_WINDOWS:
            return exe_paths.get('Windows', '')
        elif IS_LINUX:
            return exe_paths.get('Linux', '')
        
        return ''
    
    def play_game(self, game_id):
        """Launch a game"""
        if self.is_monitoring:
            QMessageBox.warning(
                self, "Already Playing",
                f"'{self.game_manager.get_game(self.current_game_id)['name']}' is already running.\n\n"
                "Stop it first before starting another game."
            )
            return
        
        game_data = self.game_manager.get_game(game_id)
        if not game_data:
            QMessageBox.critical(self, "Error", "Game not found")
            return
        
        exe_path = self.get_exe_path_for_platform(game_data)
        
        if not exe_path:
            QMessageBox.warning(
                self, "Error",
                f"No executable configured for {game_data['name']} on this platform.\n\n"
                "Please edit the game and set the executable path."
            )
            return
        
        exe_file = Path(exe_path)
        if not exe_file.exists():
            QMessageBox.warning(
                self, "Error",
                f"Executable not found:\n{exe_path}\n\n"
                "Please check the path in game settings."
            )
            return
        
        # Launch game
        try:
            if IS_WINDOWS:
                proc = subprocess.Popen([str(exe_file)], shell=True)
                pid = proc.pid
                start_time = psutil.Process(pid).create_time()
                
            elif IS_LINUX:
                compat_tool = (game_data.get("compat_tool") or "").strip().lower()
                proton_path = game_data.get('proton_path')
                wine_prefix = resolve_user_path((game_data.get("wine_prefix") or "").strip())
                use_proton = proton_path and Path(proton_path).exists()
                
                if compat_tool == "wine":
                    wine_cmd = ""
                    if proton_path:
                        candidate = Path(proton_path) / "bin" / "wine"
                        if candidate.exists():
                            wine_cmd = str(candidate)
                        else:
                            candidate = Path(proton_path) / "wine"
                            if candidate.exists():
                                wine_cmd = str(candidate)
                    if not wine_cmd:
                        wine_cmd = shutil.which("wine") or ""
                    if not wine_cmd:
                        QMessageBox.warning(
                            self, "Error",
                            "Wine is not installed or not found in PATH."
                        )
                        return
                    cmd = [wine_cmd, str(exe_file)]
                    cmd = self._with_linux_game_performance(cmd)
                    print(f"[launch][legacy] wine cmd={cmd}", flush=True)
                    env = None
                    if wine_prefix:
                        env = os.environ.copy()
                        env["WINEPREFIX"] = wine_prefix
                    proc = subprocess.Popen(cmd, env=env)
                    pid = proc.pid
                    start_time = psutil.Process(pid).create_time()
                elif use_proton or compat_tool == "proton":
                    if not proton_path:
                        QMessageBox.warning(
                            self, "Error",
                            "No Proton path configured.\n\n"
                            "Please set a Proton path in game settings."
                        )
                        return
                    proton_bin = Path(proton_path) / "proton"
                    if proton_bin.exists():
                        cmd = [str(proton_bin), "run", str(exe_file)]
                        cmd = self._with_linux_game_performance(cmd)
                        print(f"[launch][legacy] proton cmd={cmd}", flush=True)
                        env = None
                        if wine_prefix:
                            env = os.environ.copy()
                            env["STEAM_COMPAT_DATA_PATH"] = wine_prefix
                        proc = subprocess.Popen(cmd, env=env)
                        pid = proc.pid
                        start_time = psutil.Process(pid).create_time()
                    else:
                        QMessageBox.warning(
                            self, "Error",
                            f"Proton not found at:\n{proton_path}\n\n"
                            "Please check the path in Settings."
                        )
                        return
                else:
                    proc = subprocess.Popen(self._with_linux_game_performance([str(exe_file)]))
                    pid = proc.pid
                    start_time = psutil.Process(pid).create_time()
            
            # Start tracking
            self.start_tracking(game_id, pid, start_time)
            self.statusBar().showMessage(f"Launched '{game_data['name']}'")
            
        except Exception as e:
            QMessageBox.critical(
                self, "Launch Error",
                f"Failed to launch game:\n{e}"
            )
    
    def start_tracking(self, game_id, pid, start_time):
        """Start tracking game session"""
        self.current_game_id = game_id
        self.current_pid = pid
        self.session_start = time.time()
        self.is_monitoring = True
        
        # Update Now Playing tab
        game_data = self.game_manager.get_game(game_id)
        self.playing_label.setText(f"🎮 Playing: {game_data['name']}")
        self.session_label.setText("Session: 0m")
        self.stop_game_btn.setEnabled(True)
        
        # Start monitor thread
        self.monitor_thread = ProcessMonitor(pid, start_time)
        self.monitor_thread.game_ended.connect(self.on_game_ended)
        self.monitor_thread.start()
        
        # Start auto-save timer (save every 30 seconds)
        self.auto_save_timer.start(30000)
        
        # Refresh library to show stop button
        self.refresh_library()
    
    def auto_save(self):
        """Auto-save session data"""
        if self.is_monitoring and self.session_start:
            elapsed = int(time.time() - self.session_start)
            game_data = self.game_manager.get_game(self.current_game_id)
            process_name = game_data.get('process_name', '')
            
            if process_name:
                current_total = self.game_manager.get_total_playtime(process_name)
                self.game_manager.set_playtime(process_name, current_total + elapsed)
                self.session_start = time.time()  # Reset for next interval
            
            # Update session display
            minutes = elapsed // 60
            self.session_label.setText(f"Session: {minutes}m")
    
    def on_game_ended(self):
        """Handle game process ending"""
        if self.is_monitoring:
            # Calculate final session time
            if self.session_start:
                elapsed = int(time.time() - self.session_start)
                game_data = self.game_manager.get_game(self.current_game_id)
                process_name = game_data.get('process_name', '')
                
                if process_name:
                    current_total = self.game_manager.get_total_playtime(process_name)
                    self.game_manager.set_playtime(process_name, current_total + elapsed)
                
                self.statusBar().showMessage(
                    f"Session ended: {game_data['name']} ({elapsed // 60}m)"
                )
            
            self.stop_playing(self.current_game_id)
    
    def stop_playing(self, game_id):
        """Stop tracking game session"""
        if not self.is_monitoring or game_id != self.current_game_id:
            return
        
        # Stop monitoring
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.wait()
            self.monitor_thread = None
        
        # Stop auto-save timer
        self.auto_save_timer.stop()
        
        # Update Now Playing tab
        self.playing_label.setText("No game currently running")
        self.session_label.setText("")
        self.stop_game_btn.setEnabled(False)
        
        # Clear tracking state
        self.current_game_id = None
        self.current_pid = None
        self.session_start = None
        
        # Refresh library
        self.refresh_library()
    
    def stop_playing_from_tab(self):
        """Stop playing from the Now Playing tab"""
        if self.current_game_id:
            self.stop_playing(self.current_game_id)
    
    def remove_game(self, game_id):
        """Remove a game from library"""
        game_data = self.game_manager.get_game(game_id)
        if not game_data:
            return
        
        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Remove '{game_data['name']}' from library?\n\n"
            "This will not delete the game files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Remove cover file if it exists
            cover_path = game_data.get('cover')
            if cover_path:
                cover_file = Path(cover_path)
                if not cover_file.is_absolute():
                    cover_file = SCRIPT_DIR / cover_file
                if cover_file.exists():
                    try:
                        cover_file.unlink()
                    except:
                        pass
            
            success, message = self.game_manager.remove_game(game_id)
            if success:
                self.statusBar().showMessage(message)
                self.refresh_library()
            else:
                QMessageBox.critical(self, "Error", message)
    
    def edit_game(self, game_id):
        """Open edit dialog for a game"""
        game_data = self.game_manager.get_game(game_id)
        if not game_data:
            return
        
        # Get current playtime
        process_name = game_data.get('process_name', '')
        total_time = self.game_manager.get_total_playtime(process_name)
        game_data_copy = game_data.copy()
        game_data_copy['playtime'] = int(total_time // 60)
        
        dlg = EditGameDialog(game_data_copy, self)
        dlg.game_updated.connect(lambda updated: self.apply_game_updates(game_id, updated))
        dlg.exec()
    
    def apply_game_updates(self, game_id, updated_data):
        """Apply changes from edit dialog"""
        old_data = self.game_manager.get_game(game_id)
        if not old_data:
            return
        
        new_name = updated_data.get('name', old_data.get('name'))
        new_id = new_name.replace(' ', '_').lower()
        
        # Prevent name collision
        if new_id != game_id and new_id in self.game_manager.library_data:
            QMessageBox.critical(
                self, "Error",
                f"A game with the name '{new_name}' already exists."
            )
            return
        
        # Build new entry
        new_entry = old_data.copy()
        new_entry['name'] = new_name
        new_entry['genre'] = updated_data.get('genre', '')
        new_entry['platform'] = updated_data.get('platform', '')
        new_entry['notes'] = updated_data.get('notes', '')
        new_entry['playtime'] = int(updated_data.get('playtime', 0))
        
        # Update exe_paths
        new_exe_paths = updated_data.get('exe_paths')
        if new_exe_paths:
            new_entry['exe_paths'] = new_exe_paths
            current_exe = new_exe_paths.get('Windows', '') if IS_WINDOWS else new_exe_paths.get('Linux', '')
            if current_exe:
                new_entry['process_name'] = Path(current_exe).stem
        
        # Update playtime in tracking data
        process_name = new_entry.get('process_name')
        if process_name:
            self.game_manager.set_playtime(process_name, new_entry['playtime'] * 60)
        
        # Handle cover image updates
        cover_temp = updated_data.get('cover_temp', '')
        if cover_temp:
            self._update_game_media(new_entry, old_data, cover_temp, 'cover', new_name, COVERS_DIR)
        elif old_data.get('cover') and new_name != old_data.get('name'):
            self._rename_game_media(new_entry, old_data, 'cover', new_name)
        
        # Handle logo image updates
        logo_temp = updated_data.get('logo_temp', '')
        if logo_temp:
            from core.constants import LOGOS_DIR
            self._update_game_media(new_entry, old_data, logo_temp, 'logo', new_name, LOGOS_DIR)
        elif old_data.get('logo') and new_name != old_data.get('name'):
            self._rename_game_media(new_entry, old_data, 'logo', new_name)
        
        # Handle hero image updates
        hero_temp = updated_data.get('hero_temp', '')
        if hero_temp:
            from core.constants import HEROES_DIR
            self._update_game_media(new_entry, old_data, hero_temp, 'hero', new_name, HEROES_DIR)
        elif old_data.get('hero') and new_name != old_data.get('name'):
            self._rename_game_media(new_entry, old_data, 'hero', new_name)
        
        # Save updated entry
        success, new_game_id, message = self.game_manager.update_game(game_id, new_entry)
        
        if success:
            self.statusBar().showMessage(message)
            self.refresh_library()
        else:
            QMessageBox.critical(self, "Error", message)
    
    def _update_game_media(self, new_entry, old_data, temp_path, media_type, game_name, media_dir):
        """Helper to update game media (cover/logo/hero)"""
        try:
            src = Path(temp_path)
            if src.exists():
                dest_name = f"{game_name.replace(' ', '_')}_{media_type}{src.suffix}"
                dest_path = media_dir / dest_name
                shutil.copy(str(src), str(dest_path))
                new_entry[media_type] = str(dest_path.relative_to(SCRIPT_DIR))
                
                # Remove old media file
                old_path = old_data.get(media_type)
                if old_path:
                    old_file = Path(old_path)
                    if not old_file.is_absolute():
                        old_file = SCRIPT_DIR / old_file
                    if old_file.exists() and old_file.resolve() != dest_path.resolve():
                        try:
                            old_file.unlink()
                        except:
                            pass
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to update {media_type}: {e}")
    
    def _rename_game_media(self, new_entry, old_data, media_type, game_name):
        """Helper to rename game media when game name changes"""
        old_path = old_data.get(media_type)
        if old_path:
            old_file = Path(old_path)
            if old_file.exists():
                new_name = f"{game_name.replace(' ', '_')}_{media_type}{old_file.suffix}"
                new_path = old_file.parent / new_name
                try:
                    old_file.rename(new_path)
                    new_entry[media_type] = str(new_path.relative_to(SCRIPT_DIR))
                except:
                    new_entry[media_type] = str(old_file)
